"""FastAPI messaging gateway — HTTP API for channel dispatch."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from msg_gateway.models import ChannelStatus, HealthResponse, SendRequest, SendResponse
from superpowers.channels.base import ChannelError
from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings

app = FastAPI(title="Claude Superpowers Message Gateway", version="0.1.0")

_registry: ChannelRegistry | None = None


def _get_registry() -> ChannelRegistry:
    global _registry
    if _registry is None:
        _registry = ChannelRegistry(Settings.load())
    return _registry


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
