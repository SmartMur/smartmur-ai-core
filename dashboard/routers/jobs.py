"""Job monitor: track queued/running/completed tasks and git-branch job orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dashboard.deps import get_jobs_db

router = APIRouter()
logger = logging.getLogger(__name__)


class JobOut(BaseModel):
    id: str
    name: str
    job_type: str = "shell"
    status: str = "queued"
    started_at: float | None = None
    completed_at: float | None = None
    duration: float | None = None
    output: str = ""
    error: str = ""
    created_at: float


class JobCreate(BaseModel):
    name: str
    job_type: str = "shell"


class JobBranchOut(BaseModel):
    """A job that ran on a git branch."""

    job_id: str
    branch: str
    sha: str = ""
    date: str = ""
    status: str = "unknown"
    name: str = ""


class JobBranchDetail(BaseModel):
    """Full detail for a git-branch job."""

    job_id: str
    name: str
    branch: str
    status: str
    output: str = ""
    error: str = ""
    return_code: int | None = None
    commit_sha: str | None = None
    pr_url: str | None = None
    changed_files: list[str] = []
    started_at: float | None = None
    completed_at: float | None = None
    duration: float | None = None


# --- Git branch job endpoints (must be before /{jid} to avoid path conflicts) ---


@router.get("/branches", response_model=list[JobBranchOut])
def list_job_branches():
    """List all job/* branches and their status."""
    try:
        from superpowers.job_runner import JobRunner

        runner = JobRunner()
        return runner.list_job_branches()
    except (ImportError, OSError, RuntimeError, subprocess.SubprocessError, KeyError) as exc:
        logger.warning("Failed to list job branches: %s", exc)
        return []


@router.get("/branches/{job_id}", response_model=JobBranchDetail)
def get_job_branch(job_id: str):
    """Get details for a specific git-branch job."""
    from superpowers.job_runner import JobRunner

    runner = JobRunner()
    result = runner.get_job(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job branch not found")
    return JobBranchDetail(
        job_id=result.job_id,
        name=result.name,
        branch=result.branch,
        status=result.status.value,
        output=result.output,
        error=result.error,
        return_code=result.return_code,
        commit_sha=result.commit_sha,
        pr_url=result.pr_url,
        changed_files=result.changed_files,
        started_at=result.started_at,
        completed_at=result.completed_at,
        duration=result.duration,
    )


# --- DB-backed job endpoints ---


@router.get("", response_model=list[JobOut])
def list_jobs(limit: int = 50, status: str | None = None):
    db = get_jobs_db()
    return db.list(limit=limit, status=status)


@router.post("", response_model=JobOut, status_code=201)
def create_job(req: JobCreate):
    db = get_jobs_db()
    return db.create(name=req.name, job_type=req.job_type)


@router.get("/{jid}", response_model=JobOut)
def get_job(jid: str):
    from fastapi import HTTPException

    db = get_jobs_db()
    job = db.get(jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{jid}/start")
def start_job(jid: str):
    from fastapi import HTTPException

    db = get_jobs_db()
    if not db.start(jid):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


@router.post("/{jid}/complete")
def complete_job(jid: str, output: str = "", error: str = ""):
    from fastapi import HTTPException

    db = get_jobs_db()
    if not db.complete(jid, output=output, error=error):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


@router.delete("/{jid}", status_code=204)
def delete_job(jid: str):
    from fastapi import HTTPException

    db = get_jobs_db()
    if not db.delete(jid):
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/stream/updates")
async def stream_job_updates():
    """SSE endpoint for real-time job status updates."""
    db = get_jobs_db()

    async def event_generator():
        while True:
            jobs = db.list(limit=20)
            yield f"data: {json.dumps({'type': 'jobs', 'jobs': jobs})}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
