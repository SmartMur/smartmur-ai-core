"""Chat ID allowlist authorization gate."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class AuthGate:
    """Authorize incoming messages by chat ID allowlist.

    Secure by default: if no allowlist is configured, ALL messages are rejected.
    Set ALLOWED_CHAT_IDS env var to a comma-separated list of chat IDs.
    """

    def __init__(self, allowed_ids: list[str] | None = None):
        if allowed_ids is not None:
            self._allowed = set(allowed_ids)
        else:
            raw = os.environ.get("ALLOWED_CHAT_IDS", "")
            self._allowed = {cid.strip() for cid in raw.split(",") if cid.strip()}
        self._reject_log: set[str] = set()

    @property
    def is_configured(self) -> bool:
        return len(self._allowed) > 0

    def is_allowed(self, chat_id: str) -> bool:
        if not self.is_configured:
            if chat_id not in self._reject_log:
                logger.warning(
                    "AuthGate: no allowlist configured — rejecting chat_id=%s "
                    "(set ALLOWED_CHAT_IDS env var)",
                    chat_id,
                )
                self._reject_log.add(chat_id)
            return False

        allowed = chat_id in self._allowed
        if not allowed and chat_id not in self._reject_log:
            logger.warning("AuthGate: unauthorized chat_id=%s", chat_id)
            self._reject_log.add(chat_id)
        return allowed

    def add(self, chat_id: str) -> None:
        self._allowed.add(chat_id)

    def remove(self, chat_id: str) -> None:
        self._allowed.discard(chat_id)
