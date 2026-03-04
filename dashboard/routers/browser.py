"""Browser: engine status, profiles, and remote automation controls."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

BROWSER_ENGINE_URL = os.environ.get("BROWSER_ENGINE_URL", "http://browser-engine:8300")


class BrowserEngineStatus(BaseModel):
    engine_online: bool
    status: str = "unknown"
    uptime_seconds: float = 0
    active_sessions: int = 0
    sessions: list[dict] = []
    profiles: list[str] = []
    error: str = ""


class BrowserProfileOut(BaseModel):
    name: str


class NavigateRequest(BaseModel):
    url: str
    profile: str = "default"


class NavigateResponse(BaseModel):
    url: str = ""
    title: str = ""
    ok: bool = False
    error: str = ""


class ScreenshotRequest(BaseModel):
    url: str | None = None
    profile: str = "default"
    full_page: bool = True
    selector: str | None = None


class ScreenshotResponse(BaseModel):
    url: str = ""
    title: str = ""
    image_base64: str = ""
    ok: bool = False
    error: str = ""


def _engine_url(path: str) -> str:
    return f"{BROWSER_ENGINE_URL}{path}"


@router.get("/status", response_model=BrowserEngineStatus)
def browser_status():
    """Get browser engine status including active sessions and profiles."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(_engine_url("/status"))
            resp.raise_for_status()
            data = resp.json()
            return BrowserEngineStatus(
                engine_online=True,
                status=data.get("status", "running"),
                uptime_seconds=data.get("uptime_seconds", 0),
                active_sessions=data.get("active_sessions", 0),
                sessions=data.get("sessions", []),
                profiles=data.get("profiles", []),
            )
    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        return BrowserEngineStatus(
            engine_online=False,
            status="offline",
            error=str(exc),
        )


@router.get("/profiles", response_model=list[BrowserProfileOut])
def list_profiles():
    """List browser profiles from the engine, falling back to local profiles."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(_engine_url("/profiles"))
            resp.raise_for_status()
            data = resp.json()
            return [BrowserProfileOut(name=name) for name in data.get("profiles", [])]
    except (httpx.HTTPError, OSError, ValueError, KeyError):
        # Fallback to local profile manager
        try:
            from dashboard.deps import get_browser_profiles

            pm = get_browser_profiles()
            return [BrowserProfileOut(name=name) for name in pm.list_profiles()]
        except (ImportError, OSError, RuntimeError):
            return []


@router.post("/navigate", response_model=NavigateResponse)
def navigate(req: NavigateRequest):
    """Navigate to a URL via the browser engine."""
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _engine_url("/navigate"),
                json={
                    "url": req.url,
                    "profile": req.profile,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return NavigateResponse(**data)
    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        return NavigateResponse(url=req.url, ok=False, error=str(exc))


@router.post("/screenshot", response_model=ScreenshotResponse)
def screenshot(req: ScreenshotRequest):
    """Take a screenshot via the browser engine."""
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _engine_url("/screenshot"),
                json={
                    "url": req.url,
                    "profile": req.profile,
                    "full_page": req.full_page,
                    "selector": req.selector,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return ScreenshotResponse(**data)
    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        return ScreenshotResponse(ok=False, error=str(exc))


@router.delete("/sessions/{profile}")
def close_session(profile: str):
    """Close a browser session on the engine."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.delete(_engine_url(f"/sessions/{profile}"))
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"Browser engine error: {exc}")


@router.delete("/sessions")
def close_all_sessions():
    """Close all browser sessions on the engine."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.delete(_engine_url("/sessions"))
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"Browser engine error: {exc}")
