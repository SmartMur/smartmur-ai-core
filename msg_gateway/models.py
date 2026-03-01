"""Pydantic v2 request/response models for the messaging gateway."""

from __future__ import annotations

from pydantic import BaseModel


class SendRequest(BaseModel):
    channel: str
    target: str
    message: str


class SendResponse(BaseModel):
    ok: bool
    channel: str
    target: str
    message: str = ""
    error: str = ""


class ChannelStatus(BaseModel):
    name: str
    configured: bool


class HealthResponse(BaseModel):
    status: str
    channels: list[ChannelStatus]
