"""Chat verification handshake — /start allowlist check and access request queue."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from msg_gateway.telegram.api import TelegramApi
from msg_gateway.telegram.auth import AuthGate
from msg_gateway.telegram.types import Message

logger = logging.getLogger(__name__)


@dataclass
class AccessRequest:
    """A pending access request from an unauthorized user."""

    chat_id: str
    user_id: int = 0
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccessRequest:
        return cls(
            chat_id=data.get("chat_id", ""),
            user_id=data.get("user_id", 0),
            username=data.get("username", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            timestamp=data.get("timestamp", time.time()),
        )

    @classmethod
    def from_message(cls, msg: Message) -> AccessRequest:
        user = msg.from_user
        return cls(
            chat_id=msg.chat_id,
            user_id=user.id if user else 0,
            username=user.username if user else "",
            first_name=user.first_name if user else "",
            last_name=user.last_name if user else "",
        )


class ChatVerification:
    """Manages the /start verification handshake and access request queue.

    When an unauthorized user sends /start:
    1. Check if their chat_id is on the allowlist
    2. If not, send "access request pending" message
    3. Store the request for admin review
    """

    def __init__(
        self,
        api: TelegramApi,
        auth: AuthGate,
        admin_chat_id: str = "",
    ):
        self._api = api
        self._auth = auth
        self._admin_chat_id = admin_chat_id
        self._pending: dict[str, AccessRequest] = {}

    @property
    def pending_requests(self) -> dict[str, AccessRequest]:
        return dict(self._pending)

    def handle_start(self, msg: Message) -> bool:
        """Handle /start command with verification.

        Returns True if the user is authorized, False if access is pending.
        """
        chat_id = msg.chat_id
        if not chat_id:
            return False

        if self._auth.is_allowed(chat_id):
            return True

        # User is not on the allowlist — create access request
        request = AccessRequest.from_message(msg)
        self._pending[chat_id] = request

        # Notify the user
        name = msg.from_user.first_name if msg.from_user else "there"
        self._api.send_message(
            chat_id,
            f"Hello {name}! Your access request is pending admin approval.\n"
            f"Your chat ID: {chat_id}\n\n"
            "You will be notified when your access is granted.",
        )

        # Notify admin if configured
        if self._admin_chat_id:
            user_info = self._format_user_info(request)
            self._api.send_message(
                self._admin_chat_id,
                f"New access request:\n{user_info}\n\nTo approve: /approve {chat_id}",
            )

        logger.info(
            "Access request from chat_id=%s user=%s",
            chat_id,
            request.username or request.first_name or "unknown",
        )
        return False

    def approve(self, chat_id: str) -> bool:
        """Approve a pending access request."""
        self._auth.add(chat_id)
        request = self._pending.pop(chat_id, None)

        # Notify the user
        self._api.send_message(
            chat_id,
            "Your access has been approved! You can now use the bot.\n"
            "Send /help to see available commands.",
        )

        if request:
            logger.info("Approved access for chat_id=%s", chat_id)
        return True

    def deny(self, chat_id: str) -> bool:
        """Deny and remove a pending access request."""
        request = self._pending.pop(chat_id, None)
        if not request:
            return False

        self._api.send_message(
            chat_id,
            "Your access request has been denied.",
        )

        logger.info("Denied access for chat_id=%s", chat_id)
        return True

    def get_pending(self) -> list[AccessRequest]:
        """Get all pending access requests."""
        return list(self._pending.values())

    def _format_user_info(self, request: AccessRequest) -> str:
        parts = [f"  Chat ID: {request.chat_id}"]
        if request.username:
            parts.append(f"  Username: @{request.username}")
        if request.first_name:
            name = request.first_name
            if request.last_name:
                name += f" {request.last_name}"
            parts.append(f"  Name: {name}")
        if request.user_id:
            parts.append(f"  User ID: {request.user_id}")
        return "\n".join(parts)
