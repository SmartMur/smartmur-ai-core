"""Multi-channel messaging adapters."""

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult
from superpowers.channels.registry import ChannelRegistry

__all__ = [
    "Channel",
    "ChannelError",
    "ChannelRegistry",
    "ChannelType",
    "SendResult",
]
