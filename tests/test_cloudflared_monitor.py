"""Tests for the Cloudflared tunnel monitor — diagnose, fix, report."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from superpowers.cloudflared_monitor import (
    ERROR_PATTERNS,
    CloudflaredMonitor,
    ContainerState,
    DiagnosticResult,
)

# ---------------------------------------------------------------------------
# ContainerState
# ---------------------------------------------------------------------------


class TestContainerState:
    def test_default_state(self):
        s = ContainerState()
        assert not s.running
        assert s.exit_code == 0
        assert s.restart_count == 0

    def test_to_dict(self):
        s = ContainerState(running=True, exit_code=0, restart_count=3, status="running")
        d = s.to_dict()
        assert d["running"] is True
        assert d["restart_count"] == 3


# ---------------------------------------------------------------------------
# DiagnosticResult
# ---------------------------------------------------------------------------


class TestDiagnosticResult:
    def test_default(self):
        r = DiagnosticResult()
        assert r.status == "unknown"
        assert r.issues == []
        assert r.actions_taken == []

    def test_telegram_summary_healthy(self):
        r = DiagnosticResult(status="healthy")
        msg = r.to_telegram_summary()
        assert "HEALTHY" in msg

    def test_telegram_summary_with_issues(self):
        r = DiagnosticResult(
            status="crash_loop",
            issues=["Crash loop detected: 10 restarts"],
            actions_taken=["Stopped container"],
        )
        msg = r.to_telegram_summary()
        assert "CRASH_LOOP" in msg
        assert "Crash loop" in msg

    def test_telegram_summary_user_action(self):
        r = DiagnosticResult(
            status="down",
            needs_user_action=True,
            user_action_message="Provide a real tunnel token",
        )
        msg = r.to_telegram_summary()
        assert "User action required" in msg


# ---------------------------------------------------------------------------
# Error patterns
# ---------------------------------------------------------------------------


class TestErrorPatterns:
    def test_invalid_token_pattern(self):
        assert ERROR_PATTERNS["invalid_token"].search("Error: invalid token provided")

    def test_placeholder_token_pattern(self):
        assert ERROR_PATTERNS["placeholder_token"].search("token=your_tunnel_token_here")

    def test_network_error_pattern(self):
        assert ERROR_PATTERNS["network_error"].search("dial tcp: connection refused")

    def test_dns_pattern(self):
        assert ERROR_PATTERNS["network_error"].search("DNS resolution failed")

    def test_cert_pattern(self):
        assert ERROR_PATTERNS["cert_error"].search("TLS certificate error")


# ---------------------------------------------------------------------------
# CloudflaredMonitor — token check
# ---------------------------------------------------------------------------


class TestTokenCheck:
    def test_valid_token(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('TUNNEL_TOKEN="eyJhIjoiYWJjZGVmMTIzNDU2Nzg5MGFiY2RlZiJ9"\n')
        m = CloudflaredMonitor(compose_dir=tmp_path)
        valid, msg = m.check_env_token()
        assert valid
        assert "valid" in msg.lower()

    def test_placeholder_token(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TUNNEL_TOKEN=your_tunnel_token_here\n")
        m = CloudflaredMonitor(compose_dir=tmp_path)
        valid, msg = m.check_env_token()
        assert not valid
        assert "placeholder" in msg.lower()

    def test_missing_env_file(self, tmp_path):
        m = CloudflaredMonitor(compose_dir=tmp_path)
        valid, msg = m.check_env_token()
        assert not valid
        assert "not found" in msg.lower()

    def test_empty_token(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TUNNEL_TOKEN=\n")
        m = CloudflaredMonitor(compose_dir=tmp_path)
        valid, msg = m.check_env_token()
        assert not valid

    def test_short_token(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TUNNEL_TOKEN=abc123\n")
        m = CloudflaredMonitor(compose_dir=tmp_path)
        valid, msg = m.check_env_token()
        assert not valid
        assert "short" in msg.lower()

    def test_no_token_var(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_VAR=something\n")
        m = CloudflaredMonitor(compose_dir=tmp_path)
        valid, msg = m.check_env_token()
        assert not valid
        assert "no tunnel token" in msg.lower()

    def test_quoted_token(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TUNNEL_TOKEN='eyJhIjoiYWJjZGVmMTIzNDU2Nzg5MGFiY2RlZiJ9'\n")
        m = CloudflaredMonitor(compose_dir=tmp_path)
        valid, msg = m.check_env_token()
        assert valid


# ---------------------------------------------------------------------------
# CloudflaredMonitor — diagnose
# ---------------------------------------------------------------------------


class TestDiagnose:
    def test_not_found(self):
        m = CloudflaredMonitor()
        state = ContainerState(status="not_found")
        diag = m.diagnose(state)
        assert diag.status == "down"
        assert any("not found" in i.lower() for i in diag.issues)

    def test_inspect_failed(self):
        m = CloudflaredMonitor()
        state = ContainerState(status="inspect_failed")
        diag = m.diagnose(state)
        assert diag.status == "unknown"

    def test_healthy_running(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('TUNNEL_TOKEN="eyJhIjoiYWJjZGVmMTIzNDU2Nzg5MGFiY2RlZiJ9"\n')
        m = CloudflaredMonitor(compose_dir=tmp_path)
        state = ContainerState(running=True, status="running", restart_count=0)
        diag = m.diagnose(state)
        assert diag.status == "healthy"

    def test_crash_loop(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('TUNNEL_TOKEN="eyJhIjoiYWJjZGVmMTIzNDU2Nzg5MGFiY2RlZiJ9"\n')
        m = CloudflaredMonitor(compose_dir=tmp_path)
        state = ContainerState(running=False, status="exited", restart_count=10, exit_code=255)
        diag = m.diagnose(state)
        assert diag.status == "crash_loop"

    def test_bad_token_diagnosis(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TUNNEL_TOKEN=your_tunnel_token_here\n")
        m = CloudflaredMonitor(compose_dir=tmp_path)
        state = ContainerState(running=False, status="exited", exit_code=255)
        diag = m.diagnose(state)
        assert diag.needs_user_action
        assert "cloudflare" in diag.user_action_message.lower()

    def test_log_pattern_detection(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('TUNNEL_TOKEN="eyJhIjoiYWJjZGVmMTIzNDU2Nzg5MGFiY2RlZiJ9"\n')
        m = CloudflaredMonitor(compose_dir=tmp_path)
        state = ContainerState(
            running=True,
            status="running",
            error_log="Error: DNS resolution failed for tunnel endpoint",
        )
        diag = m.diagnose(state)
        assert any("network_error" in i for i in diag.issues)


# ---------------------------------------------------------------------------
# CloudflaredMonitor — apply_fixes
# ---------------------------------------------------------------------------


class TestApplyFixes:
    @patch.object(CloudflaredMonitor, "_run_cmd")
    def test_stop_crash_loop_with_bad_token(self, mock_cmd):
        mock_cmd.return_value = MagicMock(returncode=0)
        m = CloudflaredMonitor()
        state = ContainerState(running=False, restart_count=10)
        diag = DiagnosticResult(status="crash_loop", needs_user_action=True)
        result = m.apply_fixes(state, diag)
        mock_cmd.assert_called_once()
        assert any("stopped" in a.lower() for a in result.actions_taken)

    @patch.object(CloudflaredMonitor, "_run_cmd")
    def test_restart_on_network_error(self, mock_cmd):
        mock_cmd.return_value = MagicMock(returncode=0)
        m = CloudflaredMonitor()
        state = ContainerState(running=False, restart_count=1)
        diag = DiagnosticResult(status="down", issues=["Log pattern match: network_error"])
        result = m.apply_fixes(state, diag)
        assert any("restart" in a.lower() for a in result.actions_taken)

    @patch.object(CloudflaredMonitor, "_run_cmd")
    def test_no_fix_when_healthy(self, mock_cmd):
        m = CloudflaredMonitor()
        state = ContainerState(running=True, restart_count=0)
        diag = DiagnosticResult(status="healthy")
        result = m.apply_fixes(state, diag)
        mock_cmd.assert_not_called()
        assert not result.actions_taken


# ---------------------------------------------------------------------------
# CloudflaredMonitor — save_status
# ---------------------------------------------------------------------------


class TestSaveStatus:
    @patch("superpowers.cloudflared_monitor.get_data_dir")
    def test_saves_status_json(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path
        m = CloudflaredMonitor()
        state = ContainerState(running=True, status="running")
        diag = DiagnosticResult(status="healthy")
        path = m.save_status(state, diag)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["diagnosis"]["status"] == "healthy"

    @patch("superpowers.cloudflared_monitor.get_data_dir")
    def test_appends_incident_log(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path
        m = CloudflaredMonitor()
        state = ContainerState(running=False)
        diag = DiagnosticResult(status="down", issues=["Container not found"])
        m.save_status(state, diag)
        incident_file = tmp_path / "cloudflared-monitor" / "incident-log.jsonl"
        assert incident_file.exists()
        lines = incident_file.read_text().strip().splitlines()
        assert len(lines) == 1

    @patch("superpowers.cloudflared_monitor.get_data_dir")
    def test_no_incident_log_when_clean(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path
        m = CloudflaredMonitor()
        state = ContainerState(running=True)
        diag = DiagnosticResult(status="healthy")
        m.save_status(state, diag)
        incident_file = tmp_path / "cloudflared-monitor" / "incident-log.jsonl"
        assert not incident_file.exists()
