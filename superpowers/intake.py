"""Fast request intake pipeline: clear context, plan, and dispatch skills."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from superpowers.auto_install import check_and_install
from superpowers.config import get_data_dir
from superpowers.role_router import Role, RoleRouter
from superpowers.skill_loader import SkillLoader
from superpowers.skill_registry import SkillRegistry

if TYPE_CHECKING:
    from superpowers.intake_telemetry import IntakeTelemetry

RUNTIME_DIR = get_data_dir() / "runtime"
SESSION_FILE = RUNTIME_DIR / "current_request.json"


@dataclass
class IntakeTask:
    id: int
    requirement: str
    skill: str | None
    status: str = "planned"  # planned|running|ok|failed|skipped
    output: str = ""
    error: str = ""
    assigned_role: str = "executor"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear_context(runtime_dir: Path | None = None) -> Path:
    """Reset runtime intake context files."""
    root = Path(runtime_dir) if runtime_dir else RUNTIME_DIR
    root.mkdir(parents=True, exist_ok=True)

    for p in root.glob("*.json"):
        p.unlink(missing_ok=True)

    marker = {
        "cleared_at": _now(),
        "status": "ready",
    }
    session = root / "context-cleared.json"
    session.write_text(json.dumps(marker, indent=2))
    return session


def extract_requirements(text: str) -> list[str]:
    """Split a request into actionable requirement lines."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("-", "*")):
            line = line[1:].strip()
        if line:
            lines.append(line)
    return lines or [text.strip()]


def build_plan(requirements: list[str]) -> list[IntakeTask]:
    return [IntakeTask(id=i + 1, requirement=req, skill=None) for i, req in enumerate(requirements)]


def _execute_one(
    task: IntakeTask,
    loader: SkillLoader,
    registry: SkillRegistry,
    telemetry: IntakeTelemetry | None = None,
) -> IntakeTask:
    if not task.skill:
        task.status = "skipped"
        task.error = "no mapped skill"
        return task

    if telemetry:
        telemetry.task_started(task.id, task.skill)

    t0 = time.monotonic()
    try:
        skill = registry.get(task.skill)
        task.status = "running"
        result = loader.run_sandboxed(skill, args={"request": task.requirement})
        task.output = (result.stdout + result.stderr).strip()[:2000]
        task.status = "ok" if result.returncode == 0 else "failed"
        if result.returncode != 0 and not task.error:
            task.error = f"exit code {result.returncode}"
    except Exception as exc:
        task.status = "failed"
        task.error = str(exc)

    duration_ms = int((time.monotonic() - t0) * 1000)
    if telemetry and task.skill:
        telemetry.task_completed(task.id, task.skill, task.status, duration_ms)

    return task


def run_intake(
    request_text: str,
    execute: bool = False,
    max_workers: int = 4,
    runtime_dir: Path | None = None,
    skills_dir: Path | None = None,
    progress_callback: object | None = None,
    telemetry: IntakeTelemetry | None = None,
    role: str | None = None,
) -> dict:
    """Run the intake pipeline and return dispatch metadata.

    Args:
        progress_callback: Optional callable(str) invoked with progress messages
                          during execution (e.g., for Telegram real-time updates).
        telemetry: Optional IntakeTelemetry instance for structured audit events.
        role: Optional role filter (planner/executor/verifier). If set and not
              "all", only tasks whose auto-assigned role matches will proceed;
              others are skipped.
    """
    root = Path(runtime_dir) if runtime_dir else RUNTIME_DIR
    root.mkdir(parents=True, exist_ok=True)

    def _notify(msg: str) -> None:
        if progress_callback and callable(progress_callback):
            try:
                progress_callback(msg)
            except Exception:
                pass

    clear_context(root)
    if telemetry:
        telemetry.context_cleared(runtime_dir=str(root))

    requirements = extract_requirements(request_text)
    if telemetry:
        telemetry.requirements_extracted(
            count=len(requirements),
            preview="; ".join(requirements)[:200],
        )

    tasks = build_plan(requirements)
    if telemetry:
        telemetry.plan_built(task_count=len(tasks))

    _notify(f"Planned {len(tasks)} task(s)")

    # --- Role assignment ---
    router = RoleRouter()
    assignments = router.assign_roles(tasks)
    for assignment in assignments:
        for task in tasks:
            if task.id == assignment.task_id:
                task.assigned_role = assignment.role.value
                break

    # If a specific role filter is set, skip non-matching tasks
    if role and role != "all":
        for task in tasks:
            if task.assigned_role != role:
                task.status = "skipped"
                task.error = f"role filter: need {role}, got {task.assigned_role}"

    resolved_skills_dir = Path(skills_dir) if skills_dir else None
    if resolved_skills_dir is None:
        cwd_skills = Path.cwd() / "skills"
        if cwd_skills.is_dir():
            resolved_skills_dir = cwd_skills

    registry = SkillRegistry(skills_dir=resolved_skills_dir)
    for task in tasks:
        if task.status == "skipped":
            continue
        task.skill = check_and_install(
            task.requirement,
            skills_dir=resolved_skills_dir or registry.skills_dir,
            registry=registry,
        )
        if task.skill is None:
            task.status = "failed"
            task.error = "could not map/install skill"
            if telemetry:
                telemetry.skill_map_failed(task.id, task.requirement)
        else:
            if telemetry:
                telemetry.skill_mapped(task.id, task.requirement, task.skill)

    if execute:
        _notify("Executing tasks...")
        loader = SkillLoader()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(_execute_one, task, loader, registry, telemetry)
                for task in tasks
                if task.status != "failed"
            ]
            for future in as_completed(futures):
                completed_task = future.result()
                _notify(f"Task {completed_task.id} ({completed_task.requirement[:50]}): {completed_task.status}")

    payload = {
        "created_at": _now(),
        "execute": execute,
        "role": role,
        "requirements": requirements,
        "tasks": [asdict(t) for t in tasks],
        "role_assignments": [
            {"task_id": a.task_id, "role": a.role.value, "reason": a.reason}
            for a in assignments
        ],
    }
    session_file = root / SESSION_FILE.name
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps(payload, indent=2))

    ok = sum(1 for t in tasks if t.status == "ok")
    failed = sum(1 for t in tasks if t.status == "failed")
    _notify(f"Intake complete: {ok} ok, {failed} failed, {len(tasks)} total")

    if telemetry:
        telemetry.session_saved(
            total=len(tasks), ok=ok, failed=failed, execute=execute,
        )

    return payload
