"""Shared Telegram Bot API client with retry and backoff."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot"

# Retry settings
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds
_RETRY_CODES = {429, 500, 502, 503, 504}


@dataclass
class ApiResponse:
    ok: bool
    result: Any = None
    error_code: int = 0
    description: str = ""


class TelegramApi:
    """Shared Telegram Bot API client with retry logic."""

    def __init__(self, bot_token: str, timeout: int = 15):
        if not bot_token:
            raise ValueError("bot_token is required")
        self._token = bot_token
        self._timeout = timeout
        self._base = f"{_API_BASE}{bot_token}/"

    def call(
        self,
        method: str,
        payload: dict | None = None,
        *,
        timeout: int | None = None,
        retries: int = _MAX_RETRIES,
    ) -> ApiResponse:
        """Make an API call with automatic retry on transient errors."""
        url = f"{self._base}{method}"
        data = json.dumps(payload).encode() if payload else None
        headers = {"Content-Type": "application/json"} if data else {}
        effective_timeout = timeout or self._timeout

        last_error = ""
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                    body = json.loads(resp.read().decode())

                if body.get("ok"):
                    return ApiResponse(ok=True, result=body.get("result"))
                return ApiResponse(
                    ok=False,
                    error_code=body.get("error_code", 0),
                    description=body.get("description", "unknown error"),
                )

            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}: {exc.reason}"
                if exc.code in _RETRY_CODES and attempt < retries:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    if exc.code == 429:
                        # Rate limited — check Retry-After header
                        retry_after = exc.headers.get("Retry-After")
                        if retry_after:
                            wait = max(wait, float(retry_after))
                    logger.warning(
                        "Telegram API %s error %d, retry %d/%d in %.1fs",
                        method, exc.code, attempt + 1, retries, wait,
                    )
                    time.sleep(wait)
                    continue
                break

            except urllib.error.URLError as exc:
                last_error = str(exc.reason)
                if attempt < retries:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Telegram API %s network error, retry %d/%d in %.1fs",
                        method, attempt + 1, retries, wait,
                    )
                    time.sleep(wait)
                    continue
                break

            except (json.JSONDecodeError, KeyError) as exc:
                last_error = str(exc)
                break

        return ApiResponse(ok=False, description=last_error)

    def fire_and_forget(self, method: str, payload: dict) -> None:
        """Non-blocking API call that silently ignores errors."""
        try:
            self.call(method, payload, retries=0)
        except Exception:
            pass

    # --- Convenience methods ---

    def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> ApiResponse:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.call("sendMessage", payload)

    def send_chat_action(self, chat_id: str, action: str = "typing") -> None:
        self.fire_and_forget("sendChatAction", {"chat_id": chat_id, "action": action})

    def get_updates(self, offset: int = 0, timeout: int = 30) -> ApiResponse:
        return self.call(
            "getUpdates",
            {"offset": offset, "timeout": timeout},
            timeout=timeout + 5,
            retries=1,
        )

    def get_me(self) -> ApiResponse:
        return self.call("getMe")

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
        show_alert: bool = False,
    ) -> ApiResponse:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        if show_alert:
            payload["show_alert"] = True
        return self.call("answerCallbackQuery", payload)

    def set_my_commands(self, commands: list[dict[str, str]]) -> ApiResponse:
        return self.call("setMyCommands", {"commands": commands})
