"""Slack channel adapter using slack_sdk."""

from __future__ import annotations

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult


class SlackChannel(Channel):
    channel_type = ChannelType.slack

    def __init__(self, bot_token: str):
        if not bot_token:
            raise ChannelError("Slack bot token is required")
        self._token = bot_token

    def send(self, target: str, message: str) -> SendResult:
        try:
            from slack_sdk import WebClient
            from slack_sdk.errors import SlackApiError
        except ImportError:
            return SendResult(
                ok=False,
                channel="slack",
                target=target,
                error="slack_sdk not installed: pip install slack_sdk",
            )

        client = WebClient(token=self._token)
        try:
            resp = client.chat_postMessage(channel=target, text=message)
            return SendResult(
                ok=True,
                channel="slack",
                target=target,
                message=f"ts={resp['ts']}",
            )
        except SlackApiError as exc:
            return SendResult(
                ok=False,
                channel="slack",
                target=target,
                error=str(exc.response["error"]),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            return SendResult(
                ok=False,
                channel="slack",
                target=target,
                error=f"Unexpected error: {exc}",
            )

    def test_connection(self) -> SendResult:
        try:
            from slack_sdk import WebClient
            from slack_sdk.errors import SlackApiError
        except ImportError:
            return SendResult(
                ok=False,
                channel="slack",
                target="",
                error="slack_sdk not installed: pip install slack_sdk",
            )

        client = WebClient(token=self._token)
        try:
            resp = client.auth_test()
            return SendResult(
                ok=True,
                channel="slack",
                target="",
                message=f"bot={resp['user']}, team={resp['team']}",
            )
        except SlackApiError as exc:
            return SendResult(
                ok=False,
                channel="slack",
                target="",
                error=str(exc.response["error"]),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            return SendResult(
                ok=False,
                channel="slack",
                target="",
                error=f"Unexpected error: {exc}",
            )
