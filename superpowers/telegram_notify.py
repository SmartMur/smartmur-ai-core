"""Instant Telegram notification helper — always-on communication channel.

Usage:
    from superpowers.telegram_notify import notify, notify_start, notify_done, notify_error

    notify("Hello from Claude!")
    notify_start("Working on feature X")
    notify_done("Feature X complete")
    notify_error("Build failed", details="exit code 1")
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime

_API_BASE = "https://api.telegram.org/bot"


def _get_config() -> tuple[str, str]:
    """Get bot token and chat ID from environment."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID", "")
    return token, chat_id


def notify(message: str, *, chat_id: str = "", parse_mode: str = "Markdown") -> bool:
    """Send a message to Telegram immediately. Returns True on success.

    Near-instant delivery — uses direct urllib call with 5s timeout.
    Falls back silently on failure (never blocks the caller).
    """
    token, default_chat = _get_config()
    if not token:
        return False
    target = chat_id or default_chat
    if not target:
        return False

    try:
        url = f"{_API_BASE}{token}/sendMessage"
        payload = json.dumps({
            "chat_id": target,
            "text": message,
            "parse_mode": parse_mode,
        }).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("ok", False)
    except Exception:
        return False


def _ts() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S UTC")


def notify_start(task: str, **kwargs) -> bool:
    """Send a [STARTED] notification."""
    return notify(f"[STARTED] {task}\n_{_ts()}_", **kwargs)


def notify_done(task: str, **kwargs) -> bool:
    """Send a [COMPLETED] notification."""
    return notify(f"[COMPLETED] {task}\n_{_ts()}_", **kwargs)


def notify_error(task: str, details: str = "", **kwargs) -> bool:
    """Send an [ERROR] notification."""
    msg = f"[ERROR] {task}"
    if details:
        msg += f"\n```\n{details[:1000]}\n```"
    msg += f"\n_{_ts()}_"
    return notify(msg, **kwargs)


def notify_progress(task: str, pct: int | None = None, **kwargs) -> bool:
    """Send a [PROGRESS] notification."""
    msg = f"[PROGRESS] {task}"
    if pct is not None:
        msg += f" ({pct}%)"
    msg += f"\n_{_ts()}_"
    return notify(msg, **kwargs)
