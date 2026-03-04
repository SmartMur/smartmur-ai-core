"""Abstract base class for inbound channel adapters.

This defines the interface contract for adapters that receive webhook
messages, process them, and send responses.  It is separate from the
simpler ``superpowers.channels.base.Channel`` (which handles outbound-only
send/test).  This base adds inbound parsing, acknowledgement, typing
indicators, and streaming support.

Existing adapters (Slack, Telegram, Discord, etc.) can be migrated to
this interface incrementally.  Creating the base first establishes the
contract without requiring a rewrite of working code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Message:
    """Normalized inbound message from any channel."""

    id: str
    channel: str  # e.g. "telegram", "slack", "discord"
    sender_id: str
    sender_name: str
    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = field(default_factory=dict)
    chat_id: str = ""
    reply_to_id: str = ""
    attachments: list[dict[str, Any]] = field(default_factory=list)


class ChannelAdapter(ABC):
    """Abstract base class for inbound channel adapters.

    Each adapter handles:
    - Parsing inbound webhook payloads into normalized ``Message`` objects
    - Sending acknowledgements (read receipts / reactions)
    - Showing processing indicators (typing, "working..." reactions)
    - Sending text responses back to the originating channel

    Subclasses MUST implement all abstract methods.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short channel identifier, e.g. ``'telegram'``, ``'slack'``."""
        ...

    @property
    def supports_streaming(self) -> bool:
        """Whether this adapter can stream partial responses.

        Override and return ``True`` if the channel supports message editing
        or chunked delivery (e.g. Telegram edit, Slack update).
        """
        return False

    @abstractmethod
    async def receive(self, request: Any) -> Message:
        """Parse an inbound webhook request into a normalized ``Message``.

        Parameters
        ----------
        request:
            The raw HTTP request object (e.g. ``starlette.requests.Request``).

        Returns
        -------
        Message
            Parsed and normalized message.

        Raises
        ------
        ValueError
            If the request cannot be parsed.
        """
        ...

    @abstractmethod
    async def acknowledge(self, message: Message) -> None:
        """Send a read receipt or reaction to acknowledge the message.

        For Telegram this might add a reaction emoji.
        For Slack this might add a checkmark reaction.
        For channels that don't support acknowledgements, this is a no-op.
        """
        ...

    @abstractmethod
    async def start_processing_indicator(self, message: Message) -> None:
        """Show that the bot is working on a response.

        Typically sends a "typing" indicator.  Should be called immediately
        after receiving a message and before starting long-running work.
        """
        ...

    @abstractmethod
    async def send_response(self, message: Message, response: str) -> None:
        """Send a text response back to the channel/chat that sent ``message``.

        Parameters
        ----------
        message:
            The original inbound message (used to determine reply target).
        response:
            The text to send.
        """
        ...
