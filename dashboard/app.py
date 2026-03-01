"""FastAPI dashboard — serves REST API + static SPA at localhost:8200."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dashboard.routers import (
    audit,
    browser,
    cron,
    memory,
    messaging,
    skills,
    ssh,
    status,
    vault,
    watchers,
    workflows,
)

app = FastAPI(title="Claw Dashboard", version="0.1.0")

# --- API routers ---
app.include_router(status.router, prefix="/api")
app.include_router(cron.router, prefix="/api/cron", tags=["cron"])
app.include_router(messaging.router, prefix="/api/msg", tags=["messaging"])
app.include_router(ssh.router, prefix="/api/ssh", tags=["ssh"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(vault.router, prefix="/api/vault", tags=["vault"])
app.include_router(watchers.router, prefix="/api/watchers", tags=["watchers"])
app.include_router(browser.router, prefix="/api/browser", tags=["browser"])

# --- Static files (SPA) ---
_static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
