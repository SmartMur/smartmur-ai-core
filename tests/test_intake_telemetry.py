"""Tests for structured intake telemetry and audit metadata support."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from superpowers.audit import AuditLog
from superpowers.intake_telemetry import IntakeTelemetry


# --- AuditLog metadata support ---


class TestAuditLogMetadata:
    def test_log_with_metadata_includes_metadata_key(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("test.action", "detail", "src", metadata={"key": "value", "num": 42})

        entry = json.loads(log_file.read_text().strip())
        assert entry["action"] == "test.action"
        assert entry["detail"] == "detail"
        assert entry["source"] == "src"
        assert entry["metadata"] == {"key": "value", "num": 42}

    def test_log_without_metadata_is_backward_compatible(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("test.action", "detail", "src")

        entry = json.loads(log_file.read_text().strip())
        assert "metadata" not in entry
        assert entry["action"] == "test.action"
        assert entry["detail"] == "detail"
        assert entry["source"] == "src"
        assert "ts" in entry

    def test_log_with_none_metadata_omits_key(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("test.action", "detail", metadata=None)

        entry = json.loads(log_file.read_text().strip())
        assert "metadata" not in entry

    def test_log_with_empty_dict_metadata_includes_key(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("test.action", "detail", metadata={})

        entry = json.loads(log_file.read_text().strip())
        assert entry["metadata"] == {}


# --- IntakeTelemetry event tests ---


class TestIntakeTelemetry:
    def _make_telemetry(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        telemetry = IntakeTelemetry(audit=audit)
        return telemetry, log_file

    def _last_entry(self, log_file):
        lines = log_file.read_text().strip().splitlines()
        return json.loads(lines[-1])

    def test_context_cleared(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.context_cleared(runtime_dir="/tmp/test")

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.context_cleared"
        assert entry["detail"] == "context cleared"
        assert entry["source"] == "intake"
        assert entry["metadata"]["runtime_dir"] == "/tmp/test"

    def test_requirements_extracted(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.requirements_extracted(count=3, preview="do thing one; do thing two; do thing three")

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.requirements_extracted"
        assert entry["detail"] == "extracted 3 requirements"
        assert entry["source"] == "intake"
        assert entry["metadata"]["count"] == 3
        assert "do thing one" in entry["metadata"]["preview"]

    def test_requirements_extracted_truncates_preview(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        long_preview = "x" * 500
        telemetry.requirements_extracted(count=1, preview=long_preview)

        entry = self._last_entry(log_file)
        assert len(entry["metadata"]["preview"]) == 200

    def test_plan_built(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.plan_built(task_count=5)

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.plan_built"
        assert entry["detail"] == "built plan with 5 tasks"
        assert entry["metadata"]["task_count"] == 5

    def test_skill_mapped(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.skill_mapped(task_id=1, requirement="run heartbeat", skill_name="heartbeat")

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.skill_mapped"
        assert entry["detail"] == "task 1: heartbeat"
        assert entry["source"] == "intake"
        assert entry["metadata"]["task_id"] == 1
        assert entry["metadata"]["requirement"] == "run heartbeat"
        assert entry["metadata"]["skill"] == "heartbeat"

    def test_skill_mapped_truncates_requirement(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        long_req = "a" * 200
        telemetry.skill_mapped(task_id=2, requirement=long_req, skill_name="test")

        entry = self._last_entry(log_file)
        assert len(entry["metadata"]["requirement"]) == 100

    def test_skill_map_failed(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.skill_map_failed(task_id=3, requirement="unknown task")

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.skill_map_failed"
        assert entry["detail"] == "task 3: no skill"
        assert entry["metadata"]["task_id"] == 3
        assert entry["metadata"]["requirement"] == "unknown task"

    def test_task_started(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.task_started(task_id=1, skill_name="heartbeat")

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.task_started"
        assert entry["detail"] == "task 1: heartbeat"
        assert entry["metadata"]["task_id"] == 1
        assert entry["metadata"]["skill"] == "heartbeat"

    def test_task_completed(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.task_completed(task_id=1, skill_name="heartbeat", status="ok", duration_ms=150)

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.task_completed"
        assert entry["detail"] == "task 1: ok"
        assert entry["metadata"]["task_id"] == 1
        assert entry["metadata"]["skill"] == "heartbeat"
        assert entry["metadata"]["status"] == "ok"
        assert entry["metadata"]["duration_ms"] == 150

    def test_task_completed_default_duration(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.task_completed(task_id=2, skill_name="test", status="failed")

        entry = self._last_entry(log_file)
        assert entry["metadata"]["duration_ms"] == 0

    def test_session_saved(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.session_saved(total=5, ok=3, failed=2, execute=True)

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.session_saved"
        assert entry["detail"] == "3 ok, 2 failed, 5 total"
        assert entry["metadata"]["total"] == 5
        assert entry["metadata"]["ok"] == 3
        assert entry["metadata"]["failed"] == 2
        assert entry["metadata"]["execute"] is True

    def test_notification_sent_success(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.notification_sent(channel="telegram", phase="start", success=True)

        entry = self._last_entry(log_file)
        assert entry["action"] == "intake.notification"
        assert entry["detail"] == "telegram: start (ok)"
        assert entry["metadata"]["channel"] == "telegram"
        assert entry["metadata"]["phase"] == "start"
        assert entry["metadata"]["success"] is True

    def test_notification_sent_failure(self, tmp_path):
        telemetry, log_file = self._make_telemetry(tmp_path)
        telemetry.notification_sent(channel="slack", phase="finish", success=False)

        entry = self._last_entry(log_file)
        assert entry["detail"] == "slack: finish (failed)"
        assert entry["metadata"]["success"] is False

    def test_default_audit_log_created(self):
        """IntakeTelemetry with no audit arg creates its own AuditLog."""
        telemetry = IntakeTelemetry()
        assert telemetry._audit is not None
        assert isinstance(telemetry._audit, AuditLog)


# --- Integration: run_intake with telemetry ---


class TestIntakeTelemetryIntegration:
    def test_run_intake_with_telemetry_emits_events(self, tmp_path, monkeypatch):
        from superpowers import intake
        from superpowers.intake import run_intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: None)

        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        telemetry = IntakeTelemetry(audit=audit)

        payload = run_intake(
            "- task alpha\n- task beta",
            runtime_dir=tmp_path,
            execute=False,
            telemetry=telemetry,
        )

        # Parse all audit entries
        entries = [json.loads(line) for line in log_file.read_text().strip().splitlines()]
        actions = [e["action"] for e in entries]

        # Verify lifecycle events were emitted in order
        assert "intake.context_cleared" in actions
        assert "intake.requirements_extracted" in actions
        assert "intake.plan_built" in actions
        # Both tasks should fail to map (check_and_install returns None)
        assert actions.count("intake.skill_map_failed") == 2
        assert "intake.session_saved" in actions

        # Verify ordering: context_cleared before requirements_extracted before plan_built
        idx_cleared = actions.index("intake.context_cleared")
        idx_reqs = actions.index("intake.requirements_extracted")
        idx_plan = actions.index("intake.plan_built")
        idx_saved = actions.index("intake.session_saved")
        assert idx_cleared < idx_reqs < idx_plan < idx_saved

    def test_run_intake_with_telemetry_skill_mapped(self, tmp_path, monkeypatch):
        from superpowers import intake
        from superpowers.intake import run_intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        telemetry = IntakeTelemetry(audit=audit)

        payload = run_intake(
            "run heartbeat",
            runtime_dir=tmp_path,
            execute=False,
            telemetry=telemetry,
        )

        entries = [json.loads(line) for line in log_file.read_text().strip().splitlines()]
        actions = [e["action"] for e in entries]

        assert "intake.skill_mapped" in actions
        mapped = [e for e in entries if e["action"] == "intake.skill_mapped"][0]
        assert mapped["metadata"]["skill"] == "heartbeat"

    def test_run_intake_without_telemetry_still_works(self, tmp_path, monkeypatch):
        """Backward compat: passing no telemetry should not break anything."""
        from superpowers import intake
        from superpowers.intake import run_intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: None)

        payload = run_intake("do something", runtime_dir=tmp_path, execute=False)
        assert payload is not None
        assert payload["requirements"] == ["do something"]

    def test_run_intake_execute_with_telemetry(self, tmp_path, monkeypatch):
        """When execute=True, telemetry should emit task_started/completed events."""
        from superpowers import intake
        from superpowers.intake import run_intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        telemetry = IntakeTelemetry(audit=audit)

        with patch.object(intake, "_execute_one") as mock_exec:
            def side_effect(task, loader, reg, telem=None):
                if telem:
                    telem.task_started(task.id, task.skill)
                    telem.task_completed(task.id, task.skill, "ok", duration_ms=50)
                task.status = "ok"
                return task

            mock_exec.side_effect = side_effect

            payload = run_intake(
                "run it",
                runtime_dir=tmp_path,
                execute=True,
                telemetry=telemetry,
            )

        entries = [json.loads(line) for line in log_file.read_text().strip().splitlines()]
        actions = [e["action"] for e in entries]

        assert "intake.task_started" in actions
        assert "intake.task_completed" in actions
        completed = [e for e in entries if e["action"] == "intake.task_completed"][0]
        assert completed["metadata"]["status"] == "ok"
        assert completed["metadata"]["duration_ms"] == 50
