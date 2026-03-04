"""Messaging: channels, profiles, send."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dashboard.deps import get_channel_registry, get_profile_manager
from superpowers.channels.base import ChannelError
from dashboard.models import (
    ChannelInfo,
    ProfileOut,
    ProfileSendRequest,
    SendMessageRequest,
    SendMessageResponse,
)

router = APIRouter()

ALL_CHANNELS = ["slack", "telegram", "discord", "email"]


@router.get("/channels", response_model=list[ChannelInfo])
def list_channels():
    reg = get_channel_registry()
    available = reg.available()
    return [ChannelInfo(name=ch, configured=ch in available) for ch in ALL_CHANNELS]


@router.post("/send", response_model=SendMessageResponse)
def send_message(req: SendMessageRequest):
    reg = get_channel_registry()
    try:
        ch = reg.get(req.channel)
    except (ChannelError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = ch.send(req.target, req.message)
    return SendMessageResponse(
        ok=result.ok,
        channel=result.channel,
        target=result.target,
        error=result.error or "",
    )


@router.post("/test/{channel}", response_model=SendMessageResponse)
def test_channel(channel: str):
    reg = get_channel_registry()
    try:
        ch = reg.get(channel)
    except (ChannelError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = ch.test_connection()
    return SendMessageResponse(
        ok=result.ok,
        channel=result.channel,
        target=result.target,
        error=result.error or "",
    )


@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles():
    pm = get_profile_manager()
    return [
        ProfileOut(
            name=p.name,
            targets=[{"channel": t.channel, "target": t.target} for t in p.targets],
        )
        for p in pm.list_profiles()
    ]


@router.post("/profiles/{name}/send", response_model=list[SendMessageResponse])
def send_via_profile(name: str, req: ProfileSendRequest):
    pm = get_profile_manager()
    try:
        results = pm.send(name, req.message)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}")

    return [
        SendMessageResponse(
            ok=r.ok,
            channel=r.channel,
            target=r.target,
            error=r.error or "",
        )
        for r in results
    ]
