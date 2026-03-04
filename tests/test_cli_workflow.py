"""Tests for CLI workflow subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_workflow import workflow_group
from superpowers.workflow.base import (
    StepConfig,
    StepResult,
    StepStatus,
    StepType,
    WorkflowConfig,
    WorkflowError,
)


def _make_workflow(name="deploy", description="Deploy the app", steps=None, rollback=None, notify=""):
    if steps is None:
        steps = [
            StepConfig(name="build", type=StepType.shell, command="make build"),
            StepConfig(name="test", type=StepType.shell, command="make test"),
        ]
    return WorkflowConfig(
        name=name,
        description=description,
        steps=steps,
        rollback_steps=rollback or [],
        notify_profile=notify,
    )


def _make_step_results(passed=True):
    status = StepStatus.passed if passed else StepStatus.failed
    return [
        StepResult(step_name="build", status=status, output="ok", duration_ms=120),
        StepResult(step_name="test", status=status, output="ok", duration_ms=300),
    ]


# --- workflow list ---


@patch("superpowers.cli_workflow._loader")
def test_workflow_list_with_workflows(mock_loader_fn):
    loader = MagicMock()
    loader.list_workflows.return_value = ["deploy", "backup"]
    loader.load.side_effect = lambda n: _make_workflow(name=n, description=f"{n} workflow")
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["list"])
    assert result.exit_code == 0
    assert "deploy" in result.output
    assert "backup" in result.output


@patch("superpowers.cli_workflow._loader")
def test_workflow_list_empty(mock_loader_fn):
    loader = MagicMock()
    loader.list_workflows.return_value = []
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["list"])
    assert result.exit_code == 0
    assert "No workflows found" in result.output


@patch("superpowers.cli_workflow._loader")
def test_workflow_list_load_error(mock_loader_fn):
    loader = MagicMock()
    loader.list_workflows.return_value = ["broken"]
    loader.load.side_effect = WorkflowError("invalid yaml")
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["list"])
    assert result.exit_code == 0
    assert "error loading" in result.output


# --- workflow show ---


@patch("superpowers.cli_workflow._loader")
def test_workflow_show_happy(mock_loader_fn):
    wf = _make_workflow(notify="critical")
    loader = MagicMock()
    loader.load.return_value = wf
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["show", "deploy"])
    assert result.exit_code == 0
    assert "deploy" in result.output
    assert "build" in result.output
    assert "test" in result.output
    assert "critical" in result.output


@patch("superpowers.cli_workflow._loader")
def test_workflow_show_with_rollback(mock_loader_fn):
    rollback = [StepConfig(name="rollback-deploy", type=StepType.shell, command="git revert HEAD")]
    wf = _make_workflow(rollback=rollback)
    loader = MagicMock()
    loader.load.return_value = wf
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["show", "deploy"])
    assert result.exit_code == 0
    assert "Rollback" in result.output
    assert "rollback-deploy" in result.output


@patch("superpowers.cli_workflow._loader")
def test_workflow_show_not_found(mock_loader_fn):
    loader = MagicMock()
    loader.load.side_effect = WorkflowError("workflow 'x' not found")
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["show", "x"])
    assert result.exit_code != 0
    assert "not found" in result.output


# --- workflow run ---


@patch("superpowers.cli_workflow.WorkflowEngine")
@patch("superpowers.cli_workflow._loader")
def test_workflow_run_all_pass(mock_loader_fn, mock_engine_cls):
    loader = MagicMock()
    loader.load.return_value = _make_workflow()
    mock_loader_fn.return_value = loader

    engine = MagicMock()
    engine.run.return_value = _make_step_results(passed=True)
    mock_engine_cls.return_value = engine

    runner = CliRunner()
    result = runner.invoke(workflow_group, ["run", "deploy"])
    assert result.exit_code == 0
    assert "All 2 steps passed" in result.output


@patch("superpowers.cli_workflow.WorkflowEngine")
@patch("superpowers.cli_workflow._loader")
def test_workflow_run_with_failure(mock_loader_fn, mock_engine_cls):
    loader = MagicMock()
    loader.load.return_value = _make_workflow()
    mock_loader_fn.return_value = loader

    engine = MagicMock()
    results = [
        StepResult(step_name="build", status=StepStatus.passed, output="ok", duration_ms=100),
        StepResult(step_name="test", status=StepStatus.failed, error="assertion error", duration_ms=200),
    ]
    engine.run.return_value = results
    mock_engine_cls.return_value = engine

    runner = CliRunner()
    result = runner.invoke(workflow_group, ["run", "deploy"])
    assert result.exit_code != 0
    assert "1 failed" in result.output


@patch("superpowers.cli_workflow.WorkflowEngine")
@patch("superpowers.cli_workflow._loader")
def test_workflow_run_dry_run(mock_loader_fn, mock_engine_cls):
    loader = MagicMock()
    loader.load.return_value = _make_workflow()
    mock_loader_fn.return_value = loader

    engine = MagicMock()
    engine.run.return_value = _make_step_results(passed=True)
    mock_engine_cls.return_value = engine

    runner = CliRunner()
    result = runner.invoke(workflow_group, ["run", "deploy", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    engine.run.assert_called_once()
    call_kwargs = engine.run.call_args
    assert call_kwargs[1]["dry_run"] is True or call_kwargs[0][1] is True


@patch("superpowers.cli_workflow._loader")
def test_workflow_run_load_error(mock_loader_fn):
    loader = MagicMock()
    loader.load.side_effect = WorkflowError("missing file")
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["run", "broken"])
    assert result.exit_code != 0
    assert "missing file" in result.output


# --- workflow validate ---


@patch("superpowers.cli_workflow._loader")
def test_workflow_validate_ok(mock_loader_fn):
    loader = MagicMock()
    loader.load.return_value = _make_workflow()
    loader.validate.return_value = []
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["validate", "deploy"])
    assert result.exit_code == 0
    assert "is valid" in result.output


@patch("superpowers.cli_workflow._loader")
def test_workflow_validate_errors(mock_loader_fn):
    loader = MagicMock()
    loader.load.return_value = _make_workflow()
    loader.validate.return_value = ["step 'x' has no command", "unknown step type"]
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["validate", "deploy"])
    assert result.exit_code != 0
    assert "step 'x' has no command" in result.output


@patch("superpowers.cli_workflow._loader")
def test_workflow_validate_load_error(mock_loader_fn):
    loader = MagicMock()
    loader.load.side_effect = WorkflowError("bad yaml")
    mock_loader_fn.return_value = loader
    runner = CliRunner()
    result = runner.invoke(workflow_group, ["validate", "broken"])
    assert result.exit_code != 0
    assert "bad yaml" in result.output


# --- workflow init ---


@patch("superpowers.cli_workflow.install_builtins")
@patch("superpowers.cli_workflow.get_data_dir", create=True)
def test_workflow_init_created(mock_data_dir, mock_install):
    mock_data_dir.return_value = MagicMock(__truediv__=MagicMock(return_value="/tmp/workflows"))
    mock_install.return_value = ["deploy", "backup", "morning-brief"]
    runner = CliRunner()
    with patch("superpowers.config.get_data_dir", mock_data_dir):
        result = runner.invoke(workflow_group, ["init"])
    assert result.exit_code == 0
    assert "deploy" in result.output
    assert "backup" in result.output


@patch("superpowers.cli_workflow.install_builtins")
@patch("superpowers.cli_workflow.get_data_dir", create=True)
def test_workflow_init_already_exists(mock_data_dir, mock_install):
    mock_data_dir.return_value = MagicMock(__truediv__=MagicMock(return_value="/tmp/workflows"))
    mock_install.return_value = []
    runner = CliRunner()
    with patch("superpowers.config.get_data_dir", mock_data_dir):
        result = runner.invoke(workflow_group, ["init"])
    assert result.exit_code == 0
    assert "already exist" in result.output
