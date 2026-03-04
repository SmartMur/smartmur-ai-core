"""Chat routes: conversation CRUD, message sending, SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dashboard.deps import get_conversations_db

logger = logging.getLogger(__name__)

# --- System prompt & memory injection ---

_SYSTEM_PROMPT_TEMPLATE = """\
You are Claw, Ray's personal AI assistant running on his home server.
You are chatting with Ray through the Claw Dashboard web UI.

Key facts about Ray and this environment:
- Owner: Ray
- Project: Claude Code Superpowers — a local-first automation platform
- Tech stack: Python, Docker, Redis, FastAPI, Alpine.js
- Server: Docker host at 192.168.30.117 (dev-deb, Debian x86_64)
{memories}
Personality: Concise, technical, helpful. No unnecessary fluff.
If Ray asks about himself, his setup, or this project — you know the answer from the facts above.
If Ray asks you to do something on the server, explain what commands or skills would accomplish it."""


def _load_memories() -> str:
    """Load facts from the memory DB for context injection."""
    mem_path = Path(os.environ.get(
        "SUPERPOWERS_DIR", os.path.expanduser("~/.claude-superpowers")
    )) / "memory.db"
    if not mem_path.exists():
        return ""
    try:
        conn = sqlite3.connect(str(mem_path))
        rows = conn.execute(
            "SELECT category, key, value FROM memories ORDER BY access_count DESC LIMIT 20"
        ).fetchall()
        conn.close()
        if not rows:
            return ""
        lines = [f"- [{cat}] {key}: {val}" for cat, key, val in rows]
        return "\nMemories:\n" + "\n".join(lines) + "\n"
    except (sqlite3.Error, OSError, ValueError) as exc:
        logger.warning("Failed to load memories: %s", exc)
        return ""


def _build_system_prompt() -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(memories=_load_memories())


def _build_conversation_context(messages: list[dict], max_turns: int = 10) -> str:
    """Format recent conversation history for context."""
    recent = messages[-(max_turns * 2):]  # last N turns (user+assistant pairs)
    if not recent:
        return ""
    lines = []
    for msg in recent:
        role = "Ray" if msg.get("role") == "user" else "Claw"
        lines.append(f"{role}: {msg['content']}")
    return (
        "\n<conversation_history>\n"
        + "\n".join(lines)
        + "\n</conversation_history>\n\n"
    )

router = APIRouter()


class ChatMessage(BaseModel):
    message: str
    conversation_id: str = ""


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[dict]
    created_at: float
    updated_at: float


# --- Conversation CRUD ---


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations():
    db = get_conversations_db()
    return db.list()


@router.post("/conversations", response_model=ConversationDetail, status_code=201)
def create_conversation():
    db = get_conversations_db()
    return db.create()


@router.get("/conversations/{cid}", response_model=ConversationDetail)
def get_conversation(cid: str):
    db = get_conversations_db()
    conv = db.get(cid)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: str):
    db = get_conversations_db()
    if not db.delete(cid):
        raise HTTPException(status_code=404, detail="Conversation not found")


# --- Chat message sending ---


@router.post("/send")
def send_message(req: ChatMessage):
    db = get_conversations_db()

    # Create conversation if needed
    cid = req.conversation_id
    if not cid:
        conv = db.create()
        cid = conv["id"]

    # Store user message
    conv = db.add_message(cid, "user", req.message)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Build context from conversation history
    history = conv.get("messages", [])[:-1]  # exclude the message we just added
    response_text = _generate_response(req.message, history)
    db.add_message(cid, "assistant", response_text)

    return {
        "conversation_id": cid,
        "response": response_text,
    }


@router.get("/stream")
async def stream_chat(message: str, conversation_id: str = ""):
    """SSE endpoint for streaming chat responses."""
    db = get_conversations_db()

    cid = conversation_id
    if not cid:
        conv = db.create()
        cid = conv["id"]

    # Get existing history before adding new message
    conv = db.get(cid)
    history = conv["messages"] if conv else []

    # Store user message
    db.add_message(cid, "user", message)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send conversation ID first
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': cid})}\n\n"

        # Generate response with full context
        full_response = _generate_response(message, history)
        words = full_response.split()
        accumulated = []

        for i, word in enumerate(words):
            accumulated.append(word)
            chunk = word + (" " if i < len(words) - 1 else "")
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            await asyncio.sleep(0.03)  # Simulate streaming delay

        # Store complete response
        db.add_message(cid, "assistant", " ".join(accumulated))

        # Signal completion
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': cid})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _generate_response(message: str, history: list[dict] | None = None) -> str:
    """Generate a response using the LLM provider with system prompt and history."""
    from superpowers.llm_provider import get_default_provider

    system_prompt = _build_system_prompt()
    context = _build_conversation_context(history or [])

    # Build the full prompt: conversation history + current message
    if context:
        full_prompt = f"{context}Ray: {message}"
    else:
        full_prompt = message

    try:
        provider = get_default_provider(role="chat")
        result = provider.invoke(full_prompt, system_prompt=system_prompt)
        if result.strip():
            return result.strip()
    except FileNotFoundError:
        logger.error("LLM provider not available — check configuration")
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        logger.warning("LLM provider error: %s", exc)
        return "Response timed out — try a shorter question."

    return (
        f"Received: {message}\n\n"
        "(LLM provider not available. Check configuration.)"
    )
