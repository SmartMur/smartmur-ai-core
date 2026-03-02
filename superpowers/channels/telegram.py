"""Telegram channel adapter using urllib (no external deps)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot"

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds
_RETRY_HTTP_CODES = {429, 500, 502, 503, 504}


class TelegramChannel(Channel):
    channel_type = ChannelType.telegram

    def __init__(self, bot_token: str):
        if not bot_token:
            raise ChannelError("Telegram bot token is required")
        self._token = bot_token

    def _api(
        self,
        method: str,
        payload: dict | None = None,
        *,
        retries: int = _MAX_RETRIES,
    ) -> dict:
        url = f"{_API_BASE}{self._token}/{method}"
        data = json.dumps(payload).encode() if payload else None
        headers = {"Content-Type": "application/json"} if data else {}

        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode())

            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code in _RETRY_HTTP_CODES and attempt < retries:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    if exc.code == 429:
                        retry_after = exc.headers.get("Retry-After")
                        if retry_after:
                            wait = max(wait, float(retry_after))
                    logger.warning(
                        "Telegram API %s HTTP %d, retry %d/%d in %.1fs",
                        method, exc.code, attempt + 1, retries, wait,
                    )
                    time.sleep(wait)
                    continue
                # Non-retryable HTTP error — raise immediately
                raise

            except urllib.error.URLError as exc:
                last_exc = exc
                if attempt < retries:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Telegram API %s network error, retry %d/%d in %.1fs",
                        method, attempt + 1, retries, wait,
                    )
                    time.sleep(wait)
                    continue
                raise

        # Should not reach here, but just in case
        raise last_exc  # type: ignore[misc]

    def send(
        self,
        target: str,
        message: str,
        *,
        parse_mode: str = "Markdown",
        reply_markup: dict | None = None,
    ) -> SendResult:
        try:
            payload: dict = {
                "chat_id": target,
                "text": message,
                "parse_mode": parse_mode,
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            result = self._api("sendMessage", payload)
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
