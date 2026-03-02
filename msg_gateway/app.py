"""FastAPI messaging gateway — HTTP API for channel dispatch."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from msg_gateway.models import ChannelStatus, HealthResponse, SendRequest, SendResponse
from superpowers.channels.base import ChannelError
from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Claude Superpowers Message Gateway", version="0.1.0")

_registry: ChannelRegistry | None = None
_telegram_poller: Any = None  # TelegramPoller instance for webhook mode


def _get_registry() -> ChannelRegistry:
    global _registry
    if _registry is None:
        _registry = ChannelRegistry(Settings.load())
    return _registry


def set_telegram_poller(poller: Any) -> None:
    """Register a TelegramPoller instance for webhook mode."""
    global _telegram_poller
    _telegram_poller = poller


def get_telegram_poller() -> Any:
    """Get the registered TelegramPoller instance."""
    return _telegram_poller


@app.get("/health", response_model=HealthResponse)
def health():
    reg = _get_registry()
    available = reg.available()
    all_channels = ["slack", "telegram", "discord", "email"]
    return HealthResponse(
        status="ok",
        channels=[
            ChannelStatus(name=ch, configured=ch in available)
            for ch in all_channels
        ],
    )


@app.get("/channels", response_model=list[str])
def channels():
    return _get_registry().available()


@app.post("/send", response_model=SendResponse)
def send(req: SendRequest):
    reg = _get_registry()
    try:
        ch = reg.get(req.channel)
    except ChannelError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = ch.send(req.target, req.message)
    return SendResponse(
        ok=result.ok,
        channel=result.channel,
        target=result.target,
        message=result.message,
        error=result.error,
    )


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Receive Telegram updates via webhook POST.

    Validates the X-Telegram-Bot-Api-Secret-Token header, then
    dispatches the update to the registered TelegramPoller's handler.
    """
    poller = get_telegram_poller()
    if poller is None:
        raise HTTPException(
            status_code=503,
            detail="Telegram webhook not configured — no poller registered",
        )

    webhook_handler = poller.webhook_handler

    # Validate secret token (fail-closed)
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not webhook_handler.validate_secret(secret_header):
        logger.warning("Webhook request with invalid secret token rejected")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    # Parse the update JSON
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Process the update
    ok = webhook_handler.process_update(data)
    return {"ok": ok}
