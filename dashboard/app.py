"""FastAPI dashboard — serves REST API + static SPA at localhost:8200."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from dashboard.deps import require_auth
from dashboard.routers import (
    audit,
    auth,
    browser,
    chat,
    cron,
    github,
    jobs,
    memory,
    messaging,
    notifications,
    reports,
    settings,
    skills,
    ssh,
    status,
    vault,
    watchers,
    workflows,
)

app = FastAPI(title="Claw Dashboard", version="0.2.0")


# --- Public endpoints ---
@app.get("/health")
def health():
    return {"status": "ok"}


# --- Public auth routes (no auth required) ---
app.include_router(auth.router, tags=["auth"])


# --- Protected API routers (all under /api/*) ---
api_router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])
api_router.include_router(status.router)
api_router.include_router(cron.router, prefix="/cron", tags=["cron"])
api_router.include_router(messaging.router, prefix="/msg", tags=["messaging"])
api_router.include_router(ssh.router, prefix="/ssh", tags=["ssh"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_router.include_router(watchers.router, prefix="/watchers", tags=["watchers"])
api_router.include_router(browser.router, prefix="/browser", tags=["browser"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(github.router, prefix="/github", tags=["github"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(api_router)

# --- Static files (SPA) ---
_static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
