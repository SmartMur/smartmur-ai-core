"""FastAPI service for headless browser automation via Playwright."""

from __future__ import annotations

import base64
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Claw Browser Engine", version="0.1.0")

# --- Global state ---
_sessions: dict[str, dict[str, Any]] = {}
_start_time: float = time.time()

PROFILES_DIR = Path(os.environ.get("BROWSER_PROFILES_DIR", "/data/browser/profiles"))
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


# --- Models ---


class NavigateRequest(BaseModel):
    url: str
    profile: str = "default"
    wait_until: str = "domcontentloaded"


class NavigateResponse(BaseModel):
    url: str
    title: str
    ok: bool
    error: str = ""


class ScreenshotRequest(BaseModel):
    url: str | None = None
    profile: str = "default"
    full_page: bool = True
    selector: str | None = None


class ScreenshotResponse(BaseModel):
    url: str
    title: str
    image_base64: str
    ok: bool
    error: str = ""


class ExtractRequest(BaseModel):
    url: str | None = None
    profile: str = "default"
    selector: str = "body"


class ExtractResponse(BaseModel):
    url: str
    text: str
    ok: bool
    error: str = ""


class TableExtractRequest(BaseModel):
    url: str | None = None
    profile: str = "default"
    selector: str = "table"


class FormFillRequest(BaseModel):
    profile: str = "default"
    fields: dict[str, str]


class ClickRequest(BaseModel):
    profile: str = "default"
    selector: str


class EvalRequest(BaseModel):
    profile: str = "default"
    js: str


class SessionInfo(BaseModel):
    profile: str
    current_url: str
    current_title: str
    created_at: float


class EngineStatus(BaseModel):
    status: str
    uptime_seconds: float
    active_sessions: int
    sessions: list[SessionInfo]
    profiles: list[str]


# --- Session management ---


def _get_or_create_session(profile: str) -> dict[str, Any]:
    """Get an existing browser session or create a new one."""
    if profile in _sessions:
        return _sessions[profile]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="playwright not installed in browser-engine container",
        ) from exc

    pw = sync_playwright().start()
    user_data_dir = PROFILES_DIR / profile
    user_data_dir.mkdir(parents=True, exist_ok=True)

    context = pw.chromium.launch_persistent_context(
        user_data_dir=str(user_data_dir),
        headless=True,
        viewport={"width": 1280, "height": 720},
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    context.set_default_timeout(30000)

    page = context.pages[0] if context.pages else context.new_page()

    session = {
        "playwright": pw,
        "context": context,
        "page": page,
        "profile": profile,
        "created_at": time.time(),
    }
    _sessions[profile] = session
    return session


def _close_session(profile: str) -> None:
    """Close and remove a browser session."""
    if profile not in _sessions:
        return
    session = _sessions.pop(profile)
    try:
        session["context"].close()
    except (OSError, RuntimeError):
        pass
    try:
        session["playwright"].stop()
    except (OSError, RuntimeError):
        pass


# --- Health / Status ---


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status", response_model=EngineStatus)
def engine_status():
    profiles = (
        sorted(d.name for d in PROFILES_DIR.iterdir() if d.is_dir())
        if PROFILES_DIR.exists()
        else []
    )
    sessions = []
    for name, sess in _sessions.items():
        try:
            page = sess["page"]
            sessions.append(
                SessionInfo(
                    profile=name,
                    current_url=page.url,
                    current_title=page.title(),
                    created_at=sess["created_at"],
                )
            )
        except (OSError, RuntimeError, KeyError):
            sessions.append(
                SessionInfo(
                    profile=name,
                    current_url="unknown",
                    current_title="unknown",
                    created_at=sess.get("created_at", 0),
                )
            )
    return EngineStatus(
        status="running",
        uptime_seconds=time.time() - _start_time,
        active_sessions=len(_sessions),
        sessions=sessions,
        profiles=profiles,
    )


@app.get("/profiles")
def list_profiles():
    profiles = (
        sorted(d.name for d in PROFILES_DIR.iterdir() if d.is_dir())
        if PROFILES_DIR.exists()
        else []
    )
    return {"profiles": profiles}


# --- Navigation ---


@app.post("/navigate", response_model=NavigateResponse)
def navigate(req: NavigateRequest):
    try:
        session = _get_or_create_session(req.profile)
        page = session["page"]
        response = page.goto(req.url, wait_until=req.wait_until)
        ok = response is not None and response.ok if response else True
        return NavigateResponse(
            url=page.url,
            title=page.title(),
            ok=ok,
        )
    except HTTPException:
        raise
    except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
        return NavigateResponse(
            url=req.url,
            title="",
            ok=False,
            error=str(exc),
        )


# --- Screenshot ---


@app.post("/screenshot", response_model=ScreenshotResponse)
def screenshot(req: ScreenshotRequest):
    try:
        session = _get_or_create_session(req.profile)
        page = session["page"]

        if req.url:
            page.goto(req.url, wait_until="domcontentloaded")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            screenshot_path = f.name

        if req.selector:
            element = page.locator(req.selector).first
            element.screenshot(path=screenshot_path)
        else:
            page.screenshot(path=screenshot_path, full_page=req.full_page)

        with open(screenshot_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("ascii")

        Path(screenshot_path).unlink(missing_ok=True)

        return ScreenshotResponse(
            url=page.url,
            title=page.title(),
            image_base64=img_data,
            ok=True,
        )
    except HTTPException:
        raise
    except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
        return ScreenshotResponse(
            url=req.url or "unknown",
            title="",
            image_base64="",
            ok=False,
            error=str(exc),
        )


# --- Text extraction ---


@app.post("/extract", response_model=ExtractResponse)
def extract_text(req: ExtractRequest):
    try:
        session = _get_or_create_session(req.profile)
        page = session["page"]

        if req.url:
            page.goto(req.url, wait_until="domcontentloaded")

        text = page.locator(req.selector).first.inner_text()
        return ExtractResponse(url=page.url, text=text, ok=True)
    except HTTPException:
        raise
    except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
        return ExtractResponse(url=req.url or "unknown", text="", ok=False, error=str(exc))


# --- Table extraction ---


@app.post("/extract-table")
def extract_table(req: TableExtractRequest):
    try:
        session = _get_or_create_session(req.profile)
        page = session["page"]

        if req.url:
            page.goto(req.url, wait_until="domcontentloaded")

        table = page.locator(req.selector).first
        rows = []
        tr_elements = table.locator("tr")
        count = tr_elements.count()
        for i in range(count):
            row = tr_elements.nth(i)
            cells = row.locator("th, td")
            cell_count = cells.count()
            row_data = [cells.nth(j).inner_text() for j in range(cell_count)]
            rows.append(row_data)
        return {"url": page.url, "rows": rows, "ok": True}
    except HTTPException:
        raise
    except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
        return {"url": req.url or "unknown", "rows": [], "ok": False, "error": str(exc)}


# --- Form fill ---


@app.post("/fill-form")
def fill_form(req: FormFillRequest):
    try:
        session = _get_or_create_session(req.profile)
        page = session["page"]
        for selector, value in req.fields.items():
            page.fill(selector, value)
        return {"ok": True}
    except HTTPException:
        raise
    except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
        return {"ok": False, "error": str(exc)}


# --- Click ---


@app.post("/click")
def click(req: ClickRequest):
    try:
        session = _get_or_create_session(req.profile)
        page = session["page"]
        page.click(req.selector)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except (TimeoutError, RuntimeError):
            pass
        return {"url": page.url, "title": page.title(), "ok": True}
    except HTTPException:
        raise
    except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
        return {"ok": False, "error": str(exc)}


# --- JS eval ---


@app.post("/evaluate")
def evaluate(req: EvalRequest):
    try:
        session = _get_or_create_session(req.profile)
        page = session["page"]
        result = page.evaluate(req.js)
        return {"result": str(result), "ok": True}
    except HTTPException:
        raise
    except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
        return {"ok": False, "error": str(exc)}


# --- Session management endpoints ---


@app.delete("/sessions/{profile}")
def close_session(profile: str):
    if profile not in _sessions:
        raise HTTPException(status_code=404, detail=f"No active session for profile: {profile}")
    _close_session(profile)
    return {"ok": True, "detail": f"Session '{profile}' closed"}


@app.delete("/sessions")
def close_all_sessions():
    profiles = list(_sessions.keys())
    for p in profiles:
        _close_session(p)
    return {"ok": True, "closed": profiles}


@app.on_event("shutdown")
def shutdown_event():
    profiles = list(_sessions.keys())
    for p in profiles:
        _close_session(p)
