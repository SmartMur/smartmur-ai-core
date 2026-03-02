"""Job monitor: track queued/running/completed tasks."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dashboard.deps import get_jobs_db

router = APIRouter()


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
