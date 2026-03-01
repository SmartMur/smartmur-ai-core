"""Cron job CRUD, execution, and log retrieval."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from dashboard.deps import get_cron_engine
from dashboard.models import CronJobCreate, CronJobOut, CronLogEntry

router = APIRouter()


def _job_to_out(job) -> CronJobOut:
    return CronJobOut(
        id=job.id,
        name=job.name,
        schedule=job.schedule,
        job_type=job.job_type.value,
        command=job.command,
        args=job.args,
        output_channel=job.output_channel,
        enabled=job.enabled,
        created_at=job.created_at,
        last_run=job.last_run,
        last_status=job.last_status,
    )


@router.get("/jobs", response_model=list[CronJobOut])
def list_jobs():
    engine = get_cron_engine()
    return [_job_to_out(j) for j in engine.list_jobs()]


@router.get("/jobs/{job_id}", response_model=CronJobOut)
def get_job(job_id: str):
    engine = get_cron_engine()
    try:
        return _job_to_out(engine.get_job(job_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/jobs", response_model=CronJobOut, status_code=201)
def create_job(req: CronJobCreate):
    engine = get_cron_engine()
    try:
        job = engine.add_job(
            name=req.name,
            schedule=req.schedule,
            job_type=req.job_type,
            command=req.command,
            args=req.args,
            output_channel=req.output_channel,
            enabled=req.enabled,
        )
        return _job_to_out(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    engine = get_cron_engine()
    try:
        engine.remove_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/jobs/{job_id}/enable", response_model=CronJobOut)
def enable_job(job_id: str):
    engine = get_cron_engine()
    try:
        return _job_to_out(engine.enable_job(job_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/jobs/{job_id}/disable", response_model=CronJobOut)
def disable_job(job_id: str):
    engine = get_cron_engine()
    try:
        return _job_to_out(engine.disable_job(job_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/jobs/{job_id}/run", response_model=CronJobOut)
def run_job(job_id: str):
    engine = get_cron_engine()
    try:
        engine._execute_job(job_id)
        return _job_to_out(engine.get_job(job_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/jobs/{job_id}/logs", response_model=list[CronLogEntry])
def get_job_logs(job_id: str, limit: int = 20):
    engine = get_cron_engine()
    try:
        engine.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")

    output_dir = engine._output_dir / job_id
    if not output_dir.is_dir():
        return []

    log_files = sorted(output_dir.glob("*.log"), reverse=True)[:limit]
    entries = []
    for lf in log_files:
        entries.append(CronLogEntry(
            filename=lf.name,
            content=lf.read_text()[:4000],
        ))
    return entries
