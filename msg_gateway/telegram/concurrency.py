"""Per-chat semaphore and job queue for Telegram bot concurrency control."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_MAX_PER_CHAT = 2
DEFAULT_MAX_GLOBAL = 5
DEFAULT_QUEUE_OVERFLOW = 10


@dataclass
class ConcurrencyStats:
    chat_active: int = 0
    chat_queued: int = 0
    global_active: int = 0
    global_max: int = DEFAULT_MAX_GLOBAL


class ConcurrencyGate:
    """Control concurrent job execution per chat and globally.

    - max_per_chat: Maximum concurrent jobs per chat (default: 2)
    - max_global: Maximum concurrent jobs across all chats (default: 5)
    - queue_overflow: Maximum queued jobs per chat before rejecting (default: 10)
    """

    def __init__(
        self,
        max_per_chat: int = DEFAULT_MAX_PER_CHAT,
        max_global: int = DEFAULT_MAX_GLOBAL,
        queue_overflow: int = DEFAULT_QUEUE_OVERFLOW,
    ):
        self._max_per_chat = max_per_chat
        self._max_global = max_global
        self._queue_overflow = queue_overflow

        self._global_sem = threading.Semaphore(max_global)
        self._chat_sems: dict[str, threading.Semaphore] = {}
        self._chat_queued: dict[str, int] = {}
        self._lock = threading.Lock()
        self._active_count = 0

    def _get_chat_sem(self, chat_id: str) -> threading.Semaphore:
        with self._lock:
            if chat_id not in self._chat_sems:
                self._chat_sems[chat_id] = threading.Semaphore(self._max_per_chat)
                self._chat_queued[chat_id] = 0
            return self._chat_sems[chat_id]

    def try_acquire(self, chat_id: str) -> bool:
        """Try to acquire a slot. Returns True if acquired, False if queue full."""
        with self._lock:
            queued = self._chat_queued.get(chat_id, 0)
            if queued >= self._queue_overflow:
                logger.warning(
                    "ConcurrencyGate: queue overflow for chat_id=%s (%d queued)",
                    chat_id, queued,
                )
                return False
            self._chat_queued[chat_id] = queued + 1

        chat_sem = self._get_chat_sem(chat_id)

        # Block waiting for per-chat slot
        chat_sem.acquire()
        # Block waiting for global slot
        self._global_sem.acquire()

        with self._lock:
            self._active_count += 1
            self._chat_queued[chat_id] = max(0, self._chat_queued.get(chat_id, 1) - 1)

        return True

    def release(self, chat_id: str) -> None:
        """Release a slot after job completion."""
        with self._lock:
            self._active_count = max(0, self._active_count - 1)

        self._global_sem.release()
        chat_sem = self._get_chat_sem(chat_id)
        chat_sem.release()

    def stats(self, chat_id: str) -> ConcurrencyStats:
        """Get concurrency stats for a chat."""
        with self._lock:
            return ConcurrencyStats(
                chat_active=self._max_per_chat - self._get_chat_sem(chat_id)._value,
                chat_queued=self._chat_queued.get(chat_id, 0),
                global_active=self._active_count,
                global_max=self._max_global,
            )
