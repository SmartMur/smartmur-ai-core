"""Per-chat conversation history with Redis (fallback: in-memory dict)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_HISTORY = 20
DEFAULT_TTL = 3600  # 1 hour


@dataclass
class HistoryEntry:
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryEntry:
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
        )


class SessionManager:
    """Per-chat conversation history.

    Uses Redis if available, falls back to in-memory dict.
    Sliding window of last N messages per chat with TTL expiry.
    """

    def __init__(
        self,
        redis_url: str = "",
        max_history: int = DEFAULT_MAX_HISTORY,
        ttl: int = DEFAULT_TTL,
    ):
        self._max_history = max_history
        self._ttl = ttl
        self._redis = None
        self._memory: dict[str, list[HistoryEntry]] = {}

        if redis_url:
            try:
                import redis

                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("SessionManager: using Redis at %s", redis_url)
            except (ImportError, ConnectionError, OSError, ValueError) as exc:
                logger.warning("SessionManager: Redis unavailable (%s), using in-memory", exc)
                self._redis = None

    def _key(self, chat_id: str) -> str:
        return f"tg:session:{chat_id}"

    def add(self, chat_id: str, role: str, content: str) -> None:
        """Add a message to the chat's conversation history."""
        entry = HistoryEntry(role=role, content=content)

        if self._redis:
            try:
                key = self._key(chat_id)
                self._redis.rpush(key, json.dumps(entry.to_dict()))
                # Trim to sliding window
                self._redis.ltrim(key, -self._max_history, -1)
                self._redis.expire(key, self._ttl)
                return
            except (ConnectionError, OSError, ValueError) as exc:
                logger.warning("Redis session write failed: %s", exc)

        # In-memory fallback
        if chat_id not in self._memory:
            self._memory[chat_id] = []
        self._memory[chat_id].append(entry)
        # Trim
        if len(self._memory[chat_id]) > self._max_history:
            self._memory[chat_id] = self._memory[chat_id][-self._max_history :]

    def get(self, chat_id: str) -> list[HistoryEntry]:
        """Get conversation history for a chat."""
        if self._redis:
            try:
                key = self._key(chat_id)
                raw_entries = self._redis.lrange(key, 0, -1)
                entries = [HistoryEntry.from_dict(json.loads(r)) for r in raw_entries]
                # Check TTL — expired entries handled by Redis TTL
                return entries
            except (ConnectionError, OSError, ValueError) as exc:
                logger.warning("Redis session read failed: %s", exc)

        # In-memory fallback
        entries = self._memory.get(chat_id, [])
        # Expire old entries
        cutoff = time.time() - self._ttl
        entries = [e for e in entries if e.timestamp >= cutoff]
        self._memory[chat_id] = entries
        return entries

    def clear(self, chat_id: str) -> None:
        """Clear conversation history for a chat."""
        if self._redis:
            try:
                self._redis.delete(self._key(chat_id))
            except (ConnectionError, OSError):
                pass
        self._memory.pop(chat_id, None)

    def format_context(self, chat_id: str) -> str:
        """Format conversation history as context string for Claude."""
        entries = self.get(chat_id)
        if not entries:
            return ""
        lines = []
        for entry in entries:
            prefix = "Human" if entry.role == "user" else "Assistant"
            lines.append(f"{prefix}: {entry.content}")
        return "\n".join(lines)
