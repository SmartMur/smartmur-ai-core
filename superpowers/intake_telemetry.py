"""Structured telemetry for intake pipeline lifecycle."""

from __future__ import annotations

from superpowers.audit import AuditLog


class IntakeTelemetry:
    """Emit structured audit events for each intake lifecycle phase."""

    def __init__(self, audit: AuditLog | None = None):
        self._audit = audit or AuditLog()

    def context_cleared(self, runtime_dir: str = "") -> None:
        self._audit.log(
            "intake.context_cleared",
            "context cleared",
            "intake",
            metadata={"runtime_dir": runtime_dir},
        )

    def requirements_extracted(self, count: int, preview: str = "") -> None:
        self._audit.log(
            "intake.requirements_extracted",
            f"extracted {count} requirements",
            "intake",
            metadata={"count": count, "preview": preview[:200]},
        )

    def plan_built(self, task_count: int) -> None:
        self._audit.log(
            "intake.plan_built",
            f"built plan with {task_count} tasks",
            "intake",
            metadata={"task_count": task_count},
        )

    def skill_mapped(self, task_id: int, requirement: str, skill_name: str) -> None:
        self._audit.log(
            "intake.skill_mapped",
            f"task {task_id}: {skill_name}",
            "intake",
            metadata={
                "task_id": task_id,
                "requirement": requirement[:100],
                "skill": skill_name,
            },
        )

    def skill_map_failed(self, task_id: int, requirement: str) -> None:
        self._audit.log(
            "intake.skill_map_failed",
            f"task {task_id}: no skill",
            "intake",
            metadata={"task_id": task_id, "requirement": requirement[:100]},
        )

    def task_started(self, task_id: int, skill_name: str) -> None:
        self._audit.log(
            "intake.task_started",
            f"task {task_id}: {skill_name}",
            "intake",
            metadata={"task_id": task_id, "skill": skill_name},
        )

    def task_completed(
        self, task_id: int, skill_name: str, status: str, duration_ms: int = 0
    ) -> None:
        self._audit.log(
            "intake.task_completed",
            f"task {task_id}: {status}",
            "intake",
            metadata={
                "task_id": task_id,
                "skill": skill_name,
                "status": status,
                "duration_ms": duration_ms,
            },
        )

    def session_saved(self, total: int, ok: int, failed: int, execute: bool) -> None:
        self._audit.log(
            "intake.session_saved",
            f"{ok} ok, {failed} failed, {total} total",
            "intake",
            metadata={
                "total": total,
                "ok": ok,
                "failed": failed,
                "execute": execute,
            },
        )

    def notification_sent(self, channel: str, phase: str, success: bool) -> None:
        self._audit.log(
            "intake.notification",
            f"{channel}: {phase} ({'ok' if success else 'failed'})",
            "intake",
            metadata={"channel": channel, "phase": phase, "success": success},
        )
