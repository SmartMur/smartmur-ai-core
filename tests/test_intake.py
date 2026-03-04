"""Tests for request intake pipeline."""

from __future__ import annotations

import json
import types
from unittest.mock import MagicMock, patch

from superpowers import intake
from superpowers.intake import (
    IntakeTask,
    _execute_one,
    build_plan,
    clear_context,
    extract_requirements,
    run_intake,
)

# --- extract_requirements ---


def test_extract_requirements_multiline():
    text = """
    - first task
    * second task
    third task
    """
    reqs = extract_requirements(text)
    assert reqs == ["first task", "second task", "third task"]


def test_extract_requirements_single_line():
    assert extract_requirements("do something") == ["do something"]


def test_extract_requirements_empty_returns_stripped():
    assert extract_requirements("  hello  ") == ["hello"]


def test_extract_requirements_blank_lines_skipped():
    text = "line one\n\n\nline two"
    assert extract_requirements(text) == ["line one", "line two"]


def test_extract_requirements_strips_bullets():
    text = "- alpha\n* beta\n  - gamma"
    reqs = extract_requirements(text)
    assert reqs == ["alpha", "beta", "gamma"]


# --- clear_context ---


def test_clear_context_removes_json(tmp_path):
    old = tmp_path / "old.json"
    old.write_text("{}")

    marker = clear_context(tmp_path)
    assert marker.exists()
    assert marker.name == "context-cleared.json"
    assert not old.exists()


def test_clear_context_creates_dir(tmp_path):
    target = tmp_path / "subdir" / "deep"
    marker = clear_context(target)
    assert target.is_dir()
    assert marker.exists()
    data = json.loads(marker.read_text())
    assert data["status"] == "ready"
    assert "cleared_at" in data


def test_clear_context_leaves_non_json(tmp_path):
    txt = tmp_path / "keep.txt"
    txt.write_text("keep me")
    clear_context(tmp_path)
    assert txt.exists()


# --- build_plan ---


def test_build_plan_creates_indexed_tasks():
    reqs = ["a", "b", "c"]
    tasks = build_plan(reqs)
    assert len(tasks) == 3
    assert tasks[0].id == 1
    assert tasks[2].requirement == "c"
    assert all(t.skill is None and t.status == "planned" for t in tasks)


def test_build_plan_empty():
    assert build_plan([]) == []


# --- _execute_one ---


def test_execute_one_no_skill():
    task = IntakeTask(id=1, requirement="test", skill=None)
    result = _execute_one(task, MagicMock(), MagicMock())
    assert result.status == "skipped"
    assert result.error == "no mapped skill"


def test_execute_one_success():
    task = IntakeTask(id=1, requirement="run heartbeat", skill="heartbeat")
    mock_registry = MagicMock()
    mock_loader = MagicMock()
    mock_loader.run_sandboxed.return_value = types.SimpleNamespace(
        stdout="OK\n",
        stderr="",
        returncode=0,
    )
    result = _execute_one(task, mock_loader, mock_registry)
    assert result.status == "ok"
    assert "OK" in result.output
    mock_registry.get.assert_called_once_with("heartbeat")


def test_execute_one_failure_exit_code():
    task = IntakeTask(id=1, requirement="fail", skill="broken")
    mock_registry = MagicMock()
    mock_loader = MagicMock()
    mock_loader.run_sandboxed.return_value = types.SimpleNamespace(
        stdout="",
        stderr="boom",
        returncode=1,
    )
    result = _execute_one(task, mock_loader, mock_registry)
    assert result.status == "failed"
    assert result.error == "exit code 1"


def test_execute_one_exception():
    task = IntakeTask(id=1, requirement="crash", skill="crasher")
    mock_registry = MagicMock()
    mock_registry.get.side_effect = FileNotFoundError("no such skill")
    mock_loader = MagicMock()
    result = _execute_one(task, mock_loader, mock_registry)
    assert result.status == "failed"
    assert "no such skill" in result.error


# --- run_intake ---


def test_run_intake_writes_session(tmp_path, monkeypatch):
    session_file = tmp_path / "current_request.json"
    monkeypatch.setattr(intake, "SESSION_FILE", session_file)
    monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

    payload = run_intake("nightly status", runtime_dir=tmp_path, execute=False)

    assert payload["requirements"] == ["nightly status"]
    assert payload["tasks"][0]["skill"] == "heartbeat"
    assert payload["tasks"][0]["status"] == "planned"
    assert session_file.exists()
    saved = json.loads(session_file.read_text())
    assert saved["tasks"][0]["requirement"] == "nightly status"


def test_run_intake_no_skill_maps_to_failed(tmp_path, monkeypatch):
    session_file = tmp_path / "current_request.json"
    monkeypatch.setattr(intake, "SESSION_FILE", session_file)
    monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: None)

    payload = run_intake("unknown thing", runtime_dir=tmp_path, execute=False)
    assert payload["tasks"][0]["status"] == "failed"
    assert "could not map" in payload["tasks"][0]["error"]


def test_run_intake_execute_runs_tasks(tmp_path, monkeypatch):
    session_file = tmp_path / "current_request.json"
    monkeypatch.setattr(intake, "SESSION_FILE", session_file)
    monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

    with patch.object(intake, "_execute_one") as mock_exec:
        mock_exec.side_effect = lambda task, loader, reg, telem=None: (
            setattr(task, "status", "ok") or task
        )
        payload = run_intake("run it", runtime_dir=tmp_path, execute=True)

    assert mock_exec.called
    assert payload["execute"] is True


def test_run_intake_progress_callback(tmp_path, monkeypatch):
    session_file = tmp_path / "current_request.json"
    monkeypatch.setattr(intake, "SESSION_FILE", session_file)
    monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: None)

    messages = []
    run_intake("a task", runtime_dir=tmp_path, execute=False, progress_callback=messages.append)

    assert any("Planned" in m for m in messages)
    assert any("Intake complete" in m for m in messages)


def test_run_intake_callback_exception_swallowed(tmp_path, monkeypatch):
    session_file = tmp_path / "current_request.json"
    monkeypatch.setattr(intake, "SESSION_FILE", session_file)
    monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: None)

    def bad_callback(msg):
        raise RuntimeError("callback boom")

    # Should not raise
    payload = run_intake(
        "test", runtime_dir=tmp_path, execute=False, progress_callback=bad_callback
    )
    assert payload is not None


def test_run_intake_multi_requirements(tmp_path, monkeypatch):
    session_file = tmp_path / "current_request.json"
    monkeypatch.setattr(intake, "SESSION_FILE", session_file)
    monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

    payload = run_intake(
        "- task one\n- task two\n- task three", runtime_dir=tmp_path, execute=False
    )
    assert len(payload["tasks"]) == 3
    assert payload["requirements"] == ["task one", "task two", "task three"]


# --- cli_intake ---


def test_cli_intake_clear(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from superpowers.cli_intake import intake_group

    monkeypatch.setattr(intake, "RUNTIME_DIR", tmp_path)
    runner = CliRunner()
    result = runner.invoke(intake_group, ["clear"])
    assert result.exit_code == 0
    assert "Context cleared" in result.output


def test_cli_intake_show_no_session(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from superpowers.cli_intake import intake_group

    monkeypatch.setattr(intake, "SESSION_FILE", tmp_path / "missing.json")
    runner = CliRunner()
    result = runner.invoke(intake_group, ["show"])
    assert result.exit_code == 0
    assert "No intake session" in result.output


def test_cli_intake_show_with_session(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from superpowers.cli_intake import intake_group

    session = tmp_path / "current_request.json"
    session.write_text(json.dumps({"tasks": [], "requirements": []}))
    monkeypatch.setattr(intake, "SESSION_FILE", session)

    runner = CliRunner()
    result = runner.invoke(intake_group, ["show"])
    assert result.exit_code == 0
