"""Telegram channel adapter using urllib (no external deps)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult

_API_BASE = "https://api.telegram.org/bot"


class TelegramChannel(Channel):
    channel_type = ChannelType.telegram

    def __init__(self, bot_token: str):
        if not bot_token:
            raise ChannelError("Telegram bot token is required")
        self._token = bot_token

    def _api(self, method: str, payload: dict | None = None) -> dict:
        url = f"{_API_BASE}{self._token}/{method}"
        data = json.dumps(payload).encode() if payload else None
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def send(self, target: str, message: str) -> SendResult:
        try:
            result = self._api("sendMessage", {
                "chat_id": target,
                "text": message,
                "parse_mode": "Markdown",
            })
            if result.get("ok"):
                return SendResult(
                    ok=True, channel="telegram", target=target,
                    message=f"message_id={result['result']['message_id']}",
                )
            return SendResult(
                ok=False, channel="telegram", target=target,
                error=result.get("description", "unknown error"),
            )
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
            return SendResult(
                ok=False, channel="telegram", target=target, error=str(exc),
            )

    def test_connection(self) -> SendResult:
        try:
            result = self._api("getMe")
            if result.get("ok"):
                bot = result["result"]
                return SendResult(
                    ok=True, channel="telegram", target="",
                    message=f"bot=@{bot['username']}",
                )
            return SendResult(
                ok=False, channel="telegram", target="",
                error=result.get("description", "unknown error"),
            )
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
            return SendResult(
                ok=False, channel="telegram", target="", error=str(exc),
            )
