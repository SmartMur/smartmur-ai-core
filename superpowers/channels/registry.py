"""Channel registry — factory for channel adapters based on Settings."""

from __future__ import annotations

import sys

from superpowers.channels.base import Channel, ChannelError, ChannelType
from superpowers.config import Settings


class ChannelRegistry:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings.load()
        self._channels: dict[str, Channel] = {}

    def get(self, name: str) -> Channel:
        """Get or lazily create a channel adapter by name."""
        if name in self._channels:
            return self._channels[name]

        channel = self._create(name)
        self._channels[name] = channel
        return channel

    def available(self) -> list[str]:
        """List channel names that have credentials configured."""
        names = []
        s = self._settings
        if s.slack_bot_token:
            names.append("slack")
        if s.telegram_bot_token:
            names.append("telegram")
        if s.discord_bot_token:
            names.append("discord")
        if s.smtp_host and s.smtp_user:
            names.append("email")
        if sys.platform == "darwin":
            names.append("imessage")
        return names

    def _create(self, name: str) -> Channel:
        s = self._settings
        if name == ChannelType.slack.value:
            from superpowers.channels.slack import SlackChannel

            return SlackChannel(bot_token=s.slack_bot_token)
        elif name == ChannelType.telegram.value:
            from superpowers.channels.telegram import TelegramChannel

            return TelegramChannel(bot_token=s.telegram_bot_token)
        elif name == ChannelType.discord.value:
            from superpowers.channels.discord import DiscordChannel

            return DiscordChannel(bot_token=s.discord_bot_token)
        elif name == ChannelType.email.value:
            from superpowers.channels.email import EmailChannel

            return EmailChannel(
                host=s.smtp_host,
                user=s.smtp_user,
                password=s.smtp_pass,
                from_addr=s.smtp_from,
                port=s.smtp_port,
            )
        elif name == ChannelType.imessage.value:
            from superpowers.channels.imessage import IMessageChannel

            return IMessageChannel()
        else:
            raise ChannelError(f"Unknown channel: {name}")
