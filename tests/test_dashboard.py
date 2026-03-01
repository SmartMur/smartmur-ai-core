"""Dashboard API tests — TestClient with dependency overrides."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.app import app
from dashboard import deps


# =============================================================================
# Fake engines / stores for dependency injection
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

    def add_job(self, **kwargs):
        j = FakeJob(**kwargs)
        self._jobs[j.id] = j
        return j

    def remove_job(self, job_id):
        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")
        del self._jobs[job_id]

    def enable_job(self, job_id):
        j = self.get_job(job_id)
        j.enabled = True
        return j

    def disable_job(self, job_id):
        j = self.get_job(job_id)
        j.enabled = False
        return j

    def _execute_job(self, job_id):
        j = self.get_job(job_id)
        j.last_run = "2026-01-01T12:00:00"
        j.last_status = "ok"


@dataclass
class FakeMemoryEntry:
    id: int = 1
    category: type("MC", (), {"value": "fact"})() = None
    key: str = "test-key"
    value: str = "test-value"
    tags: list = field(default_factory=list)
    project: str = ""
    created_at: str = "2026-01-01T00:00:00"
    accessed_at: str = "2026-01-01T00:00:00"
    access_count: int = 1

    def __post_init__(self):
        if self.category is None:
            self.category = type("MC", (), {"value": "fact"})()


class FakeMemoryStore:
    def __init__(self):
        self._entries = [FakeMemoryEntry()]

    def list_memories(self, category=None, project=None, limit=50):
        return self._entries[:limit]

    def stats(self):
        return {"total": len(self._entries), "by_category": {"fact": 1}, "oldest": "2026-01-01", "newest": "2026-01-01"}

    def search(self, query, category=None, limit=20):
        return [e for e in self._entries if query.lower() in e.key.lower() or query.lower() in e.value.lower()]

    def remember(self, key, value, category="fact", tags=None, project=""):
        entry = FakeMemoryEntry(id=len(self._entries) + 1, key=key, value=value)
        self._entries.append(entry)
        return entry

    def recall(self, key, category=None):
        for e in self._entries:
            if e.key == key:
                return e
        return None

    def forget(self, key, category=None):
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.key != key]
        return len(self._entries) < before

    def decay(self, days=90):
        return 0


@dataclass
class FakeHostConfig:
    alias: str = "pve1"
    hostname: str = "192.168.1.10"
    port: int = 22
    username: str = "root"
    groups: list = field(default_factory=lambda: ["all", "proxmox"])


class FakeHostRegistry:
    def __init__(self):
        self._hosts = [FakeHostConfig()]

    def list_hosts(self):
        return self._hosts

    def groups(self):
        return {"all": ["pve1"], "proxmox": ["pve1"]}


@dataclass
class FakeCommandResult:
    host: str = "pve1"
    command: str = "uptime"
    stdout: str = "up 10 days"
    stderr: str = ""
    exit_code: int = 0
    ok: bool = True
    error: str = ""


class FakeSSHExecutor:
    def run(self, target, command, timeout=30):
        return [FakeCommandResult(command=command)]


@dataclass
class FakeHostStatus:
    alias: str = "pve1"
    hostname: str = "192.168.1.10"
    ping_ok: bool = True
    ssh_ok: bool = True
    uptime: str = "up 10 days"
    load_avg: str = "0.1, 0.2, 0.3"
    latency_ms: float = 5.0
    error: str = ""


class FakeHealthChecker:
    def check_all(self):
        return type("HR", (), {"hosts": [FakeHostStatus()]})()


class FakeWorkflowLoader:
    def list_workflows(self):
        return ["deploy", "backup"]

    def load(self, name):
        if name not in ("deploy", "backup"):
            raise Exception(f"Not found: {name}")
        from superpowers.workflow.base import StepConfig, StepType, WorkflowConfig
        return WorkflowConfig(
            name=name,
            description=f"The {name} workflow",
            steps=[StepConfig(
                name="step1", type=StepType.shell,
                command="echo hi",
            )],
        )

    def validate(self, config):
        return []


class FakeWorkflowEngine:
    def run(self, config, dry_run=False):
        from superpowers.workflow.base import StepResult, StepStatus
        return [StepResult(step_name="step1", status=StepStatus.passed, output="dry-run: ok" if dry_run else "ok")]


@dataclass
class FakeSkill:
    name: str = "heartbeat"
    description: str = "Ping hosts"
    version: str = "1.0.0"
    author: str = "dreday"
    triggers: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    permissions: list = field(default_factory=list)


class FakeSkillRegistry:
    def list_skills(self):
        return [FakeSkill()]

    def get(self, name):
        if name != "heartbeat":
            raise KeyError(f"Skill not found: {name}")
        return FakeSkill()


class FakeAuditLog:
    def tail(self, n=20):
        return [{"ts": "2026-01-01T00:00:00", "action": "test", "detail": "detail", "source": "dashboard"}]

    def search(self, query, limit=50):
        return [{"ts": "2026-01-01T00:00:00", "action": "test", "detail": query, "source": "dashboard"}]


@dataclass
class FakeWatchRule:
    name: str = "torrent-mover"
    path: str = "/Downloads"
    events: list = field(default_factory=lambda: ["created"])
    action: type = None
    command: str = "mv {} /torrents"
    enabled: bool = True

    def __post_init__(self):
        if self.action is None:
            self.action = type("WA", (), {"value": "shell"})()


class FakeWatcherEngine:
    def list_rules(self):
        return [FakeWatchRule()]


class FakeBrowserProfileManager:
    def list_profiles(self):
        return ["default", "proxmox"]


class FakeChannelRegistry:
    def available(self):
        return ["slack", "telegram"]

    def get(self, name):
        if name not in ("slack", "telegram"):
            from superpowers.channels.base import ChannelError
            raise ChannelError(f"Channel not configured: {name}")
        return type("Ch", (), {
            "send": lambda self, target, message: type("SR", (), {
                "ok": True, "channel": name, "target": target, "message": message, "error": ""
            })()
        })()


class FakeProfileManager:
    def list_profiles(self):
        return [type("NP", (), {
            "name": "critical",
            "targets": [type("PT", (), {"channel": "slack", "target": "#alerts"})()],
        })()]

    def send(self, name, message):
        if name != "critical":
            raise KeyError(f"Profile not found: {name}")
        return [type("SR", (), {"ok": True, "channel": "slack", "target": "#alerts", "error": ""})()]


class FakeVault:
    def __init__(self, tmp_path):
        self.vault_path = tmp_path / "vault.enc"
        self.vault_path.touch()

    def list_keys(self):
        return ["API_KEY", "SSH_PASS"]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_cron_dir(tmp_path):
    return tmp_path


@pytest.fixture
def client(tmp_path):
    """TestClient with all dependencies overridden to fakes."""
    fake_cron = FakeCronEngine(tmp_path)
    fake_memory = FakeMemoryStore()
    fake_hosts = FakeHostRegistry()
    fake_executor = FakeSSHExecutor()
    fake_health = FakeHealthChecker()
    fake_wf_loader = FakeWorkflowLoader()
    fake_wf_engine = FakeWorkflowEngine()
    fake_skills = FakeSkillRegistry()
    fake_audit = FakeAuditLog()
    fake_watcher = FakeWatcherEngine()
    fake_browser = FakeBrowserProfileManager()
    fake_channels = FakeChannelRegistry()
    fake_profiles = FakeProfileManager()
    fake_vault = FakeVault(tmp_path)

    # Bypass auth for existing tests
    app.dependency_overrides[deps.require_auth] = lambda: "test-user"

    # Override all singleton instances in deps module
    deps._cron_engine = fake_cron
    deps._memory_store = fake_memory
    deps._host_registry = fake_hosts
    deps._ssh_executor = fake_executor
    deps._health_checker = fake_health
    deps._workflow_loader = fake_wf_loader
    deps._workflow_engine = fake_wf_engine
    deps._skill_registry = fake_skills
    deps._audit_log = fake_audit
    deps._watcher_engine = fake_watcher
    deps._browser_profiles = fake_browser
    deps._channel_registry = fake_channels
    deps._profile_manager = fake_profiles
    deps._vault = fake_vault

    with TestClient(app) as c:
        yield c

    # Reset singletons
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
# Status
# =============================================================================


class TestStatus:
    def test_aggregate_status(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "subsystems" in data
        names = [s["name"] for s in data["subsystems"]]
        assert "cron" in names
        assert "channels" in names
        assert "memory" in names

    def test_status_contains_all_subsystems(self, client):
        resp = client.get("/api/status")
        data = resp.json()
        expected = {"cron", "channels", "ssh", "workflows", "memory", "skills", "vault", "watchers", "audit", "browser"}
        actual = {s["name"] for s in data["subsystems"]}
        assert expected == actual

    def test_status_cron_detail(self, client):
        resp = client.get("/api/status")
        cron = [s for s in resp.json()["subsystems"] if s["name"] == "cron"][0]
        assert cron["ok"] is True
        assert "1 jobs" in cron["detail"]


# =============================================================================
# Cron
# =============================================================================


class TestCron:
    def test_list_jobs(self, client):
        resp = client.get("/api/cron/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "test-job"

    def test_get_job(self, client):
        resp = client.get("/api/cron/jobs/job-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "job-1"

    def test_get_job_not_found(self, client):
        resp = client.get("/api/cron/jobs/nope")
        assert resp.status_code == 404

    def test_create_job(self, client):
        resp = client.post("/api/cron/jobs", json={
            "name": "new-job",
            "schedule": "every 1h",
            "command": "ls",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "new-job"

    def test_delete_job(self, client):
        resp = client.delete("/api/cron/jobs/job-1")
        assert resp.status_code == 204

    def test_delete_job_not_found(self, client):
        resp = client.delete("/api/cron/jobs/nope")
        assert resp.status_code == 404

    def test_enable_job(self, client):
        resp = client.post("/api/cron/jobs/job-1/enable")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_disable_job(self, client):
        resp = client.post("/api/cron/jobs/job-1/disable")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_run_job(self, client):
        resp = client.post("/api/cron/jobs/job-1/run")
        assert resp.status_code == 200
        assert resp.json()["last_status"] == "ok"

    def test_run_job_not_found(self, client):
        resp = client.post("/api/cron/jobs/nope/run")
        assert resp.status_code == 404

    def test_get_logs_empty(self, client):
        resp = client.get("/api/cron/jobs/job-1/logs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_logs_with_file(self, client, tmp_path):
        log_dir = tmp_path / "cron" / "output" / "job-1"
        log_dir.mkdir(parents=True)
        (log_dir / "20260101T120000Z.log").write_text("exit_code: 0\n---\nhello\n")
        resp = client.get("/api/cron/jobs/job-1/logs")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) == 1
        assert "hello" in logs[0]["content"]


# =============================================================================
# Messaging
# =============================================================================


class TestMessaging:
    def test_list_channels(self, client):
        resp = client.get("/api/msg/channels")
        assert resp.status_code == 200
        channels = resp.json()
        assert len(channels) == 4
        slack = [c for c in channels if c["name"] == "slack"][0]
        assert slack["configured"] is True

    def test_send_message(self, client):
        resp = client.post("/api/msg/send", json={
            "channel": "slack",
            "target": "#general",
            "message": "hello",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_send_unconfigured_channel(self, client):
        resp = client.post("/api/msg/send", json={
            "channel": "discord",
            "target": "#general",
            "message": "hello",
        })
        assert resp.status_code == 400

    def test_test_channel(self, client):
        resp = client.post("/api/msg/test/slack")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_list_profiles(self, client):
        resp = client.get("/api/msg/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) == 1
        assert profiles[0]["name"] == "critical"

    def test_send_via_profile(self, client):
        resp = client.post("/api/msg/profiles/critical/send", json={"message": "test"})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["ok"] is True

    def test_send_via_missing_profile(self, client):
        resp = client.post("/api/msg/profiles/nope/send", json={"message": "test"})
        assert resp.status_code == 404


# =============================================================================
# SSH
# =============================================================================


class TestSSH:
    def test_list_hosts(self, client):
        resp = client.get("/api/ssh/hosts")
        assert resp.status_code == 200
        hosts = resp.json()
        assert len(hosts) == 1
        assert hosts[0]["alias"] == "pve1"

    def test_list_groups(self, client):
        resp = client.get("/api/ssh/groups")
        assert resp.status_code == 200
        groups = resp.json()
        assert "all" in groups

    def test_run_command(self, client):
        resp = client.post("/api/ssh/run", json={
            "target": "pve1",
            "command": "uptime",
        })
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["ok"] is True
        assert "up 10 days" in results[0]["stdout"]

    def test_health_check(self, client):
        resp = client.get("/api/ssh/health")
        assert resp.status_code == 200
        health = resp.json()
        assert len(health) == 1
        assert health[0]["ping_ok"] is True
        assert health[0]["ssh_ok"] is True


# =============================================================================
# Workflows
# =============================================================================


class TestWorkflows:
    def test_list_workflows(self, client):
        resp = client.get("/api/workflows")
        assert resp.status_code == 200
        wfs = resp.json()
        assert len(wfs) == 2
        names = [w["name"] for w in wfs]
        assert "deploy" in names

    def test_get_workflow(self, client):
        resp = client.get("/api/workflows/deploy")
        assert resp.status_code == 200
        assert resp.json()["name"] == "deploy"
        assert len(resp.json()["steps"]) == 1

    def test_get_workflow_not_found(self, client):
        resp = client.get("/api/workflows/nope")
        assert resp.status_code == 404

    def test_validate_workflow(self, client):
        resp = client.post("/api/workflows/deploy/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_run_dry(self, client):
        resp = client.post("/api/workflows/deploy/run", json={"dry_run": True})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["status"] == "passed"

    def test_run_live(self, client):
        resp = client.post("/api/workflows/deploy/run", json={"dry_run": False})
        assert resp.status_code == 200


# =============================================================================
# Memory
# =============================================================================


class TestMemory:
    def test_list_memories(self, client):
        resp = client.get("/api/memory")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_memory_stats(self, client):
        resp = client.get("/api/memory/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total"] >= 1

    def test_search_memories(self, client):
        resp = client.get("/api/memory/search?q=test")
        assert resp.status_code == 200

    def test_create_memory(self, client):
        resp = client.post("/api/memory", json={
            "key": "ssh-host",
            "value": "192.168.1.1",
            "category": "fact",
        })
        assert resp.status_code == 201
        assert resp.json()["key"] == "ssh-host"

    def test_recall_memory(self, client):
        resp = client.get("/api/memory/test-key")
        assert resp.status_code == 200
        assert resp.json()["key"] == "test-key"

    def test_recall_not_found(self, client):
        resp = client.get("/api/memory/nonexistent")
        assert resp.status_code == 404

    def test_forget_memory(self, client):
        resp = client.delete("/api/memory/test-key")
        assert resp.status_code == 204

    def test_forget_not_found(self, client):
        resp = client.delete("/api/memory/nonexistent")
        assert resp.status_code == 404

    def test_decay(self, client):
        resp = client.post("/api/memory/decay?days=90")
        assert resp.status_code == 200
        assert "removed" in resp.json()


# =============================================================================
# Skills
# =============================================================================


class TestSkills:
    def test_list_skills(self, client):
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        skills = resp.json()
        assert len(skills) == 1
        assert skills[0]["name"] == "heartbeat"

    def test_get_skill(self, client):
        resp = client.get("/api/skills/heartbeat")
        assert resp.status_code == 200
        assert resp.json()["version"] == "1.0.0"

    def test_get_skill_not_found(self, client):
        resp = client.get("/api/skills/nonexistent")
        assert resp.status_code == 404


# =============================================================================
# Audit
# =============================================================================


class TestAudit:
    def test_tail(self, client):
        resp = client.get("/api/audit/tail")
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) >= 1
        assert entries[0]["action"] == "test"

    def test_tail_with_limit(self, client):
        resp = client.get("/api/audit/tail?n=5")
        assert resp.status_code == 200

    def test_search(self, client):
        resp = client.get("/api/audit/search?q=test")
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) >= 1


# =============================================================================
# Vault
# =============================================================================


class TestVault:
    def test_vault_status(self, client):
        resp = client.get("/api/vault/status")
        assert resp.status_code == 200
        status = resp.json()
        assert status["initialized"] is True
        assert status["key_count"] == 2

    def test_vault_keys(self, client):
        resp = client.get("/api/vault/keys")
        assert resp.status_code == 200
        keys = resp.json()
        assert "API_KEY" in keys
        assert "SSH_PASS" in keys


# =============================================================================
# Watchers
# =============================================================================


class TestWatchers:
    def test_list_rules(self, client):
        resp = client.get("/api/watchers/rules")
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) == 1
        assert rules[0]["name"] == "torrent-mover"

    def test_get_rule(self, client):
        resp = client.get("/api/watchers/rules/torrent-mover")
        assert resp.status_code == 200
        assert resp.json()["action"] == "shell"

    def test_get_rule_not_found(self, client):
        resp = client.get("/api/watchers/rules/nonexistent")
        assert resp.status_code == 404


# =============================================================================
# Browser
# =============================================================================


class TestBrowser:
    def test_list_profiles(self, client):
        resp = client.get("/api/browser/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) == 2
        names = [p["name"] for p in profiles]
        assert "default" in names
        assert "proxmox" in names


# =============================================================================
# Static files
# =============================================================================


class TestStatic:
    def test_index_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Claw Dashboard" in resp.text

    def test_app_css(self, client):
        resp = client.get("/app.css")
        assert resp.status_code == 200
        assert "--bg-primary" in resp.text

    def test_app_js(self, client):
        resp = client.get("/app.js")
        assert resp.status_code == 200
        assert "function app()" in resp.text

    def test_favicon(self, client):
        resp = client.get("/favicon.svg")
        assert resp.status_code == 200
