"""Dashboard orchestrations API tests — TestClient with temp orchestrator data."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard import deps
from dashboard.app import app


# =============================================================================
# Fake engines (minimal stubs so the dashboard starts)
# =============================================================================


class FakeJob:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "job-1")
        self.name = kwargs.get("name", "test-job")
        self.schedule = kwargs.get("schedule", "every 30m")
        self.job_type = type("JT", (), {"value": kwargs.get("job_type", "shell")})()
        self.command = kwargs.get("command", "echo hello")
        self.args = kwargs.get("args", {})
        self.output_channel = kwargs.get("output_channel", "file")
        self.enabled = kwargs.get("enabled", True)
        self.created_at = kwargs.get("created_at", "2026-01-01T00:00:00")
        self.last_run = kwargs.get("last_run", "")
        self.last_status = kwargs.get("last_status", "")


class FakeCronEngine:
    def __init__(self, tmp_path):
        self._output_dir = tmp_path / "cron" / "output"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._jobs = {"job-1": FakeJob()}

    def list_jobs(self):
        return list(self._jobs.values())

    def get_job(self, job_id):
        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")
        return self._jobs[job_id]


class FakeMemoryStore:
    def list_memories(self, **kw):
        return []

    def stats(self):
        return {"total": 0, "by_category": {}, "oldest": None, "newest": None}

    def search(self, *a, **kw):
        return []


class FakeAuditLog:
    def tail(self, n=20):
        return []

    def search(self, query, limit=50):
        return []


class FakeChannelRegistry:
    def available(self):
        return []


class FakeProfileManager:
    def list_profiles(self):
        return []


class FakeHostRegistry:
    def list_hosts(self):
        return []

    def groups(self):
        return {}


class FakeWorkflowLoader:
    def list_workflows(self):
        return []


class FakeWorkflowEngine:
    pass


class FakeSkillRegistry:
    def list_skills(self):
        return []

    def get(self, name):
        raise KeyError(f"Skill not found: {name}")


class FakeWatcherEngine:
    def list_rules(self):
        return []


class FakeBrowserProfileManager:
    def list_profiles(self):
        return []


class FakeVault:
    def __init__(self, tmp_path):
        self.vault_path = tmp_path / "vault.enc"
        self.vault_path.touch()

    def list_keys(self):
        return []


class FakeSSHExecutor:
    def run(self, target, command, timeout=30):
        return []


class FakeHealthChecker:
    def check_all(self):
        return type("HR", (), {"hosts": []})()


# =============================================================================
# Helpers
# =============================================================================


def _make_report(
    command: str = "audit",
    status: str = "passed",
    started_at: str = "2026-03-01T10:00:00+00:00",
    finished_at: str = "2026-03-01T10:01:00+00:00",
    duration_ms: int = 60000,
    steps_passed: int = 3,
    steps_failed: int = 0,
    steps_skipped: int = 0,
    summary: str = "All checks passed",
    step_details: list | None = None,
) -> dict:
    if step_details is None:
        step_details = [
            {"name": "lint", "status": "passed", "output": "clean", "error": "", "duration_ms": 10000},
            {"name": "test", "status": "passed", "output": "42 passed", "error": "", "duration_ms": 30000},
            {"name": "scan", "status": "passed", "output": "no issues", "error": "", "duration_ms": 20000},
        ]
    return {
        "command": command,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "report_path": f"/data/orchestrator/{command}/20260301-100000.json",
        "summary": summary,
        "steps_passed": steps_passed,
        "steps_failed": steps_failed,
        "steps_skipped": steps_skipped,
        "total_duration_ms": duration_ms,
        "step_details": step_details,
    }


def _write_report(orch_dir: Path, command: str, timestamp: str, report: dict):
    """Write a JSON report file to the orchestrator output dir."""
    cmd_dir = orch_dir / command
    cmd_dir.mkdir(parents=True, exist_ok=True)
    json_path = cmd_dir / f"{timestamp}.json"
    json_path.write_text(json.dumps(report, indent=2))


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def orch_dir(tmp_path):
    """Create a temp orchestrator output directory."""
    d = tmp_path / "orchestrator"
    d.mkdir()
    return d


@pytest.fixture
def client(tmp_path, orch_dir, monkeypatch):
    """TestClient with auth bypass and patched orchestrator output dir."""
    monkeypatch.setenv("DASHBOARD_USER", "admin")
    monkeypatch.setenv("DASHBOARD_PASS", "testpass123")
    monkeypatch.setenv("DASHBOARD_SECRET", "test-secret-key-for-jwt-signing-1234")

    deps._settings = None

    # Override all singletons
    deps._cron_engine = FakeCronEngine(tmp_path)
    deps._memory_store = FakeMemoryStore()
    deps._host_registry = FakeHostRegistry()
    deps._ssh_executor = FakeSSHExecutor()
    deps._health_checker = FakeHealthChecker()
    deps._workflow_loader = FakeWorkflowLoader()
    deps._workflow_engine = FakeWorkflowEngine()
    deps._skill_registry = FakeSkillRegistry()
    deps._audit_log = FakeAuditLog()
    deps._watcher_engine = FakeWatcherEngine()
    deps._browser_profiles = FakeBrowserProfileManager()
    deps._channel_registry = FakeChannelRegistry()
    deps._profile_manager = FakeProfileManager()
    deps._vault = FakeVault(tmp_path)

    # Bypass auth
    app.dependency_overrides[deps.require_auth] = lambda: "test-user"

    # Patch get_data_dir to use our temp directory
    with patch("dashboard.routers.orchestrations.get_data_dir", return_value=tmp_path):
        with TestClient(app) as c:
            yield c

    # Clean up
    deps._settings = None
    deps._cron_engine = None
    deps._memory_store = None
    deps._host_registry = None
    deps._ssh_executor = None
    deps._health_checker = None
    deps._workflow_loader = None
    deps._workflow_engine = None
    deps._skill_registry = None
    deps._audit_log = None
    deps._watcher_engine = None
    deps._browser_profiles = None
    deps._channel_registry = None
    deps._profile_manager = None
    deps._vault = None
    app.dependency_overrides.pop(deps.require_auth, None)


# =============================================================================
# Tests: List orchestrations
# =============================================================================


class TestListOrchestrations:
    def test_list_empty(self, client):
        resp = client.get("/api/orchestrations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_data(self, client, orch_dir):
        report = _make_report(command="audit")
        _write_report(orch_dir, "audit", "20260301-100000", report)

        resp = client.get("/api/orchestrations")
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) == 1
        assert runs[0]["command"] == "audit"
        assert runs[0]["status"] == "passed"

    def test_list_multiple_commands(self, client, orch_dir):
        _write_report(orch_dir, "audit", "20260301-100000", _make_report(command="audit"))
        _write_report(
            orch_dir,
            "health-check",
            "20260301-110000",
            _make_report(command="health-check", status="failed", steps_failed=1),
        )

        resp = client.get("/api/orchestrations")
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) == 2
        commands = {r["command"] for r in runs}
        assert "audit" in commands
        assert "health-check" in commands

    def test_list_sorted_newest_first(self, client, orch_dir):
        _write_report(
            orch_dir,
            "audit",
            "20260301-080000",
            _make_report(command="audit", started_at="2026-03-01T08:00:00+00:00"),
        )
        _write_report(
            orch_dir,
            "audit",
            "20260301-120000",
            _make_report(command="audit", started_at="2026-03-01T12:00:00+00:00"),
        )

        resp = client.get("/api/orchestrations")
        runs = resp.json()
        assert len(runs) == 2
        # Newest first
        assert runs[0]["started_at"] >= runs[1]["started_at"]

    def test_list_with_limit(self, client, orch_dir):
        for i in range(5):
            ts = f"20260301-{10+i:02d}0000"
            _write_report(
                orch_dir,
                "audit",
                ts,
                _make_report(command="audit", started_at=f"2026-03-01T{10+i:02d}:00:00+00:00"),
            )

        resp = client.get("/api/orchestrations?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_ignores_latest_json(self, client, orch_dir):
        _write_report(orch_dir, "audit", "20260301-100000", _make_report(command="audit"))
        # Also write latest.json (which _save_report does)
        latest_path = orch_dir / "audit" / "latest.json"
        latest_path.write_text(json.dumps(_make_report(command="audit")))

        resp = client.get("/api/orchestrations")
        runs = resp.json()
        # Should only see the timestamped file, not latest.json
        assert len(runs) == 1


# =============================================================================
# Tests: Command-specific runs
# =============================================================================


class TestCommandRuns:
    def test_list_command_runs(self, client, orch_dir):
        _write_report(orch_dir, "audit", "20260301-100000", _make_report(command="audit"))
        _write_report(orch_dir, "audit", "20260301-110000", _make_report(command="audit"))

        resp = client.get("/api/orchestrations/audit")
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) == 2
        assert all(r["command"] == "audit" for r in runs)

    def test_list_command_runs_not_found(self, client):
        resp = client.get("/api/orchestrations/nonexistent-command")
        assert resp.status_code == 404

    def test_list_command_runs_empty_dir(self, client, orch_dir):
        """Command dir exists but has no JSON files."""
        (orch_dir / "empty-cmd").mkdir()
        resp = client.get("/api/orchestrations/empty-cmd")
        assert resp.status_code == 404


# =============================================================================
# Tests: Latest run
# =============================================================================


class TestLatestRun:
    def test_get_latest(self, client, orch_dir):
        _write_report(
            orch_dir,
            "audit",
            "20260301-080000",
            _make_report(command="audit", started_at="2026-03-01T08:00:00+00:00"),
        )
        _write_report(
            orch_dir,
            "audit",
            "20260301-120000",
            _make_report(command="audit", started_at="2026-03-01T12:00:00+00:00"),
        )

        resp = client.get("/api/orchestrations/audit/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["command"] == "audit"
        # Should be the newest (file sorted reverse)
        assert "20260301-120000" in data.get("timestamp", "")

    def test_get_latest_not_found(self, client):
        resp = client.get("/api/orchestrations/nonexistent/latest")
        assert resp.status_code == 404


# =============================================================================
# Tests: Specific run
# =============================================================================


class TestSpecificRun:
    def test_get_specific_run(self, client, orch_dir):
        report = _make_report(command="audit")
        _write_report(orch_dir, "audit", "20260301-100000", report)

        resp = client.get("/api/orchestrations/audit/runs/20260301-100000")
        assert resp.status_code == 200
        data = resp.json()
        assert data["command"] == "audit"
        assert data["status"] == "passed"
        assert data["steps_passed"] == 3
        assert data["timestamp"] == "20260301-100000"

    def test_get_specific_run_not_found(self, client, orch_dir):
        resp = client.get("/api/orchestrations/audit/runs/99999999-000000")
        assert resp.status_code == 404

    def test_get_specific_run_no_command_dir(self, client):
        resp = client.get("/api/orchestrations/nonexistent/runs/20260301-100000")
        assert resp.status_code == 404

    def test_get_specific_run_has_step_details(self, client, orch_dir):
        report = _make_report(command="audit")
        _write_report(orch_dir, "audit", "20260301-100000", report)

        resp = client.get("/api/orchestrations/audit/runs/20260301-100000")
        data = resp.json()
        assert len(data["step_details"]) == 3
        assert data["step_details"][0]["name"] == "lint"
        assert data["step_details"][1]["name"] == "test"


# =============================================================================
# Tests: Trigger run
# =============================================================================


class TestTriggerRun:
    def test_trigger_known_command(self, client):
        resp = client.post("/api/orchestrations/audit/run", json={"dry_run": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "audit" in data["message"]
        assert "dry-run" in data["message"]

    def test_trigger_live_run(self, client):
        resp = client.post("/api/orchestrations/audit/run", json={"dry_run": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "live" in data["message"]

    def test_trigger_unknown_command(self, client):
        resp = client.post("/api/orchestrations/totally-unknown/run", json={})
        assert resp.status_code == 404

    def test_trigger_with_repo_path(self, client):
        resp = client.post(
            "/api/orchestrations/audit/run",
            json={"dry_run": True, "repo_path": "/tmp/some-repo"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_trigger_no_body(self, client):
        """POST with no body should use defaults."""
        resp = client.post("/api/orchestrations/audit/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True


# =============================================================================
# Tests: Status summary
# =============================================================================


class TestStatus:
    def test_status_empty(self, client):
        resp = client.get("/api/orchestrations/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 0
        assert data["passed"] == 0
        assert data["failed"] == 0
        assert data["commands"] == []

    def test_status_with_data(self, client, orch_dir):
        _write_report(orch_dir, "audit", "20260301-100000", _make_report(command="audit", status="passed"))
        _write_report(
            orch_dir,
            "health-check",
            "20260301-110000",
            _make_report(command="health-check", status="failed"),
        )
        _write_report(
            orch_dir,
            "audit",
            "20260301-120000",
            _make_report(command="audit", status="passed", started_at="2026-03-01T12:00:00+00:00"),
        )

        resp = client.get("/api/orchestrations/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 3
        assert data["passed"] == 2
        assert data["failed"] == 1
        assert data["error"] == 0
        assert "audit" in data["commands"]
        assert "health-check" in data["commands"]
        assert data["last_run_time"] != ""

    def test_status_tracks_error(self, client, orch_dir):
        _write_report(
            orch_dir,
            "audit",
            "20260301-100000",
            _make_report(command="audit", status="error"),
        )

        resp = client.get("/api/orchestrations/status")
        data = resp.json()
        assert data["error"] == 1
        assert data["total_runs"] == 1

    def test_status_commands_list(self, client, orch_dir):
        _write_report(orch_dir, "audit", "20260301-100000", _make_report(command="audit"))
        _write_report(orch_dir, "benchmark", "20260301-110000", _make_report(command="benchmark"))
        _write_report(orch_dir, "code-health", "20260301-120000", _make_report(command="code-health"))

        resp = client.get("/api/orchestrations/status")
        data = resp.json()
        assert len(data["commands"]) == 3
        assert sorted(data["commands"]) == ["audit", "benchmark", "code-health"]


# =============================================================================
# Tests: Edge cases / malformed data
# =============================================================================


class TestEdgeCases:
    def test_malformed_json_skipped(self, client, orch_dir):
        """Malformed JSON files should be silently skipped."""
        cmd_dir = orch_dir / "audit"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "20260301-100000.json").write_text("not valid json{{{")
        # Also add a valid one
        _write_report(orch_dir, "audit", "20260301-110000", _make_report(command="audit"))

        resp = client.get("/api/orchestrations/audit")
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) == 1  # Only the valid one

    def test_report_with_extra_fields(self, client, orch_dir):
        """Reports with extra fields should still load."""
        report = _make_report(command="audit")
        report["extra_field"] = "bonus data"
        _write_report(orch_dir, "audit", "20260301-100000", report)

        resp = client.get("/api/orchestrations/audit/runs/20260301-100000")
        assert resp.status_code == 200
        assert resp.json()["command"] == "audit"

    def test_multiple_commands_isolated(self, client, orch_dir):
        """Runs for different commands should not leak into each other."""
        _write_report(orch_dir, "audit", "20260301-100000", _make_report(command="audit"))
        _write_report(orch_dir, "benchmark", "20260301-110000", _make_report(command="benchmark"))

        audit_resp = client.get("/api/orchestrations/audit")
        bench_resp = client.get("/api/orchestrations/benchmark")

        assert len(audit_resp.json()) == 1
        assert len(bench_resp.json()) == 1
        assert audit_resp.json()[0]["command"] == "audit"
        assert bench_resp.json()[0]["command"] == "benchmark"
