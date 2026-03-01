"""Tests for the morning-brief workflow: load, execute with mocks, verify ordering and notification."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from superpowers.workflow.base import StepConfig, StepResult, StepStatus, StepType, WorkflowConfig
from superpowers.workflow.engine import WorkflowEngine
from superpowers.workflow.loader import WorkflowLoader


REPO_WORKFLOWS = Path(__file__).resolve().parent.parent / "workflows"


class TestMorningBriefLoad:
    """Verify the YAML loads correctly and has the expected structure."""

    def test_loads_from_repo(self):
        loader = WorkflowLoader(REPO_WORKFLOWS)
        wf = loader.load("morning-brief")
        assert wf.name == "morning-brief"
        assert wf.description == "Check services, summarize alerts, send digest"

    def test_has_three_steps(self):
        loader = WorkflowLoader(REPO_WORKFLOWS)
        wf = loader.load("morning-brief")
        assert len(wf.steps) == 3

    def test_step_types(self):
        loader = WorkflowLoader(REPO_WORKFLOWS)
        wf = loader.load("morning-brief")
        assert wf.steps[0].type == StepType.skill
        assert wf.steps[1].type == StepType.claude_prompt
        assert wf.steps[2].type == StepType.shell

    def test_step_names(self):
        loader = WorkflowLoader(REPO_WORKFLOWS)
        wf = loader.load("morning-brief")
        assert [s.name for s in wf.steps] == ["health-check", "summarize", "send-digest"]

    def test_all_steps_continue_on_failure(self):
        loader = WorkflowLoader(REPO_WORKFLOWS)
        wf = loader.load("morning-brief")
        for step in wf.steps:
            assert step.on_failure == "continue", f"Step '{step.name}' should continue on failure"

    def test_has_notify_profile(self):
        loader = WorkflowLoader(REPO_WORKFLOWS)
        wf = loader.load("morning-brief")
        assert wf.notify_profile == "info"

    def test_validates_clean(self):
        loader = WorkflowLoader(REPO_WORKFLOWS)
        wf = loader.load("morning-brief")
        errors = loader.validate(wf)
        assert errors == [], f"Validation errors: {errors}"


class TestMorningBriefExecution:
    """Execute morning-brief with mocked step handlers, verify ordering and notification."""

    @pytest.fixture()
    def wf(self):
        loader = WorkflowLoader(REPO_WORKFLOWS)
        return loader.load("morning-brief")

    @pytest.fixture()
    def engine(self):
        return WorkflowEngine()

    @pytest.fixture()
    def call_log(self):
        return []

    def _fake_skill(self, step, call_log):
        call_log.append(("skill", step.name, step.command))
        return "HOST           STATUS\nproxmox        UP\ntruenas        UP\nhomeassistant  DOWN", True

    def _fake_claude(self, step, call_log):
        call_log.append(("claude_prompt", step.name, step.command))
        return (
            "- Proxmox: healthy\n- TrueNAS: healthy\n- Home Assistant: unreachable"
        ), True

    def _fake_shell(self, step, call_log):
        call_log.append(("shell", step.name, step.command))
        return "Morning brief complete", True

    def test_all_steps_execute_in_order(self, wf, engine, call_log):
        def mock_execute(step, dry_run=False):
            if step.type == StepType.skill:
                output, ok = self._fake_skill(step, call_log)
            elif step.type == StepType.claude_prompt:
                output, ok = self._fake_claude(step, call_log)
            elif step.type == StepType.shell:
                output, ok = self._fake_shell(step, call_log)
            else:
                output, ok = "", False

            return StepResult(
                step_name=step.name,
                status=StepStatus.passed if ok else StepStatus.failed,
                output=output,
                duration_ms=10,
            )

        with patch.object(engine, "_execute_step", side_effect=mock_execute), \
             patch.object(engine, "_notify"):
            results = engine.run(wf)

        assert len(results) == 3
        assert all(r.status == StepStatus.passed for r in results)
        assert [c[1] for c in call_log] == ["health-check", "summarize", "send-digest"]

    def test_step_types_match_expected(self, wf, engine, call_log):
        def mock_execute(step, dry_run=False):
            call_log.append(step.type.value)
            return StepResult(
                step_name=step.name, status=StepStatus.passed,
                output="ok", duration_ms=5,
            )

        with patch.object(engine, "_execute_step", side_effect=mock_execute), \
             patch.object(engine, "_notify"):
            engine.run(wf)

        assert call_log == ["skill", "claude_prompt", "shell"]

    def test_continues_after_skill_failure(self, wf, engine, call_log):
        def mock_execute(step, dry_run=False):
            call_log.append(step.name)
            if step.name == "health-check":
                return StepResult(
                    step_name=step.name, status=StepStatus.failed,
                    error="skill not found", duration_ms=5,
                )
            return StepResult(
                step_name=step.name, status=StepStatus.passed,
                output="ok", duration_ms=5,
            )

        with patch.object(engine, "_execute_step", side_effect=mock_execute), \
             patch.object(engine, "_notify"):
            results = engine.run(wf)

        # All 3 steps ran despite the first failing (on_failure: continue)
        assert len(results) == 3
        assert call_log == ["health-check", "summarize", "send-digest"]
        assert results[0].status == StepStatus.failed
        assert results[1].status == StepStatus.passed
        assert results[2].status == StepStatus.passed

    def test_notify_called_with_info_profile(self, wf, engine):
        def mock_execute(step, dry_run=False):
            return StepResult(
                step_name=step.name, status=StepStatus.passed,
                output="ok", duration_ms=5,
            )

        with patch.object(engine, "_execute_step", side_effect=mock_execute), \
             patch.object(engine, "_notify") as mock_notify:
            engine.run(wf)

        mock_notify.assert_called_once()
        config_arg, results_arg = mock_notify.call_args[0]
        assert config_arg.notify_profile == "info"
        assert len(results_arg) == 3

    def test_notify_not_called_on_dry_run(self, wf, engine):
        with patch.object(engine, "_notify") as mock_notify:
            engine.run(wf, dry_run=True)

        mock_notify.assert_not_called()

    def test_dry_run_does_not_execute_real_steps(self, wf, engine):
        results = engine.run(wf, dry_run=True)
        assert len(results) == 3
        assert all(r.status == StepStatus.passed for r in results)
        assert all("dry-run" in r.output for r in results)


class TestMorningBriefCronIntegration:
    """Verify morning-brief can be registered as a cron job type."""

    def test_workflow_cron_job_type_shell(self):
        """A cron job can run the workflow via 'claw workflow run morning-brief'."""
        from superpowers.cron_engine import Job, JobType

        job = Job(
            id="mb-001",
            name="morning-brief-cron",
            schedule="daily at 07:00",
            job_type=JobType.shell,
            command="claw workflow run morning-brief",
            output_channel="info",
        )
        assert job.job_type == JobType.shell
        assert job.name == "morning-brief-cron"
        assert "morning-brief" in job.command
        assert job.output_channel == "info"

    def test_schedule_parses(self):
        """The 'daily at 07:00' schedule expression is valid."""
        from superpowers.cron_engine import parse_schedule

        trigger = parse_schedule("daily at 07:00")
        assert trigger is not None
