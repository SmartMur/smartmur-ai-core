"""Tests for the orchestration runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from superpowers.orchestrator import ORCHESTRATION_COMMANDS, Orchestrator, OrchResult
from superpowers.workflow.base import WorkflowError

# ---------- fixtures ----------


@pytest.fixture
def workflows_dir(tmp_path):
    """Create a temp dir with a minimal orchestration workflow."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    return wf_dir


@pytest.fixture
def output_dir(tmp_path):
    return tmp_path / "output"


def _write_workflow(wf_dir: Path, name: str, content: str | None = None):
    """Write a workflow YAML to the dir."""
    if content is None:
        content = f"""\
name: {name}
description: "Test {name} workflow"
steps:
  - name: step1
    type: shell
    command: "echo {name}-ok"
    on_failure: continue
"""
    (wf_dir / f"{name}.yaml").write_text(content)


# ---------- OrchResult ----------


class TestOrchResult:
    def test_defaults(self):
        r = OrchResult(command="audit", status="passed")
        assert r.command == "audit"
        assert r.status == "passed"
        assert r.started_at == ""
        assert r.finished_at == ""
        assert r.report_path == ""
        assert r.summary == ""
        assert r.steps_passed == 0
        assert r.steps_failed == 0
        assert r.steps_skipped == 0
        assert r.total_duration_ms == 0
        assert r.step_details == []

    def test_to_dict(self):
        r = OrchResult(command="audit", status="passed", steps_passed=3)
        d = r.to_dict()
        assert d["command"] == "audit"
        assert d["status"] == "passed"
        assert d["steps_passed"] == 3

    def test_to_json(self):
        r = OrchResult(command="audit", status="passed")
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["command"] == "audit"

    def test_to_markdown(self):
        r = OrchResult(
            command="health-check",
            status="passed",
            started_at="2026-03-03T00:00:00Z",
            finished_at="2026-03-03T00:00:05Z",
            total_duration_ms=5000,
            steps_passed=2,
            steps_failed=1,
            step_details=[
                {"name": "step1", "status": "passed", "output": "ok", "duration_ms": 100},
                {"name": "step2", "status": "failed", "error": "boom", "duration_ms": 200},
            ],
            summary="All good",
        )
        md = r.to_markdown()
        assert "# Orchestration: health-check" in md
        assert "Passed: 2" in md
        assert "Failed: 1" in md
        assert "All good" in md
        assert "step1" in md
        assert "step2" in md

    def test_to_markdown_no_summary(self):
        r = OrchResult(command="audit", status="passed")
        md = r.to_markdown()
        assert "## Summary" not in md

    def test_to_markdown_pipe_in_output(self):
        r = OrchResult(
            command="audit",
            status="passed",
            step_details=[
                {"name": "s1", "status": "passed", "output": "has|pipe", "duration_ms": 0},
            ],
        )
        md = r.to_markdown()
        assert "has\\|pipe" in md


# ---------- Orchestrator.list_commands ----------


class TestListCommands:
    def test_empty_dir(self, workflows_dir, output_dir):
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.list_commands()
        assert result == {}

    def test_with_matching_workflow(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.list_commands()
        assert "audit" in result
        assert "Security audit" in result["audit"]

    def test_non_orchestration_workflow_excluded(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "my-custom-thing")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.list_commands()
        assert "my-custom-thing" not in result

    def test_multiple_commands(self, workflows_dir, output_dir):
        for name in ["audit", "health-check", "benchmark"]:
            _write_workflow(workflows_dir, name)
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.list_commands()
        assert len(result) == 3
        assert "audit" in result
        assert "health-check" in result
        assert "benchmark" in result


# ---------- Orchestrator.get_command_info ----------


class TestGetCommandInfo:
    def test_valid_command(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        info = orch.get_command_info("audit")
        assert info["name"] == "audit"
        assert info["description"] == ORCHESTRATION_COMMANDS["audit"]
        assert len(info["steps"]) > 0
        assert "workflow_name" in info
        assert "has_rollback" in info

    def test_unknown_command(self, workflows_dir, output_dir):
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        with pytest.raises(WorkflowError, match="Unknown orchestration command"):
            orch.get_command_info("totally-fake")

    def test_registered_but_missing_workflow(self, workflows_dir, output_dir):
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        with pytest.raises(WorkflowError, match="workflow YAML not found"):
            orch.get_command_info("audit")

    def test_info_steps_structure(self, workflows_dir, output_dir):
        content = """\
name: audit
description: "Test audit"
steps:
  - name: check1
    type: shell
    command: "echo hi"
    on_failure: continue
    timeout: 60
  - name: check2
    type: shell
    command: "echo bye"
    on_failure: abort
"""
        _write_workflow(workflows_dir, "audit", content)
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        info = orch.get_command_info("audit")
        assert len(info["steps"]) == 2
        assert info["steps"][0]["name"] == "check1"
        assert info["steps"][0]["type"] == "shell"
        assert info["steps"][0]["on_failure"] == "continue"
        assert info["steps"][0]["timeout"] == 60
        assert info["steps"][1]["on_failure"] == "abort"

    def test_info_with_rollback(self, workflows_dir, output_dir):
        content = """\
name: deploy-validate
description: "deploy validate"
steps:
  - name: test
    type: shell
    command: "echo ok"
    on_failure: rollback
rollback:
  - name: undo
    type: shell
    command: "echo rollback"
"""
        _write_workflow(workflows_dir, "deploy-validate", content)
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        info = orch.get_command_info("deploy-validate")
        assert info["has_rollback"] is True


# ---------- Orchestrator.run ----------


class TestRun:
    def test_unknown_command(self, workflows_dir, output_dir):
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("not-a-command")
        assert result.status == "error"
        assert "Unknown" in result.summary

    def test_missing_workflow(self, workflows_dir, output_dir):
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("audit")
        assert result.status == "error"
        assert result.command == "audit"

    def test_successful_run(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("audit")
        assert result.status == "passed"
        assert result.steps_passed == 1
        assert result.steps_failed == 0
        assert result.total_duration_ms >= 0
        assert result.started_at != ""
        assert result.finished_at != ""

    def test_run_saves_report(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("audit")
        assert result.report_path != ""
        report_path = Path(result.report_path)
        assert report_path.is_file()
        # Check JSON is valid
        data = json.loads(report_path.read_text())
        assert data["command"] == "audit"

    def test_run_saves_latest(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        orch.run("audit")
        latest = output_dir / "audit" / "latest.json"
        assert latest.is_file()
        latest_md = output_dir / "audit" / "latest.md"
        assert latest_md.is_file()

    def test_run_with_failure(self, workflows_dir, output_dir):
        content = """\
name: audit
description: "fail test"
steps:
  - name: fail-step
    type: shell
    command: "exit 1"
    on_failure: continue
  - name: pass-step
    type: shell
    command: "echo ok"
    on_failure: continue
"""
        _write_workflow(workflows_dir, "audit", content)
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("audit")
        assert result.status == "failed"
        assert result.steps_passed == 1
        assert result.steps_failed == 1

    def test_dry_run(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("audit", dry_run=True)
        assert result.status == "passed"
        assert "dry-run" in result.step_details[0].get("output", "")

    def test_run_with_repo_path(self, workflows_dir, output_dir, tmp_path):
        _write_workflow(workflows_dir, "profile-repo")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("profile-repo", repo_path=str(tmp_path))
        assert result.command == "profile-repo"
        assert result.status == "passed"

    def test_step_details_populated(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("audit")
        assert len(result.step_details) == 1
        assert result.step_details[0]["name"] == "step1"
        assert result.step_details[0]["status"] == "passed"
        assert "audit-ok" in result.step_details[0]["output"]

    def test_summary_from_summarize_step(self, workflows_dir, output_dir):
        content = """\
name: audit
description: "with summary"
steps:
  - name: check
    type: shell
    command: "echo data"
    on_failure: continue
  - name: summarize
    type: shell
    command: "echo 'Summary: all clear'"
    on_failure: continue
"""
        _write_workflow(workflows_dir, "audit", content)
        orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
        result = orch.run("audit")
        assert "all clear" in result.summary


# ---------- CLI ----------


class TestCLI:
    def _runner(self):
        return CliRunner()

    def test_orchestrate_list(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")
        _write_workflow(workflows_dir, "health-check")

        from superpowers.cli_orchestrate import orchestrate_group

        runner = self._runner()

        with patch("superpowers.cli_orchestrate._orchestrator") as mock_orch_fn:
            orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
            mock_orch_fn.return_value = orch
            result = runner.invoke(orchestrate_group, ["list"])

        assert result.exit_code == 0
        assert "audit" in result.output

    def test_orchestrate_list_empty(self, workflows_dir, output_dir):
        from superpowers.cli_orchestrate import orchestrate_group

        runner = self._runner()

        with patch("superpowers.cli_orchestrate._orchestrator") as mock_orch_fn:
            orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
            mock_orch_fn.return_value = orch
            result = runner.invoke(orchestrate_group, ["list"])

        assert result.exit_code == 0
        assert "No orchestration commands" in result.output or "missing" in result.output

    def test_orchestrate_info(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")

        from superpowers.cli_orchestrate import orchestrate_group

        runner = self._runner()

        with patch("superpowers.cli_orchestrate._orchestrator") as mock_orch_fn:
            orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
            mock_orch_fn.return_value = orch
            result = runner.invoke(orchestrate_group, ["info", "audit"])

        assert result.exit_code == 0
        assert "audit" in result.output
        assert "step1" in result.output

    def test_orchestrate_info_unknown(self, workflows_dir, output_dir):
        from superpowers.cli_orchestrate import orchestrate_group

        runner = self._runner()

        with patch("superpowers.cli_orchestrate._orchestrator") as mock_orch_fn:
            orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
            mock_orch_fn.return_value = orch
            result = runner.invoke(orchestrate_group, ["info", "no-such-command"])

        assert result.exit_code == 1

    def test_orchestrate_run_success(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")

        from superpowers.cli_orchestrate import orchestrate_group

        runner = self._runner()

        with patch("superpowers.cli_orchestrate._orchestrator") as mock_orch_fn:
            orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
            mock_orch_fn.return_value = orch
            # Need to also patch the Orchestrator used in orchestrate_run
            # since it creates its own instance when --output is not provided
            with patch(
                "superpowers.cli_orchestrate.Orchestrator", return_value=orch
            ):
                result = runner.invoke(orchestrate_group, ["run", "audit"])

        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_orchestrate_run_dry(self, workflows_dir, output_dir):
        _write_workflow(workflows_dir, "audit")

        from superpowers.cli_orchestrate import orchestrate_group

        runner = self._runner()

        with patch("superpowers.cli_orchestrate.Orchestrator") as mock_orch_cls:
            orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
            mock_orch_cls.return_value = orch
            result = runner.invoke(orchestrate_group, ["run", "audit", "--dry-run"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    def test_orchestrate_run_failure_exit_code(self, workflows_dir, output_dir):
        content = """\
name: audit
description: "fail"
steps:
  - name: boom
    type: shell
    command: "exit 1"
    on_failure: continue
"""
        _write_workflow(workflows_dir, "audit", content)

        from superpowers.cli_orchestrate import orchestrate_group

        runner = self._runner()

        with patch("superpowers.cli_orchestrate.Orchestrator") as mock_orch_cls:
            orch = Orchestrator(workflows_dir=workflows_dir, output_dir=output_dir)
            mock_orch_cls.return_value = orch
            result = runner.invoke(orchestrate_group, ["run", "audit"])

        assert result.exit_code == 1


# ---------- Workflow YAML validation ----------


class TestWorkflowYAMLs:
    """Verify all 10 orchestration workflow YAMLs are loadable and valid."""

    @pytest.fixture
    def real_workflows_dir(self):
        return Path(__file__).parent.parent / "workflows"

    @pytest.mark.parametrize(
        "name",
        [
            "audit",
            "vulnerability-scan",
            "compliance-check",
            "profile-repo",
            "benchmark",
            "deploy-validate",
            "health-check",
            "incident-report",
            "code-health",
            "debt-analysis",
        ],
    )
    def test_workflow_loadable(self, real_workflows_dir, name):
        from superpowers.workflow.loader import WorkflowLoader

        loader = WorkflowLoader(real_workflows_dir)
        wf = loader.load(name)
        assert wf.name == name
        assert len(wf.steps) >= 3

    @pytest.mark.parametrize(
        "name",
        list(ORCHESTRATION_COMMANDS.keys()),
    )
    def test_workflow_valid(self, real_workflows_dir, name):
        from superpowers.workflow.loader import WorkflowLoader

        loader = WorkflowLoader(real_workflows_dir)
        wf = loader.load(name)
        errors = loader.validate(wf)
        assert errors == [], f"Validation errors for {name}: {errors}"

    @pytest.mark.parametrize(
        "name",
        list(ORCHESTRATION_COMMANDS.keys()),
    )
    def test_workflow_in_registry(self, name):
        assert name in ORCHESTRATION_COMMANDS
