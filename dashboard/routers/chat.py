"""Chat routes: conversation CRUD, message sending, SSE streaming."""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dashboard.deps import get_conversations_db

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

    # Generate a simple response (no actual LLM call in the API endpoint;
    # real streaming goes through /stream)
    response_text = _generate_response(req.message)
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

    # Store user message
    db.add_message(cid, "user", message)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send conversation ID first
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': cid})}\n\n"

        # Generate response chunks
        full_response = _generate_response(message)
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


def _generate_response(message: str) -> str:
    """Generate a response to a chat message.

    Tries to use 'claude' CLI if available, otherwise returns a simple echo.
    """
    try:
        result = subprocess.run(
            ["claude", "-p", message],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: echo-style response
    return f"Received: {message}\n\n(Claude CLI not available. Install it for AI-powered responses.)"
