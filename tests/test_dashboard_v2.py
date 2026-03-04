"""Dashboard v2 tests — session auth, chat, notifications, jobs, settings."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from dashboard import deps
from dashboard.app import app
from dashboard.db import ConversationsDB, JobsDB, NotificationsDB

# =============================================================================
# Fake engines (reuse from test_dashboard.py patterns)
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
        return {
            "total": len(self._entries),
            "by_category": {"fact": 1},
            "oldest": "2026-01-01",
            "newest": "2026-01-01",
        }

    def search(self, query, category=None, limit=20):
        return [
            e
            for e in self._entries
            if query.lower() in e.key.lower() or query.lower() in e.value.lower()
        ]

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


class FakeAuditLog:
    def tail(self, n=20):
        return [
            {
                "ts": "2026-01-01T00:00:00",
                "action": "test",
                "detail": "detail",
                "source": "dashboard",
            }
        ]

    def search(self, query, limit=50):
        return [
            {"ts": "2026-01-01T00:00:00", "action": "test", "detail": query, "source": "dashboard"}
        ]


class FakeChannelRegistry:
    def available(self):
        return ["slack", "telegram"]

    def get(self, name):
        if name not in ("slack", "telegram"):
            from superpowers.channels.base import ChannelError

            raise ChannelError(f"Channel not configured: {name}")
        return type(
            "Ch",
            (),
            {
                "send": lambda self, target, message: type(
                    "SR",
                    (),
                    {
                        "ok": True,
                        "channel": name,
                        "target": target,
                        "message": message,
                        "error": "",
                    },
                )(),
                "test_connection": lambda self: type(
                    "SR",
                    (),
                    {
                        "ok": True,
                        "channel": name,
                        "target": "",
                        "message": "connected",
                        "error": "",
                    },
                )(),
            },
        )()


class FakeProfileManager:
    def list_profiles(self):
        return [
            type(
                "NP",
                (),
                {
                    "name": "critical",
                    "targets": [type("PT", (), {"channel": "slack", "target": "#alerts"})()],
                },
            )()
        ]

    def send(self, name, message):
        if name != "critical":
            raise KeyError(f"Profile not found: {name}")
        return [
            type("SR", (), {"ok": True, "channel": "slack", "target": "#alerts", "error": ""})()
        ]


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
# Fixtures
# =============================================================================


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary DB path."""
    return tmp_path / "test_dashboard.db"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with session auth and all dependencies overridden."""
    monkeypatch.setenv("DASHBOARD_USER", "admin")
    monkeypatch.setenv("DASHBOARD_PASS", "testpass123")
    monkeypatch.setenv("DASHBOARD_SECRET", "test-secret-key-for-jwt-signing-1234")

    # Reset cached settings
    deps._settings = None

    db_path = tmp_path / "test_dashboard.db"

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
    deps._conversations_db = ConversationsDB(db_path)
    deps._notifications_db = NotificationsDB(db_path)
    deps._jobs_db = JobsDB(db_path)

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
    deps._conversations_db = None
    deps._notifications_db = None
    deps._jobs_db = None
    deps._runtime_secret = None


def _login(client) -> dict:
    """Login and return cookies dict."""
    resp = client.post("/login", json={"username": "admin", "password": "testpass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    return dict(resp.cookies)


def _auth_cookies(client) -> dict:
    """Shortcut: login and return the session cookie for subsequent requests."""
    _login(client)
    # TestClient persists cookies, so just return
    return {}


# =============================================================================
# C1: Session Auth Tests
# =============================================================================


class TestSessionAuth:
    """Test JWT/cookie-based session auth."""

    def test_login_success(self, client):
        resp = client.post("/login", json={"username": "admin", "password": "testpass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["username"] == "admin"
        # Session cookie should be set
        assert "claw_session" in resp.cookies

    def test_login_wrong_password(self, client):
        resp = client.post("/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert "Invalid" in data["error"]

    def test_login_wrong_user(self, client):
        resp = client.post("/login", json={"username": "hacker", "password": "testpass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False

    def test_api_unauthenticated(self, client):
        # Clear any cookies
        client.cookies.clear()
        resp = client.get("/api/status")
        assert resp.status_code == 401

    def test_api_authenticated_via_cookie(self, client):
        _login(client)
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "subsystems" in data

    def test_logout(self, client):
        _login(client)
        # Verify authed
        resp = client.get("/api/status")
        assert resp.status_code == 200

        # Logout
        resp = client.post("/logout")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Cookie should be cleared — next request unauthenticated
        client.cookies.clear()
        resp = client.get("/api/status")
        assert resp.status_code == 401

    def test_session_token_expiry(self, client, monkeypatch):
        """Test that expired tokens are rejected."""
        # Create a token that's already expired
        import jwt as pyjwt

        from dashboard.deps import verify_session_token

        payload = {"sub": "admin", "iat": int(time.time()) - 90000, "exp": int(time.time()) - 3600}
        expired_token = pyjwt.encode(
            payload, "test-secret-key-for-jwt-signing-1234", algorithm="HS256"
        )

        result = verify_session_token(expired_token)
        assert result is None

    def test_health_no_auth(self, client):
        client.cookies.clear()
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_static_no_auth(self, client):
        client.cookies.clear()
        resp = client.get("/login.html")
        assert resp.status_code == 200

    def test_login_endpoint_is_public(self, client):
        client.cookies.clear()
        resp = client.post("/login", json={"username": "admin", "password": "testpass123"})
        assert resp.status_code == 200

    def test_basic_auth_fallback(self, client):
        """HTTP Basic auth should still work alongside cookies."""
        import base64

        client.cookies.clear()
        creds = base64.b64encode(b"admin:testpass123").decode()
        resp = client.get("/api/status", headers={"Authorization": f"Basic {creds}"})
        assert resp.status_code == 200


# =============================================================================
# C2 + C3: Chat API Tests
# =============================================================================


class TestChatAPI:
    """Test chat conversation CRUD and messaging."""

    def test_create_conversation(self, client):
        _login(client)
        resp = client.post("/api/chat/conversations")
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["title"] == "New conversation"
        assert data["messages"] == []

    def test_list_conversations(self, client):
        _login(client)
        # Create a couple
        client.post("/api/chat/conversations")
        client.post("/api/chat/conversations")
        resp = client.get("/api/chat/conversations")
        assert resp.status_code == 200
        convs = resp.json()
        assert len(convs) >= 2

    def test_get_conversation(self, client):
        _login(client)
        create_resp = client.post("/api/chat/conversations")
        cid = create_resp.json()["id"]

        resp = client.get(f"/api/chat/conversations/{cid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cid

    def test_get_conversation_not_found(self, client):
        _login(client)
        resp = client.get("/api/chat/conversations/nonexistent")
        assert resp.status_code == 404

    def test_delete_conversation(self, client):
        _login(client)
        create_resp = client.post("/api/chat/conversations")
        cid = create_resp.json()["id"]

        resp = client.delete(f"/api/chat/conversations/{cid}")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get(f"/api/chat/conversations/{cid}")
        assert resp.status_code == 404

    def test_delete_conversation_not_found(self, client):
        _login(client)
        resp = client.delete("/api/chat/conversations/nonexistent")
        assert resp.status_code == 404

    def test_send_message(self, client):
        _login(client)
        create_resp = client.post("/api/chat/conversations")
        cid = create_resp.json()["id"]

        resp = client.post(
            "/api/chat/send",
            json={
                "message": "Hello Claude",
                "conversation_id": cid,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == cid
        assert "response" in data

    def test_send_message_auto_creates_conversation(self, client):
        _login(client)
        resp = client.post("/api/chat/send", json={"message": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"]  # Should have created one

    def test_conversation_auto_title(self, client):
        _login(client)
        create_resp = client.post("/api/chat/conversations")
        cid = create_resp.json()["id"]

        client.post(
            "/api/chat/send",
            json={
                "message": "Tell me about Python decorators",
                "conversation_id": cid,
            },
        )

        # Check the conversation was titled
        resp = client.get(f"/api/chat/conversations/{cid}")
        conv = resp.json()
        assert conv["title"] != "New conversation"
        assert "Python" in conv["title"] or "Tell" in conv["title"]

    def test_stream_endpoint_exists(self, client):
        _login(client)
        # Test that the stream endpoint is reachable (it will start streaming)
        with client.stream("GET", "/api/chat/stream?message=hello") as resp:
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("text/event-stream")
            # Read a few events
            events = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
                    if len(events) >= 2:
                        break
            # Should have at least a meta event
            assert any(e.get("type") == "meta" for e in events)


# =============================================================================
# C4: Notifications API Tests
# =============================================================================


class TestNotificationsAPI:
    """Test notification center."""

    def test_create_notification(self, client):
        _login(client)
        resp = client.post(
            "/api/notifications",
            json={
                "source": "cron",
                "title": "Job failed: backup",
                "detail": "Exit code 1",
                "level": "error",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Job failed: backup"
        assert data["read"] is False

    def test_list_notifications(self, client):
        _login(client)
        client.post("/api/notifications", json={"source": "test", "title": "N1"})
        client.post("/api/notifications", json={"source": "test", "title": "N2"})

        resp = client.get("/api/notifications")
        assert resp.status_code == 200
        notifs = resp.json()
        assert len(notifs) >= 2

    def test_unread_count(self, client):
        _login(client)
        client.post("/api/notifications", json={"source": "test", "title": "Unread 1"})
        client.post("/api/notifications", json={"source": "test", "title": "Unread 2"})

        resp = client.get("/api/notifications/unread")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 2

    def test_mark_read(self, client):
        _login(client)
        create_resp = client.post("/api/notifications", json={"source": "test", "title": "To read"})
        nid = create_resp.json()["id"]

        resp = client.post(f"/api/notifications/{nid}/read")
        assert resp.status_code == 200

        # Verify it's read
        notifs = client.get("/api/notifications").json()
        n = [x for x in notifs if x["id"] == nid][0]
        assert n["read"] is True

    def test_mark_read_not_found(self, client):
        _login(client)
        resp = client.post("/api/notifications/nonexistent/read")
        assert resp.status_code == 404

    def test_mark_all_read(self, client):
        _login(client)
        client.post("/api/notifications", json={"source": "test", "title": "A"})
        client.post("/api/notifications", json={"source": "test", "title": "B"})

        resp = client.post("/api/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify all read
        count = client.get("/api/notifications/unread").json()["count"]
        assert count == 0

    def test_unread_only_filter(self, client):
        _login(client)
        client.post("/api/notifications", json={"source": "test", "title": "Unread"})
        r = client.post("/api/notifications", json={"source": "test", "title": "Read"})
        nid = r.json()["id"]
        client.post(f"/api/notifications/{nid}/read")

        resp = client.get("/api/notifications?unread_only=true")
        assert resp.status_code == 200
        notifs = resp.json()
        assert all(not n["read"] for n in notifs)

    def test_delete_notification(self, client):
        _login(client)
        create_resp = client.post(
            "/api/notifications", json={"source": "test", "title": "Delete me"}
        )
        nid = create_resp.json()["id"]

        resp = client.delete(f"/api/notifications/{nid}")
        assert resp.status_code == 204

    def test_delete_notification_not_found(self, client):
        _login(client)
        resp = client.delete("/api/notifications/nonexistent")
        assert resp.status_code == 404

    def test_notification_feed(self, client):
        _login(client)
        client.post("/api/notifications", json={"source": "cron", "title": "Feed item"})
        resp = client.get("/api/notifications/feed")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# =============================================================================
# C5: Job Monitor API Tests
# =============================================================================


class TestJobMonitorAPI:
    """Test job monitor."""

    def test_create_job(self, client):
        _login(client)
        resp = client.post("/api/jobs", json={"name": "build-app", "job_type": "shell"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "build-app"
        assert data["status"] == "queued"

    def test_list_jobs(self, client):
        _login(client)
        client.post("/api/jobs", json={"name": "job-a"})
        client.post("/api/jobs", json={"name": "job-b"})

        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_job(self, client):
        _login(client)
        create_resp = client.post("/api/jobs", json={"name": "my-job"})
        jid = create_resp.json()["id"]

        resp = client.get(f"/api/jobs/{jid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "my-job"

    def test_get_job_not_found(self, client):
        _login(client)
        resp = client.get("/api/jobs/nonexistent")
        assert resp.status_code == 404

    def test_start_job(self, client):
        _login(client)
        create_resp = client.post("/api/jobs", json={"name": "start-me"})
        jid = create_resp.json()["id"]

        resp = client.post(f"/api/jobs/{jid}/start")
        assert resp.status_code == 200

        job = client.get(f"/api/jobs/{jid}").json()
        assert job["status"] == "running"
        assert job["started_at"] is not None

    def test_complete_job(self, client):
        _login(client)
        create_resp = client.post("/api/jobs", json={"name": "complete-me"})
        jid = create_resp.json()["id"]

        client.post(f"/api/jobs/{jid}/start")
        resp = client.post(f"/api/jobs/{jid}/complete?output=all+done")
        assert resp.status_code == 200

        job = client.get(f"/api/jobs/{jid}").json()
        assert job["status"] == "completed"
        assert job["duration"] is not None

    def test_complete_job_with_error(self, client):
        _login(client)
        create_resp = client.post("/api/jobs", json={"name": "fail-me"})
        jid = create_resp.json()["id"]

        client.post(f"/api/jobs/{jid}/start")
        resp = client.post(f"/api/jobs/{jid}/complete?error=something+broke")
        assert resp.status_code == 200

        job = client.get(f"/api/jobs/{jid}").json()
        assert job["status"] == "failed"

    def test_delete_job(self, client):
        _login(client)
        create_resp = client.post("/api/jobs", json={"name": "delete-me"})
        jid = create_resp.json()["id"]

        resp = client.delete(f"/api/jobs/{jid}")
        assert resp.status_code == 204

    def test_delete_job_not_found(self, client):
        _login(client)
        resp = client.delete("/api/jobs/nonexistent")
        assert resp.status_code == 404

    def test_filter_by_status(self, client):
        _login(client)
        client.post("/api/jobs", json={"name": "a"})
        r2 = client.post("/api/jobs", json={"name": "b"})
        # Start one
        client.post(f"/api/jobs/{r2.json()['id']}/start")

        queued = client.get("/api/jobs?status=queued").json()
        running = client.get("/api/jobs?status=running").json()
        assert all(j["status"] == "queued" for j in queued)
        assert all(j["status"] == "running" for j in running)

    def test_job_counts(self, client):
        """Verify we can count jobs by status without the infinite SSE endpoint."""
        _login(client)
        client.post("/api/jobs", json={"name": "cnt-a"})
        r2 = client.post("/api/jobs", json={"name": "cnt-b"})
        r3 = client.post("/api/jobs", json={"name": "cnt-c"})
        client.post(f"/api/jobs/{r2.json()['id']}/start")
        client.post(f"/api/jobs/{r3.json()['id']}/start")
        client.post(f"/api/jobs/{r3.json()['id']}/complete?output=done")

        all_jobs = client.get("/api/jobs").json()
        statuses = [j["status"] for j in all_jobs]
        assert "queued" in statuses
        assert "running" in statuses
        assert "completed" in statuses


# =============================================================================
# C6: Settings API Tests
# =============================================================================


class TestSettingsAPI:
    """Test settings area."""

    def test_settings_overview(self, client):
        _login(client)
        resp = client.get("/api/settings/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "integrations" in data
        assert isinstance(data["integrations"], list)
        assert len(data["integrations"]) >= 5  # At least telegram, slack, discord, email, HA
        assert "cron_count" in data

    def test_integrations_list(self, client):
        _login(client)
        resp = client.get("/api/settings/integrations")
        assert resp.status_code == 200
        integrations = resp.json()
        names = [i["name"] for i in integrations]
        assert "Telegram" in names
        assert "Slack" in names
        assert "Redis" in names

    def test_integration_has_configured_flag(self, client):
        _login(client)
        resp = client.get("/api/settings/integrations")
        integrations = resp.json()
        for i in integrations:
            assert "configured" in i
            assert "detail" in i


# =============================================================================
# C7: Navigation / Static Tests
# =============================================================================


class TestNavigationAndStatic:
    """Test that static files and new pages are accessible."""

    def test_index_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Claw Dashboard" in resp.text

    def test_index_has_new_nav_sections(self, client):
        resp = client.get("/")
        body = resp.text
        assert "Chat" in body
        assert "Jobs" in body
        assert "Notifications" in body
        assert "Settings" in body

    def test_index_has_theme_toggle(self, client):
        resp = client.get("/")
        assert "toggleTheme" in resp.text

    def test_login_page(self, client):
        resp = client.get("/login.html")
        assert resp.status_code == 200
        assert "Sign In" in resp.text

    def test_app_css(self, client):
        resp = client.get("/app.css")
        assert resp.status_code == 200
        assert "chat-layout" in resp.text
        assert "data-theme" in resp.text

    def test_app_js(self, client):
        resp = client.get("/app.js")
        assert resp.status_code == 200
        assert "function chatPage()" in resp.text
        assert "function notificationsPage()" in resp.text
        assert "function jobsPage()" in resp.text
        assert "function settingsPage()" in resp.text

    def test_favicon(self, client):
        resp = client.get("/favicon.svg")
        assert resp.status_code == 200


# =============================================================================
# DB Unit Tests
# =============================================================================


class TestConversationsDB:
    """Direct tests on ConversationsDB."""

    def test_create_and_get(self, tmp_path):
        db = ConversationsDB(tmp_path / "test.db")
        conv = db.create("My chat")
        assert conv["title"] == "My chat"
        assert conv["id"]

        fetched = db.get(conv["id"])
        assert fetched is not None
        assert fetched["title"] == "My chat"

    def test_list(self, tmp_path):
        db = ConversationsDB(tmp_path / "test.db")
        db.create("A")
        db.create("B")
        convs = db.list()
        assert len(convs) == 2

    def test_add_message_and_auto_title(self, tmp_path):
        db = ConversationsDB(tmp_path / "test.db")
        conv = db.create()
        assert conv["title"] == "New conversation"

        updated = db.add_message(conv["id"], "user", "How do I deploy to prod?")
        assert updated is not None
        assert len(updated["messages"]) == 1
        assert "deploy" in updated["title"].lower()

    def test_delete(self, tmp_path):
        db = ConversationsDB(tmp_path / "test.db")
        conv = db.create()
        assert db.delete(conv["id"]) is True
        assert db.get(conv["id"]) is None

    def test_delete_nonexistent(self, tmp_path):
        db = ConversationsDB(tmp_path / "test.db")
        assert db.delete("nope") is False


class TestNotificationsDB:
    """Direct tests on NotificationsDB."""

    def test_add_and_list(self, tmp_path):
        db = NotificationsDB(tmp_path / "test.db")
        db.add("cron", "Job failed", "exit code 1", "error")
        notifs = db.list()
        assert len(notifs) == 1
        assert notifs[0]["read"] is False

    def test_unread_count(self, tmp_path):
        db = NotificationsDB(tmp_path / "test.db")
        db.add("test", "N1")
        db.add("test", "N2")
        assert db.unread_count() == 2

    def test_mark_read(self, tmp_path):
        db = NotificationsDB(tmp_path / "test.db")
        n = db.add("test", "Read me")
        assert db.mark_read(n["id"]) is True
        assert db.unread_count() == 0

    def test_mark_all_read(self, tmp_path):
        db = NotificationsDB(tmp_path / "test.db")
        db.add("test", "A")
        db.add("test", "B")
        count = db.mark_all_read()
        assert count == 2
        assert db.unread_count() == 0

    def test_delete(self, tmp_path):
        db = NotificationsDB(tmp_path / "test.db")
        n = db.add("test", "Delete me")
        assert db.delete(n["id"]) is True
        assert len(db.list()) == 0


class TestJobsDB:
    """Direct tests on JobsDB."""

    def test_create_and_get(self, tmp_path):
        db = JobsDB(tmp_path / "test.db")
        job = db.create("build", "shell")
        assert job["status"] == "queued"
        assert db.get(job["id"]) is not None

    def test_lifecycle(self, tmp_path):
        db = JobsDB(tmp_path / "test.db")
        job = db.create("deploy")
        jid = job["id"]

        assert db.start(jid) is True
        started = db.get(jid)
        assert started["status"] == "running"

        assert db.complete(jid, output="done") is True
        completed = db.get(jid)
        assert completed["status"] == "completed"
        assert completed["duration"] >= 0

    def test_failed_job(self, tmp_path):
        db = JobsDB(tmp_path / "test.db")
        job = db.create("broken")
        db.start(job["id"])
        db.complete(job["id"], error="crash")
        result = db.get(job["id"])
        assert result["status"] == "failed"

    def test_list_with_filter(self, tmp_path):
        db = JobsDB(tmp_path / "test.db")
        db.create("a")
        j2 = db.create("b")
        db.start(j2["id"])

        queued = db.list(status="queued")
        running = db.list(status="running")
        assert len(queued) == 1
        assert len(running) == 1

    def test_delete(self, tmp_path):
        db = JobsDB(tmp_path / "test.db")
        job = db.create("tmp")
        assert db.delete(job["id"]) is True
        assert db.get(job["id"]) is None
