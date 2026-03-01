"""End-to-end integration tests spanning multiple superpowers subsystems."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from superpowers.channels.base import Channel, ChannelType, SendResult
from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings
from superpowers.credential_rotation import (
    AlertStatus,
    CredentialRotationChecker,
    run_rotation_check,
)
from superpowers.cron_engine import CronEngine, JobType
from superpowers.memory.store import MemoryStore
from superpowers.profiles import ProfileManager
from superpowers.skill_registry import SkillRegistry
from superpowers.workflow.base import StepConfig, StepStatus, StepType, WorkflowConfig
from superpowers.workflow.engine import WorkflowEngine
from superpowers.workflow.loader import WorkflowLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill_dir(base: Path, name: str, script_body: str = "#!/bin/bash\necho ok") -> Path:
    """Create a minimal skill directory with skill.yaml and script."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    script_path = skill_dir / "run.sh"
    script_path.write_text(script_body)
    script_path.chmod(0o755)
    (skill_dir / "skill.yaml").write_text(
        f"name: {name}\n"
        f"version: '1.0'\n"
        f"description: Integration test skill\n"
        f"author: test\n"
        f"script: run.sh\n"
    )
    return skill_dir


class _FakeChannel(Channel):
    """In-memory channel adapter for testing fan-out without real services."""

    def __init__(self, name: str):
        self.channel_type = ChannelType.slack  # arbitrary
        self._name = name
        self.sent: list[tuple[str, str]] = []

    def send(self, target: str, message: str) -> SendResult:
        self.sent.append((target, message))
        return SendResult(ok=True, channel=self._name, target=target, message="delivered")

    def test_connection(self) -> SendResult:
        return SendResult(ok=True, channel=self._name, target="", message="ok")


# ---------------------------------------------------------------------------
# 1. Skill -> Cron pipeline
# ---------------------------------------------------------------------------


class TestSkillCronPipeline:
    """Register a skill, create a cron job of type 'skill', execute it,
    and verify output is logged to disk."""

    def test_skill_runs_via_cron(self, tmp_path: Path):
        # Set up a skill directory with a script that writes a marker
        skills_dir = tmp_path / "skills"
        _make_skill_dir(skills_dir, "ping-test", script_body="#!/bin/bash\necho PING_OK")

        registry = SkillRegistry(skills_dir=skills_dir)
        skills = registry.discover()
        assert len(skills) == 1
        assert skills[0].name == "ping-test"

        # Set up the cron engine in tmp_path
        cron_data = tmp_path / "cron"
        engine = CronEngine(jobs_file=cron_data / "jobs.json", data_dir=cron_data)
        engine.start()

        try:
            # Patch _run_skill so it uses our local registry instead of the global default
            def _run_skill_local(job):
                from superpowers.skill_loader import SkillLoader
                skill = registry.get(job.command)
                loader = SkillLoader()
                result = loader.run(skill, job.args or None)
                return result.stdout + result.stderr, result.returncode

            engine._run_skill = _run_skill_local

            job = engine.add_job(
                name="run-ping",
                schedule="every 1h",
                job_type="skill",
                command="ping-test",
            )
            assert job.job_type == JobType.skill

            # Execute synchronously
            engine._execute_job(job.id)

            updated = engine.get_job(job.id)
            assert updated.last_status == "ok"
            assert updated.last_output_file != ""

            log_content = Path(updated.last_output_file).read_text()
            assert "PING_OK" in log_content
            assert "exit_code: 0" in log_content
        finally:
            engine.stop()


# ---------------------------------------------------------------------------
# 2. Channel -> Profile fan-out
# ---------------------------------------------------------------------------


class TestChannelProfileFanout:
    """Configure a profile with 2 mock channels, send via profile,
    verify both channels received the message."""

    def test_fanout_to_two_channels(self, tmp_path: Path):
        profiles_yaml = tmp_path / "profiles.yaml"
        profiles_yaml.write_text(
            "alerts:\n"
            "  - channel: chan_a\n"
            '    target: "#room-a"\n'
            "  - channel: chan_b\n"
            '    target: "#room-b"\n'
        )

        chan_a = _FakeChannel("chan_a")
        chan_b = _FakeChannel("chan_b")

        mock_registry = MagicMock(spec=ChannelRegistry)
        mock_registry.get.side_effect = lambda name: {"chan_a": chan_a, "chan_b": chan_b}[name]

        pm = ProfileManager(mock_registry, profiles_path=profiles_yaml)

        results = pm.send("alerts", "Backup completed successfully")

        assert len(results) == 2
        assert all(r.ok for r in results)

        # Verify each channel received the message
        assert len(chan_a.sent) == 1
        assert chan_a.sent[0] == ("#room-a", "Backup completed successfully")

        assert len(chan_b.sent) == 1
        assert chan_b.sent[0] == ("#room-b", "Backup completed successfully")


# ---------------------------------------------------------------------------
# 3. Workflow execution
# ---------------------------------------------------------------------------


class TestWorkflowExecution:
    """Load a workflow YAML, execute with real shell steps,
    verify step ordering and result propagation."""

    def test_load_and_run_workflow(self, tmp_path: Path):
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        (wf_dir / "deploy.yaml").write_text(
            "name: deploy\n"
            "description: Test deployment workflow\n"
            "steps:\n"
            "  - name: check\n"
            "    type: shell\n"
            '    command: "echo CHECK_PASS"\n'
            "  - name: build\n"
            "    type: shell\n"
            '    command: "echo BUILD_DONE"\n'
            "    condition: previous.ok\n"
            "  - name: notify\n"
            "    type: shell\n"
            '    command: "echo DEPLOY_COMPLETE"\n'
            "    condition: previous.ok\n"
        )

        loader = WorkflowLoader(wf_dir)
        wf = loader.load("deploy")
        assert wf.name == "deploy"
        assert len(wf.steps) == 3

        engine = WorkflowEngine()
        results = engine.run(wf)

        # All 3 steps should pass in order
        assert len(results) == 3
        assert all(r.status == StepStatus.passed for r in results)
        assert results[0].step_name == "check"
        assert "CHECK_PASS" in results[0].output
        assert results[1].step_name == "build"
        assert "BUILD_DONE" in results[1].output
        assert results[2].step_name == "notify"
        assert "DEPLOY_COMPLETE" in results[2].output

        # Verify ordering: each step's duration is tracked
        for r in results:
            assert r.duration_ms >= 0

    def test_conditional_skip_propagation(self, tmp_path: Path):
        """When a step fails with on_failure=continue, the next step with
        condition=previous.ok should be skipped. A subsequent step with
        on_failure=continue still runs despite the failed flag."""
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        (wf_dir / "fragile.yaml").write_text(
            "name: fragile\n"
            "steps:\n"
            "  - name: break\n"
            "    type: shell\n"
            '    command: "exit 1"\n'
            "    on_failure: continue\n"
            "  - name: should-skip\n"
            "    type: shell\n"
            '    command: "echo NEVER"\n'
            "    condition: previous.ok\n"
            "    on_failure: continue\n"
            "  - name: resilient\n"
            "    type: shell\n"
            '    command: "echo RESILIENT"\n'
            "    on_failure: continue\n"
        )

        loader = WorkflowLoader(wf_dir)
        wf = loader.load("fragile")
        engine = WorkflowEngine()
        results = engine.run(wf)

        assert results[0].status == StepStatus.failed
        assert results[1].status == StepStatus.skipped
        assert results[2].status == StepStatus.passed
        assert "RESILIENT" in results[2].output


# ---------------------------------------------------------------------------
# 4. Memory round-trip
# ---------------------------------------------------------------------------


class TestMemoryRoundTrip:
    """Store a fact via memory store, recall it, verify content matches."""

    def test_remember_and_recall(self, tmp_path: Path):
        store = MemoryStore(db_path=tmp_path / "memory.db")

        entry = store.remember(
            "proxmox-host",
            "192.168.30.100",
            category="fact",
            tags=["infra", "homelab"],
            project="homelab",
        )

        assert entry.id > 0
        assert entry.key == "proxmox-host"

        recalled = store.recall("proxmox-host")
        assert recalled is not None
        assert recalled.value == "192.168.30.100"
        assert recalled.tags == ["infra", "homelab"]
        assert recalled.project == "homelab"

    def test_update_and_recall(self, tmp_path: Path):
        store = MemoryStore(db_path=tmp_path / "memory.db")

        store.remember("db-host", "old.host.local")
        store.remember("db-host", "new.host.local")

        recalled = store.recall("db-host")
        assert recalled.value == "new.host.local"
        assert recalled.access_count >= 1

    def test_search_across_entries(self, tmp_path: Path):
        store = MemoryStore(db_path=tmp_path / "memory.db")

        store.remember("truenas-ip", "192.168.13.69", tags=["infra"])
        store.remember("proxmox-ip", "192.168.30.100", tags=["infra"])
        store.remember("editor-pref", "neovim", category="preference")

        results = store.search("192.168", category="fact")
        assert len(results) == 2

        results = store.search("neovim")
        assert len(results) == 1
        assert results[0].key == "editor-pref"

    def test_forget_removes_entry(self, tmp_path: Path):
        store = MemoryStore(db_path=tmp_path / "memory.db")
        store.remember("temp-key", "temp-value")
        assert store.forget("temp-key") is True
        assert store.recall("temp-key") is None


# ---------------------------------------------------------------------------
# 5. MCP tool registration
# ---------------------------------------------------------------------------


class TestMCPToolRegistration:
    """Import mcp_server, verify all expected tool modules are registered."""

    def test_all_tool_modules_registered(self):
        from mcp.server.fastmcp import FastMCP

        from superpowers.mcp.audit_tools import register as reg_audit
        from superpowers.mcp.browser_tools import register as reg_browser
        from superpowers.mcp.channels_tools import register as reg_channels
        from superpowers.mcp.cron_tools import register as reg_cron
        from superpowers.mcp.memory_tools import register as reg_memory
        from superpowers.mcp.skill_tools import register as reg_skills
        from superpowers.mcp.ssh_tools import register as reg_ssh
        from superpowers.mcp.vault_tools import register as reg_vault
        from superpowers.mcp.workflow_tools import register as reg_workflow

        mcp = FastMCP("integration-test")
        registrars = [
            reg_channels, reg_ssh, reg_memory, reg_browser,
            reg_workflow, reg_cron, reg_skills, reg_audit, reg_vault,
        ]
        for reg_fn in registrars:
            reg_fn(mcp)

        registered_tools = list(mcp._tool_manager._tools.keys())
        assert len(registered_tools) > 0

        # Verify the main mcp_server module wires everything together
        from superpowers import mcp_server
        assert mcp_server.mcp is not None
        main_tools = list(mcp_server.mcp._tool_manager._tools.keys())
        assert len(main_tools) >= 9  # at least one tool per module

    def test_expected_tool_names_present(self):
        from superpowers import mcp_server

        tool_names = set(mcp_server.mcp._tool_manager._tools.keys())

        # Spot-check key tools from each module
        expected_subsets = [
            "remember",
            "recall",
            "audit_tail",
            "list_workflows",
        ]
        for name in expected_subsets:
            assert name in tool_names, f"Expected tool '{name}' not found in MCP server"


# ---------------------------------------------------------------------------
# 6. Credential rotation -> notification
# ---------------------------------------------------------------------------


class TestCredentialRotationNotification:
    """Set up a vault key with expired rotation policy, run check,
    verify alert is generated and notification is sent."""

    def test_expired_key_triggers_alert_and_notification(self, tmp_path: Path):
        policies_path = tmp_path / "policies.yaml"
        checker = CredentialRotationChecker(policies_path=policies_path)
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)

        # Set a short rotation policy and mark it as rotated long ago
        checker.set_policy("prod-api-key", 30)
        checker.mark_rotated("prod-api-key", now - timedelta(days=45))

        # The key is 45 days old with a 30-day policy -> expired
        alert = checker.check_key("prod-api-key", now)
        assert alert.status == AlertStatus.expired
        assert alert.age_days == 45

        # Now run the full rotation check with mocked vault and profile manager
        vault = MagicMock()
        vault.list_keys.return_value = ["prod-api-key"]

        pm = MagicMock()
        pm.send.return_value = []

        settings = MagicMock()
        settings.data_dir = tmp_path

        alerts = run_rotation_check(
            settings,
            profile="critical",
            vault=vault,
            checker=checker,
            profile_manager=pm,
            now=now,
        )

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.expired
        assert alerts[0].key == "prod-api-key"

        # Verify notification was sent
        pm.send.assert_called_once()
        call_args = pm.send.call_args
        assert call_args[0][0] == "critical"
        assert "prod-api-key" in call_args[0][1]

    def test_fresh_key_no_notification(self, tmp_path: Path):
        policies_path = tmp_path / "policies.yaml"
        checker = CredentialRotationChecker(policies_path=policies_path)
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)

        checker.set_policy("fresh-key", 90)
        checker.mark_rotated("fresh-key", now - timedelta(days=5))

        vault = MagicMock()
        vault.list_keys.return_value = ["fresh-key"]

        pm = MagicMock()
        settings = MagicMock()
        settings.data_dir = tmp_path

        alerts = run_rotation_check(
            settings,
            vault=vault,
            checker=checker,
            profile_manager=pm,
            now=now,
        )

        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.ok
        pm.send.assert_not_called()

    def test_multiple_keys_mixed_status(self, tmp_path: Path):
        policies_path = tmp_path / "policies.yaml"
        checker = CredentialRotationChecker(policies_path=policies_path)
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)

        checker.set_policy("old-key", 30)
        checker.mark_rotated("old-key", now - timedelta(days=60))

        checker.set_policy("new-key", 90)
        checker.mark_rotated("new-key", now - timedelta(days=2))

        vault = MagicMock()
        vault.list_keys.return_value = ["new-key", "old-key"]

        pm = MagicMock()
        pm.send.return_value = []
        settings = MagicMock()
        settings.data_dir = tmp_path

        alerts = run_rotation_check(
            settings,
            profile="critical",
            vault=vault,
            checker=checker,
            profile_manager=pm,
            now=now,
        )

        statuses = {a.key: a.status for a in alerts}
        assert statuses["new-key"] == AlertStatus.ok
        assert statuses["old-key"] == AlertStatus.expired

        # Notification should be sent because at least one key is expired
        pm.send.assert_called_once()
