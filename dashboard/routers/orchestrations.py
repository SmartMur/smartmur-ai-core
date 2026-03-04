"""Orchestrations monitor: list runs, get details, trigger execution."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from superpowers.config import get_data_dir

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Models ---


class OrchRunOut(BaseModel):
    command: str
    status: str
    started_at: str = ""
    finished_at: str = ""
    report_path: str = ""
    summary: str = ""
    steps_passed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    total_duration_ms: int = 0
    step_details: list[dict] = []
    timestamp: str = ""


class OrchStatusOut(BaseModel):
    total_runs: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    last_run_time: str = ""
    commands: list[str] = []


class OrchTriggerRequest(BaseModel):
    dry_run: bool = False
    repo_path: str | None = None


class OrchTriggerResponse(BaseModel):
    ok: bool
    message: str


# --- Helpers ---


def _output_dir() -> Path:
    return get_data_dir() / "orchestrator"


def _list_runs_for_command(command: str, limit: int = 50) -> list[dict]:
    """Read saved JSON reports for a command, sorted newest first."""
    cmd_dir = _output_dir() / command
    if not cmd_dir.is_dir():
        return []

    runs = []
    for f in sorted(cmd_dir.glob("*.json"), reverse=True):
        if f.name == "latest.json":
            continue
        try:
            data = json.loads(f.read_text())
            data["timestamp"] = f.stem  # e.g. "20260301-120000"
            runs.append(data)
        except (json.JSONDecodeError, OSError):
            continue
        if len(runs) >= limit:
            break
    return runs


def _all_commands() -> list[str]:
    """Return all command names that have at least one saved report."""
    out_dir = _output_dir()
    if not out_dir.is_dir():
        return []
    return sorted(d.name for d in out_dir.iterdir() if d.is_dir() and any(d.glob("*.json")))


# --- Endpoints ---


@router.get("/status", response_model=OrchStatusOut)
def orchestrations_status():
    """Summary: total runs, pass/fail counts, last run time."""
    commands = _all_commands()
    total = 0
    passed = 0
    failed = 0
    error = 0
    last_run_time = ""

    for cmd in commands:
        runs = _list_runs_for_command(cmd)
        for r in runs:
            total += 1
            st = r.get("status", "")
            if st == "passed":
                passed += 1
            elif st == "failed":
                failed += 1
            elif st == "error":
                error += 1

            run_time = r.get("finished_at") or r.get("started_at") or ""
            if run_time and run_time > last_run_time:
                last_run_time = run_time

    return OrchStatusOut(
        total_runs=total,
        passed=passed,
        failed=failed,
        error=error,
        last_run_time=last_run_time,
        commands=commands,
    )


@router.get("", response_model=list[OrchRunOut])
def list_orchestrations(limit: int = 50):
    """List recent orchestration runs across all commands."""
    commands = _all_commands()
    all_runs: list[dict] = []
    for cmd in commands:
        all_runs.extend(_list_runs_for_command(cmd, limit=limit))

    # Sort by started_at descending
    all_runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    return all_runs[:limit]


@router.get("/{command}", response_model=list[OrchRunOut])
def list_command_runs(command: str, limit: int = 50):
    """List runs for a specific orchestration command."""
    runs = _list_runs_for_command(command, limit=limit)
    if not runs:
        raise HTTPException(status_code=404, detail=f"No runs found for command: {command}")
    return runs


@router.get("/{command}/latest", response_model=OrchRunOut)
def get_latest_run(command: str):
    """Get the most recent run for a command."""
    runs = _list_runs_for_command(command, limit=1)
    if not runs:
        raise HTTPException(status_code=404, detail=f"No runs found for command: {command}")
    return runs[0]


@router.get("/{command}/runs/{timestamp}", response_model=OrchRunOut)
def get_specific_run(command: str, timestamp: str):
    """Get a specific run by timestamp."""
    cmd_dir = _output_dir() / command
    json_path = cmd_dir / f"{timestamp}.json"
    if not json_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Run not found: {command}/{timestamp}",
        )
    try:
        data = json.loads(json_path.read_text())
        data["timestamp"] = timestamp
        return data
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read report: {exc}")


@router.post("/{command}/run", response_model=OrchTriggerResponse)
def trigger_run(command: str, req: OrchTriggerRequest | None = None):
    """Trigger an orchestration run in a background thread."""
    from superpowers.orchestrator import ORCHESTRATION_COMMANDS, Orchestrator

    if command not in ORCHESTRATION_COMMANDS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown orchestration command: {command}",
        )

    dry_run = req.dry_run if req else False
    repo_path = req.repo_path if req else None

    def _run_bg():
        try:
            orch = Orchestrator()
            orch.run(command, repo_path=repo_path, dry_run=dry_run)
        except Exception:
            logger.exception("Background orchestration run failed: %s", command)

    thread = threading.Thread(target=_run_bg, daemon=True)
    thread.start()

    mode = "dry-run" if dry_run else "live"
    return OrchTriggerResponse(
        ok=True,
        message=f"Orchestration '{command}' triggered ({mode})",
    )
