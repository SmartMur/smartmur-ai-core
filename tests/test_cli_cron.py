"""Tests for CLI cron subcommands."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_cron import cron_group


@dataclass
class FakeJob:
    id: str = "abc12345-6789"
    name: str = "test-job"
    schedule: str = "every 5m"
    command: str = "echo hello"
    enabled: bool = True
    last_run: str = "2026-01-01T00:00:00"
    last_status: str = "ok"
    last_output_file: str = ""

    @property
    def job_type(self):
        return type("JT", (), {"value": "shell"})()


def _make_engine(jobs=None):
    engine = MagicMock()
    _jobs = jobs if jobs is not None else [FakeJob()]
    engine.list_jobs.return_value = _jobs
    engine.get_job.side_effect = lambda jid: next(
        (j for j in _jobs if j.id == jid), None
    )
    engine.add_job.return_value = FakeJob()
    engine.remove_job.return_value = None
    engine.enable_job.return_value = None
    engine.disable_job.return_value = None
    engine.run_job.return_value = None
    return engine


# --- cron list ---


@patch("superpowers.cli_cron._engine")
def test_cron_list_with_jobs(mock_engine_fn):
    mock_engine_fn.return_value = _make_engine()
    runner = CliRunner()
    result = runner.invoke(cron_group, ["list"])
    assert result.exit_code == 0
    # Rich may truncate "test-job" in narrow terminals, check prefix
    assert "test-j" in result.output
    assert "every" in result.output
    assert "shell" in result.output


@patch("superpowers.cli_cron._engine")
def test_cron_list_empty(mock_engine_fn):
    mock_engine_fn.return_value = _make_engine(jobs=[])
    runner = CliRunner()
    result = runner.invoke(cron_group, ["list"])
    assert result.exit_code == 0
    assert "No jobs configured" in result.output


# --- cron add ---


@patch("superpowers.cli_cron._engine")
def test_cron_add_happy(mock_engine_fn):
    engine = _make_engine()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["add", "my-job", "every 10m", "echo hi"])
    assert result.exit_code == 0
    assert "Added job" in result.output
    engine.add_job.assert_called_once()


@patch("superpowers.cli_cron._engine")
def test_cron_add_with_options(mock_engine_fn):
    engine = _make_engine()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(
        cron_group,
        ["add", "my-skill", "daily at 09:00", "skill:net-scan", "--type", "skill", "--disabled"],
    )
    assert result.exit_code == 0
    assert "disabled state" in result.output


@patch("superpowers.cli_cron._engine")
def test_cron_add_error(mock_engine_fn):
    engine = _make_engine()
    engine.add_job.side_effect = ValueError("bad schedule")
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["add", "bad", "not-valid", "cmd"])
    assert result.exit_code != 0
    assert "bad schedule" in result.output


# --- cron remove ---


@patch("superpowers.cli_cron._engine")
def test_cron_remove_happy(mock_engine_fn):
    engine = _make_engine()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["remove", "abc12345"])
    assert result.exit_code == 0
    assert "Removed" in result.output


@patch("superpowers.cli_cron._engine")
def test_cron_remove_not_found(mock_engine_fn):
    engine = _make_engine(jobs=[])
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["remove", "missing"])
    assert result.exit_code != 0
    assert "No job found" in result.output


# --- cron enable ---


@patch("superpowers.cli_cron._engine")
def test_cron_enable_happy(mock_engine_fn):
    engine = _make_engine()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["enable", "abc12345"])
    assert result.exit_code == 0
    assert "Enabled" in result.output


# --- cron disable ---


@patch("superpowers.cli_cron._engine")
def test_cron_disable_happy(mock_engine_fn):
    engine = _make_engine()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["disable", "abc12345"])
    assert result.exit_code == 0
    assert "Disabled" in result.output


# --- cron logs ---


@patch("superpowers.cli_cron._engine")
def test_cron_logs_no_output_dir(mock_engine_fn, tmp_path):
    engine = _make_engine()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    with patch("superpowers.cli_cron.OUTPUT_DIR", tmp_path / "cron" / "output"):
        result = runner.invoke(cron_group, ["logs", "abc12345"])
    assert result.exit_code == 0
    assert "No output logs" in result.output


@patch("superpowers.cli_cron._engine")
def test_cron_logs_with_files(mock_engine_fn, tmp_path):
    engine = _make_engine()
    mock_engine_fn.return_value = engine

    log_dir = tmp_path / "cron" / "output" / "abc12345-6789"
    log_dir.mkdir(parents=True)
    (log_dir / "2026-01-01.log").write_text("line 1\nline 2")

    runner = CliRunner()
    with patch("superpowers.cli_cron.OUTPUT_DIR", tmp_path / "cron" / "output"):
        result = runner.invoke(cron_group, ["logs", "abc12345"])
    assert result.exit_code == 0
    assert "Logs for job" in result.output


# --- cron run ---


@patch("superpowers.cli_cron._engine")
def test_cron_run_happy(mock_engine_fn):
    engine = _make_engine()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["run", "abc12345"])
    assert result.exit_code == 0
    assert "Running job" in result.output
    assert "triggered" in result.output


@patch("superpowers.cli_cron._engine")
def test_cron_run_with_result(mock_engine_fn, tmp_path):
    engine = _make_engine()
    mock_result = MagicMock()
    mock_result.last_status = "ok"
    mock_result.last_output_file = str(tmp_path / "out.log")
    (tmp_path / "out.log").write_text("success output")
    engine.run_job.return_value = mock_result
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["run", "abc12345"])
    assert result.exit_code == 0
    assert "completed successfully" in result.output


@patch("superpowers.cli_cron._engine")
def test_cron_run_not_found(mock_engine_fn):
    engine = _make_engine(jobs=[])
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["run", "missing"])
    assert result.exit_code != 0


# --- cron status ---


@patch("superpowers.cli_cron.CronEngine")
@patch("superpowers.cli_cron._engine")
def test_cron_status_running(mock_engine_fn, mock_cls):
    mock_engine_fn.return_value = _make_engine()
    mock_cls.daemon_status.return_value = {"running": True, "pid": 1234}
    runner = CliRunner()
    result = runner.invoke(cron_group, ["status"])
    assert result.exit_code == 0
    assert "1234" in result.output


@patch("superpowers.cli_cron.CronEngine")
@patch("superpowers.cli_cron._engine")
def test_cron_status_stopped(mock_engine_fn, mock_cls):
    mock_engine_fn.return_value = _make_engine(jobs=[])
    mock_cls.daemon_status.return_value = {"running": False, "pid": None}
    runner = CliRunner()
    result = runner.invoke(cron_group, ["status"])
    assert result.exit_code == 0
    assert "stopped" in result.output


# --- _resolve_job_id ---


@patch("superpowers.cli_cron._engine")
def test_resolve_ambiguous_id(mock_engine_fn):
    job1 = FakeJob(id="abc11111-1111", name="job1")
    job2 = FakeJob(id="abc22222-2222", name="job2")
    engine = _make_engine(jobs=[job1, job2])
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(cron_group, ["remove", "abc"])
    assert result.exit_code != 0
    assert "Ambiguous" in result.output


# --- cron invoked without subcommand -> status ---


@patch("superpowers.cli_cron.CronEngine")
@patch("superpowers.cli_cron._engine")
def test_cron_no_subcommand_shows_status(mock_engine_fn, mock_cls):
    mock_engine_fn.return_value = _make_engine()
    mock_cls.daemon_status.return_value = {"running": False, "pid": None}
    runner = CliRunner()
    result = runner.invoke(cron_group)
    assert result.exit_code == 0
    assert "Cron Status" in result.output
