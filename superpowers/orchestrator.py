"""Orchestration runner — executes named workflow commands with structured output."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from superpowers.workflow.base import StepStatus, WorkflowError
from superpowers.workflow.engine import WorkflowEngine
from superpowers.workflow.loader import WorkflowLoader

# Orchestration commands map to workflow YAML files with this prefix convention.
# Any workflow YAML can be run as an orchestration command.
ORCHESTRATION_COMMANDS: dict[str, str] = {
    "audit": "Security audit — QA checks, dependency scan, secret detection",
    "vulnerability-scan": "Dependency vulnerability check — pip audit, npm audit",
    "compliance-check": "License compliance and policy checks",
    "profile-repo": "Repository profiling — languages, size, deps, test coverage",
    "benchmark": "Performance benchmarks — test speed, build time",
    "deploy-validate": "Pre-deploy validation — tests, lint, health check",
    "health-check": "Service health — ping, port check, HTTP probe",
    "incident-report": "Incident documentation generator",
    "code-health": "Code quality metrics — complexity, duplication, coverage",
    "debt-analysis": "Tech debt analysis — TODOs, deprecated APIs, old deps",
}


@dataclass
class OrchResult:
    """Structured result from an orchestration command run."""

    command: str
    status: str  # "passed", "failed", "error"
    started_at: str = ""
    finished_at: str = ""
    report_path: str = ""
    summary: str = ""
    steps_passed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    total_duration_ms: int = 0
    step_details: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# Orchestration: {self.command}",
            "",
            f"**Status:** {self.status}",
            f"**Started:** {self.started_at}",
            f"**Finished:** {self.finished_at}",
            f"**Duration:** {self.total_duration_ms}ms",
            "",
            "## Steps",
            "",
            f"- Passed: {self.steps_passed}",
            f"- Failed: {self.steps_failed}",
            f"- Skipped: {self.steps_skipped}",
            "",
            "| Step | Status | Duration | Output |",
            "|------|--------|----------|--------|",
        ]
        for step in self.step_details:
            output = (step.get("output") or step.get("error") or "")[:80]
            output = output.replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {step['name']} | {step['status']} "
                f"| {step.get('duration_ms', 0)}ms | {output} |"
            )
        if self.summary:
            lines.extend(["", "## Summary", "", self.summary])
        return "\n".join(lines)


class Orchestrator:
    """Run named orchestration commands backed by workflow YAMLs."""

    def __init__(
        self,
        workflows_dir: Path | None = None,
        output_dir: Path | None = None,
    ):
        self._loader = WorkflowLoader(workflows_dir)
        if output_dir is None:
            from superpowers.config import get_data_dir

            output_dir = get_data_dir() / "orchestrator"
        self._output_dir = output_dir

    def list_commands(self) -> dict[str, str]:
        """Return dict of command_name -> description for available orchestration commands."""
        available = {}
        all_workflows = self._loader.list_workflows()
        for name, desc in ORCHESTRATION_COMMANDS.items():
            if name in all_workflows:
                available[name] = desc
        return available

    def get_command_info(self, name: str) -> dict:
        """Return detailed info about an orchestration command."""
        if name not in ORCHESTRATION_COMMANDS:
            raise WorkflowError(f"Unknown orchestration command: {name}")

        try:
            wf = self._loader.load(name)
        except WorkflowError:
            raise WorkflowError(
                f"Orchestration command '{name}' is registered but workflow YAML not found"
            )

        return {
            "name": name,
            "description": ORCHESTRATION_COMMANDS[name],
            "workflow_name": wf.name,
            "workflow_description": wf.description,
            "steps": [
                {
                    "name": s.name,
                    "type": s.type.value,
                    "command": s.command,
                    "on_failure": s.on_failure,
                    "timeout": s.timeout,
                }
                for s in wf.steps
            ],
            "notify_profile": wf.notify_profile,
            "has_rollback": len(wf.rollback_steps) > 0,
        }

    def run(
        self,
        command: str,
        repo_path: str | None = None,
        dry_run: bool = False,
        **opts,
    ) -> OrchResult:
        """Execute an orchestration command and return a structured result."""
        if command not in ORCHESTRATION_COMMANDS:
            return OrchResult(
                command=command,
                status="error",
                summary=f"Unknown orchestration command: {command}",
            )

        started_at = datetime.now(UTC).isoformat()
        start_mono = time.monotonic()

        try:
            wf = self._loader.load(command)
        except WorkflowError as exc:
            return OrchResult(
                command=command,
                status="error",
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                summary=str(exc),
            )

        # If repo_path is specified, inject it into step args via env
        if repo_path:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(repo_path)
                engine = WorkflowEngine()
                results = engine.run(wf, dry_run=dry_run)
            finally:
                os.chdir(original_cwd)
        else:
            engine = WorkflowEngine()
            results = engine.run(wf, dry_run=dry_run)

        finished_at = datetime.now(UTC).isoformat()
        total_ms = int((time.monotonic() - start_mono) * 1000)

        # Build step details
        step_details = []
        for r in results:
            step_details.append(
                {
                    "name": r.step_name,
                    "status": r.status.value,
                    "output": r.output,
                    "error": r.error,
                    "duration_ms": r.duration_ms,
                }
            )

        passed = sum(1 for r in results if r.status == StepStatus.passed)
        failed = sum(1 for r in results if r.status == StepStatus.failed)
        skipped = sum(1 for r in results if r.status == StepStatus.skipped)

        # Build summary from last claude_prompt step output if available
        summary = ""
        for r in reversed(results):
            if r.step_name == "summarize" and r.output:
                summary = r.output
                break

        overall_status = "passed" if failed == 0 else "failed"

        result = OrchResult(
            command=command,
            status=overall_status,
            started_at=started_at,
            finished_at=finished_at,
            steps_passed=passed,
            steps_failed=failed,
            steps_skipped=skipped,
            total_duration_ms=total_ms,
            step_details=step_details,
            summary=summary,
        )

        # Save report
        report_path = self._save_report(result)
        result.report_path = str(report_path)

        return result

    def _save_report(self, result: OrchResult) -> Path:
        """Save JSON + markdown reports to the output directory."""
        cmd_dir = self._output_dir / result.command
        cmd_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        json_path = cmd_dir / f"{ts}.json"
        md_path = cmd_dir / f"{ts}.md"

        json_path.write_text(result.to_json())
        md_path.write_text(result.to_markdown())

        # Also write a latest symlink / file
        latest_json = cmd_dir / "latest.json"
        latest_md = cmd_dir / "latest.md"
        latest_json.write_text(result.to_json())
        latest_md.write_text(result.to_markdown())

        return json_path
