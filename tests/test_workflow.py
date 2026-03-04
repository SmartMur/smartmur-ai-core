"""Tests for the workflow engine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from superpowers.workflow.base import (
    StepConfig,
    StepResult,
    StepStatus,
    StepType,
    WorkflowConfig,
    WorkflowError,
)
from superpowers.workflow.builtins import install_builtins
from superpowers.workflow.engine import WorkflowEngine
from superpowers.workflow.loader import WorkflowLoader

# --- Base types ---


class TestStepType:
    def test_values(self):
        assert StepType.shell == "shell"
        assert StepType.claude_prompt == "claude_prompt"
        assert StepType.skill == "skill"
        assert StepType.http == "http"
        assert StepType.approval_gate == "approval_gate"
        assert StepType.auto_agent == "auto_agent"

    def test_count(self):
        assert len(StepType) == 6


class TestStepStatus:
    def test_values(self):
        assert StepStatus.pending == "pending"
        assert StepStatus.passed == "passed"
        assert StepStatus.failed == "failed"
        assert StepStatus.skipped == "skipped"


class TestStepResult:
    def test_defaults(self):
        r = StepResult(step_name="test", status=StepStatus.passed)
        assert r.output == ""
        assert r.error == ""
        assert r.duration_ms == 0


class TestStepConfig:
    def test_defaults(self):
        s = StepConfig(name="test", type=StepType.shell, command="echo hi")
        assert s.on_failure == "abort"
        assert s.timeout == 300
        assert s.condition == ""
        assert s.args == {}


class TestWorkflowConfig:
    def test_defaults(self):
        wf = WorkflowConfig(name="test")
        assert wf.steps == []
        assert wf.rollback_steps == []
        assert wf.notify_profile == ""
        assert wf.description == ""


# --- Loader ---


class TestWorkflowLoader:
    def test_load_valid(self, tmp_path):
        wf_file = tmp_path / "test.yaml"
        wf_file.write_text("""
name: test-workflow
description: A test
steps:
  - name: step1
    type: shell
    command: "echo hello"
  - name: step2
    type: http
    command: "http://example.com"
    on_failure: continue
""")
        loader = WorkflowLoader(tmp_path)
        wf = loader.load("test")
        assert wf.name == "test-workflow"
        assert len(wf.steps) == 2
        assert wf.steps[0].type == StepType.shell
        assert wf.steps[1].on_failure == "continue"

    def test_load_missing(self, tmp_path):
        loader = WorkflowLoader(tmp_path)
        with pytest.raises(WorkflowError, match="not found"):
            loader.load("nonexistent")

    def test_load_invalid_yaml(self, tmp_path):
        wf_file = tmp_path / "bad.yaml"
        wf_file.write_text("{{{{not yaml")
        loader = WorkflowLoader(tmp_path)
        with pytest.raises(WorkflowError, match="Invalid YAML"):
            loader.load("bad")

    def test_list_workflows(self, tmp_path):
        (tmp_path / "a.yaml").write_text("name: a\nsteps: []")
        (tmp_path / "b.yaml").write_text("name: b\nsteps: []")
        (tmp_path / "readme.md").write_text("not a workflow")
        loader = WorkflowLoader(tmp_path)
        assert loader.list_workflows() == ["a", "b"]

    def test_list_empty_dir(self, tmp_path):
        loader = WorkflowLoader(tmp_path)
        assert loader.list_workflows() == []

    def test_list_missing_dir(self, tmp_path):
        loader = WorkflowLoader(tmp_path / "nonexistent")
        assert loader.list_workflows() == []

    def test_validate_valid(self, tmp_path):
        wf = WorkflowConfig(
            name="test",
            steps=[StepConfig(name="s1", type=StepType.shell, command="echo ok")],
        )
        loader = WorkflowLoader(tmp_path)
        assert loader.validate(wf) == []

    def test_validate_no_name(self, tmp_path):
        wf = WorkflowConfig(
            name="",
            steps=[StepConfig(name="s1", type=StepType.shell, command="echo ok")],
        )
        loader = WorkflowLoader(tmp_path)
        errors = loader.validate(wf)
        assert any("name is required" in e for e in errors)

    def test_validate_no_steps(self, tmp_path):
        wf = WorkflowConfig(name="test", steps=[])
        loader = WorkflowLoader(tmp_path)
        errors = loader.validate(wf)
        assert any("at least one step" in e for e in errors)

    def test_validate_step_missing_command(self, tmp_path):
        wf = WorkflowConfig(
            name="test",
            steps=[StepConfig(name="s1", type=StepType.shell, command="")],
        )
        loader = WorkflowLoader(tmp_path)
        errors = loader.validate(wf)
        assert any("missing command" in e for e in errors)

    def test_load_with_rollback(self, tmp_path):
        wf_file = tmp_path / "rollback.yaml"
        wf_file.write_text("""
name: rollback-test
steps:
  - name: deploy
    type: shell
    command: "deploy.sh"
    on_failure: rollback
rollback:
  - name: undo
    type: shell
    command: "rollback.sh"
""")
        loader = WorkflowLoader(tmp_path)
        wf = loader.load("rollback")
        assert len(wf.rollback_steps) == 1
        assert wf.rollback_steps[0].name == "undo"


# --- Engine ---


class TestWorkflowEngine:
    def _shell_wf(self, *commands, on_failure="abort"):
        steps = [
            StepConfig(name=f"step{i}", type=StepType.shell, command=cmd, on_failure=on_failure)
            for i, cmd in enumerate(commands)
        ]
        return WorkflowConfig(name="test", steps=steps)

    def test_shell_success(self):
        engine = WorkflowEngine()
        wf = self._shell_wf("echo hello")
        results = engine.run(wf)
        assert len(results) == 1
        assert results[0].status == StepStatus.passed
        assert "hello" in results[0].output

    def test_shell_failure_aborts(self):
        engine = WorkflowEngine()
        wf = self._shell_wf("exit 1", "echo never")
        results = engine.run(wf)
        assert results[0].status == StepStatus.failed
        # abort stops immediately — second step never runs
        assert len(results) == 1

    def test_shell_failure_continue(self):
        engine = WorkflowEngine()
        wf = self._shell_wf("exit 1", "echo still-runs", on_failure="continue")
        results = engine.run(wf)
        assert results[0].status == StepStatus.failed
        assert results[1].status == StepStatus.passed

    def test_dry_run(self):
        engine = WorkflowEngine()
        wf = self._shell_wf("rm -rf /")
        results = engine.run(wf, dry_run=True)
        assert results[0].status == StepStatus.passed
        assert "dry-run" in results[0].output

    def test_condition_previous_ok(self):
        engine = WorkflowEngine()
        steps = [
            StepConfig(name="first", type=StepType.shell, command="echo ok"),
            StepConfig(
                name="conditional",
                type=StepType.shell,
                command="echo yep",
                condition="previous.ok",
            ),
        ]
        wf = WorkflowConfig(name="test", steps=steps)
        results = engine.run(wf)
        assert results[1].status == StepStatus.passed

    def test_condition_previous_ok_skips_on_failure(self):
        engine = WorkflowEngine()
        steps = [
            StepConfig(name="first", type=StepType.shell, command="exit 1", on_failure="continue"),
            StepConfig(
                name="conditional",
                type=StepType.shell,
                command="echo nope",
                condition="previous.ok",
            ),
        ]
        wf = WorkflowConfig(name="test", steps=steps)
        results = engine.run(wf)
        assert results[1].status == StepStatus.skipped

    def test_rollback_on_failure(self):
        engine = WorkflowEngine()
        wf = WorkflowConfig(
            name="test",
            steps=[
                StepConfig(
                    name="fail", type=StepType.shell, command="exit 1", on_failure="rollback"
                ),
            ],
            rollback_steps=[
                StepConfig(name="undo", type=StepType.shell, command="echo rolled-back"),
            ],
        )
        results = engine.run(wf)
        assert results[0].status == StepStatus.failed
        assert any("rollback:" in r.step_name for r in results)

    def test_http_step(self, monkeypatch):
        engine = WorkflowEngine()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        wf = WorkflowConfig(
            name="test",
            steps=[StepConfig(name="http", type=StepType.http, command="http://example.com")],
        )
        results = engine.run(wf)
        assert results[0].status == StepStatus.passed

    def test_approval_gate_dry_run(self):
        engine = WorkflowEngine()
        wf = WorkflowConfig(
            name="test",
            steps=[StepConfig(name="gate", type=StepType.approval_gate, command="")],
        )
        results = engine.run(wf, dry_run=True)
        assert results[0].status == StepStatus.passed
        assert "auto-approved" in results[0].output

    def test_duration_tracked(self):
        engine = WorkflowEngine()
        wf = self._shell_wf("echo fast")
        results = engine.run(wf)
        assert results[0].duration_ms >= 0

    def test_multiple_steps_all_pass(self):
        engine = WorkflowEngine()
        wf = self._shell_wf("echo a", "echo b", "echo c")
        results = engine.run(wf)
        assert len(results) == 3
        assert all(r.status == StepStatus.passed for r in results)


# --- Builtins ---


class TestBuiltins:
    def test_install_creates_files(self, tmp_path):
        created = install_builtins(tmp_path)
        assert "deploy" in created
        assert "backup" in created
        assert "morning-brief" in created
        assert (tmp_path / "deploy.yaml").is_file()

    def test_install_idempotent(self, tmp_path):
        install_builtins(tmp_path)
        created = install_builtins(tmp_path)
        assert created == []

    def test_builtins_are_loadable(self, tmp_path):
        install_builtins(tmp_path)
        loader = WorkflowLoader(tmp_path)
        for name in ["deploy", "backup", "morning-brief"]:
            wf = loader.load(name)
            assert wf.name == name
            assert len(wf.steps) > 0
