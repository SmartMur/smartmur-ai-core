"""Discord channel adapter using urllib (no external deps)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult

_API_BASE = "https://discord.com/api/v10"


class DiscordChannel(Channel):
    channel_type = ChannelType.discord

    def __init__(self, bot_token: str):
        if not bot_token:
            raise ChannelError("Discord bot token is required")
        self._token = bot_token

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{_API_BASE}{path}"
        data = json.dumps(payload).encode() if payload else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={
                "Authorization": f"Bot {self._token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def send(self, target: str, message: str) -> SendResult:
        try:
            result = self._request("POST", f"/channels/{target}/messages", {
                "content": message,
            })
            return SendResult(
                ok=True, channel="discord", target=target,
                message=f"id={result.get('id', '?')}",
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode() if exc.fp else str(exc)
            return SendResult(
                ok=False, channel="discord", target=target, error=body,
            )
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            return SendResult(
                ok=False, channel="discord", target=target, error=str(exc),
            )

    def test_connection(self) -> SendResult:
        try:
            result = self._request("GET", "/users/@me")
            return SendResult(
                ok=True, channel="discord", target="",
                message=f"bot={result.get('username', '?')}#{result.get('discriminator', '0')}",
            )
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            return SendResult(
                ok=False, channel="discord", target="", error=str(exc),
            )
