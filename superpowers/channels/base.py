"""Base classes for channel adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChannelType(StrEnum):
    slack = "slack"
    telegram = "telegram"
    discord = "discord"
    email = "email"
    imessage = "imessage"


class ChannelError(Exception):
    """Raised when a channel operation fails."""


@dataclass
class SendResult:
    ok: bool
    channel: str
    target: str
    message: str = ""
    error: str = ""


class Channel:
    """Base class for messaging channel adapters."""

    channel_type: ChannelType

    def send(self, target: str, message: str) -> SendResult:
        raise NotImplementedError

    def test_connection(self) -> SendResult:
        raise NotImplementedError
