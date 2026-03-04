"""Tests for CLI jobs subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_jobs import jobs_group


def _mock_runner(branches=None, result=None):
    runner = MagicMock()
    runner.list_job_branches.return_value = branches or []
    if result is None:
        result = MagicMock()
        result.status = MagicMock(value="completed")
        result.job_id = "j-001"
        result.changed_files = ["file1.py"]
        result.commit_sha = "abc12345"
        result.error = ""
        result.pr_url = "https://github.com/user/repo/pull/1"
    runner.run.return_value = result
    runner.create_pr.return_value = result
    runner.can_auto_merge.return_value = True
    runner.auto_merge.return_value = result
    return runner


# --- jobs list ---


@patch("superpowers.cli_jobs._runner")
def test_jobs_list_with_branches(mock_runner_fn):
    branches = [
        {"job_id": "j-1", "branch": "job/j-1", "status": "completed", "sha": "aaa"},
        {"job_id": "j-2", "branch": "job/j-2", "status": "failed", "sha": "bbb"},
    ]
    mock_runner_fn.return_value = _mock_runner(branches=branches)
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["list"])
    assert result.exit_code == 0
    assert "j-1" in result.output
    assert "j-2" in result.output
    assert "completed" in result.output
    assert "failed" in result.output


@patch("superpowers.cli_jobs._runner")
def test_jobs_list_empty(mock_runner_fn):
    mock_runner_fn.return_value = _mock_runner(branches=[])
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["list"])
    assert result.exit_code == 0
    assert "No job branches found" in result.output


@patch("superpowers.cli_jobs._runner")
def test_jobs_list_with_repo(mock_runner_fn):
    mock_runner_fn.return_value = _mock_runner(branches=[])
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["list", "--repo", "/tmp/myrepo"])
    assert result.exit_code == 0
    mock_runner_fn.assert_called_once_with("/tmp/myrepo")


# --- jobs run ---


@patch("superpowers.cli_jobs._runner")
def test_jobs_run_completed(mock_runner_fn):
    mock_runner_fn.return_value = _mock_runner()
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["run", "my-task", "-c", "echo hi"])
    assert result.exit_code == 0
    assert "Job completed" in result.output
    assert "j-001" in result.output
    assert "file1.py" in result.output


@patch("superpowers.cli_jobs._runner")
def test_jobs_run_failed(mock_runner_fn):
    job_result = MagicMock()
    job_result.status = MagicMock(value="failed")
    job_result.job_id = "j-002"
    job_result.error = "command exited with code 1"
    job_result.changed_files = []
    job_result.commit_sha = None
    mock_runner_fn.return_value = _mock_runner(result=job_result)
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["run", "failing-task", "-c", "exit 1"])
    assert result.exit_code == 0
    assert "Job failed" in result.output


@patch("superpowers.cli_jobs._runner")
def test_jobs_run_with_pr(mock_runner_fn):
    mock_runner_fn.return_value = _mock_runner()
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["run", "task", "-c", "make", "--pr"])
    assert result.exit_code == 0
    assert "PR" in result.output


@patch("superpowers.cli_jobs._runner")
def test_jobs_run_auto_merge(mock_runner_fn):
    mock_runner_fn.return_value = _mock_runner()
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["run", "task", "-c", "make", "--auto-merge"])
    assert result.exit_code == 0
    assert "Auto-merged" in result.output


@patch("superpowers.cli_jobs._runner")
def test_jobs_run_auto_merge_blocked(mock_runner_fn):
    mr = _mock_runner()
    mr.can_auto_merge.return_value = False
    mock_runner_fn.return_value = mr
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["run", "task", "-c", "make", "--auto-merge"])
    assert result.exit_code == 0
    assert "Auto-merge blocked" in result.output


@patch("superpowers.cli_jobs._runner")
def test_jobs_run_missing_command_flag(mock_runner_fn):
    mock_runner_fn.return_value = _mock_runner()
    runner = CliRunner()
    result = runner.invoke(jobs_group, ["run", "task"])
    # Click should complain about missing required --command/-c
    assert result.exit_code != 0
    assert "Missing" in result.output or "required" in result.output.lower()
