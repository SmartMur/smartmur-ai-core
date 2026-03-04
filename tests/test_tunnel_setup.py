"""Tests for the tunnel-setup skill — token validation, .env writing, docker commands."""

from __future__ import annotations

# Import from the skill module directly
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "tunnel-setup"))

import run as tunnel_setup

# ---------------------------------------------------------------------------
# Token Validation
# ---------------------------------------------------------------------------


class TestValidateToken:
    """Tests for validate_token()."""

    def test_valid_token_long_base64(self):
        """A proper Cloudflare tunnel token (150+ chars base64) should pass."""
        token = "eyJhIjoiYWJjZGVmMTIzNDU2Nzg5MCIsInQiOiJhYmNkZWYxMjM0NTY3ODkwIiwicyI6ImFiY2RlZjEyMzQ1Njc4OTAifQ=="
        valid, msg = tunnel_setup.validate_token(token)
        assert valid is True
        assert "valid" in msg.lower()

    def test_valid_token_exactly_50_chars(self):
        """50-char base64 string is the minimum accepted length."""
        token = "A" * 50
        valid, msg = tunnel_setup.validate_token(token)
        assert valid is True

    def test_too_short_49_chars(self):
        """49 chars should be rejected."""
        token = "A" * 49
        valid, msg = tunnel_setup.validate_token(token)
        assert valid is False
        assert "short" in msg.lower()

    def test_too_short_10_chars(self):
        """Very short tokens should fail."""
        token = "abcdefghij"
        valid, msg = tunnel_setup.validate_token(token)
        assert valid is False
        assert "short" in msg.lower()

    def test_empty_string(self):
        """Empty token must be rejected."""
        valid, msg = tunnel_setup.validate_token("")
        assert valid is False
        assert "empty" in msg.lower()

    def test_placeholder_your_tunnel_token_here(self):
        """The default placeholder value must be rejected."""
        valid, msg = tunnel_setup.validate_token("your_tunnel_token_here")
        assert valid is False
        assert "placeholder" in msg.lower()

    def test_placeholder_changeme(self):
        """The 'changeme' placeholder must be rejected."""
        valid, msg = tunnel_setup.validate_token("changeme")
        assert valid is False
        assert "placeholder" in msg.lower()

    def test_invalid_characters(self):
        """Tokens with spaces or special chars should fail."""
        token = "x" * 50 + " has spaces!"
        valid, msg = tunnel_setup.validate_token(token)
        assert valid is False
        assert "invalid" in msg.lower()

    def test_base64_with_special_chars(self):
        """Base64 tokens may contain +, /, =, -, _ and should be accepted."""
        token = "eyJhIjoiMTIzNCIsInQiOiI1Njc4In0=" + "A" * 20 + "-_+/="
        valid, msg = tunnel_setup.validate_token(token)
        assert valid is True


# ---------------------------------------------------------------------------
# .env File Operations
# ---------------------------------------------------------------------------


class TestEnvFileOperations:
    """Tests for reading/writing the .env file."""

    def test_read_env_token_valid(self, tmp_path):
        """Should read the token from a well-formed .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("CLOUDFLARE_TUNNEL_TOKEN=mytoken123\n")
        with patch.object(tunnel_setup, "ENV_FILE", env_file):
            token, msg = tunnel_setup._read_env_token()
            assert token == "mytoken123"
            assert msg == "found"

    def test_read_env_token_missing_file(self, tmp_path):
        """Should report missing file."""
        env_file = tmp_path / ".env"
        with patch.object(tunnel_setup, "ENV_FILE", env_file):
            token, msg = tunnel_setup._read_env_token()
            assert token == ""
            assert "not found" in msg.lower()

    def test_read_env_token_no_token_var(self, tmp_path):
        """Should report when CLOUDFLARE_TUNNEL_TOKEN is absent."""
        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_VAR=value\n")
        with patch.object(tunnel_setup, "ENV_FILE", env_file):
            token, msg = tunnel_setup._read_env_token()
            assert token == ""
            assert "not found" in msg.lower()

    def test_read_env_token_skips_comments(self, tmp_path):
        """Commented-out lines should be ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# CLOUDFLARE_TUNNEL_TOKEN=old_token\nCLOUDFLARE_TUNNEL_TOKEN=real_token\n"
        )
        with patch.object(tunnel_setup, "ENV_FILE", env_file):
            token, msg = tunnel_setup._read_env_token()
            assert token == "real_token"

    def test_read_env_token_strips_quotes(self, tmp_path):
        """Quoted values should be unquoted."""
        env_file = tmp_path / ".env"
        env_file.write_text('CLOUDFLARE_TUNNEL_TOKEN="quoted_token"\n')
        with patch.object(tunnel_setup, "ENV_FILE", env_file):
            token, msg = tunnel_setup._read_env_token()
            assert token == "quoted_token"

    def test_set_token_writes_env_file(self, tmp_path):
        """cmd_set_token should write the token to the .env file."""
        env_file = tmp_path / ".env"
        token = "A" * 60  # valid token
        with (
            patch.object(tunnel_setup, "ENV_FILE", env_file),
            patch.object(tunnel_setup, "cmd_start", return_value=0),
            patch("superpowers.audit.AuditLog.log"),
            patch("superpowers.telegram_notify.notify", return_value=False),
            patch("superpowers.telegram_notify.notify_done", return_value=False),
        ):
            rc = tunnel_setup.cmd_set_token(token)
            assert rc == 0
            content = env_file.read_text()
            assert f"CLOUDFLARE_TUNNEL_TOKEN={token}" in content

    def test_set_token_rejects_invalid(self):
        """cmd_set_token should reject invalid tokens without writing."""
        rc = tunnel_setup.cmd_set_token("too_short")
        assert rc == 2


# ---------------------------------------------------------------------------
# Status / Docker Commands (mocked)
# ---------------------------------------------------------------------------


class TestContainerStatus:
    """Tests for container status checking with mocked docker commands."""

    @patch.object(tunnel_setup, "_run_cmd")
    def test_get_container_status_running(self, mock_cmd):
        """Should parse running container info."""
        mock_cmd.return_value = MagicMock(
            returncode=0,
            stdout='{"running":true,"exit_code":0,"restart_count":0,"status":"running"}',
        )
        info = tunnel_setup._get_container_status()
        assert info["exists"] is True
        assert info["running"] is True
        assert info["status"] == "running"
        assert info["exit_code"] == 0
        assert info["restart_count"] == 0

    @patch.object(tunnel_setup, "_run_cmd")
    def test_get_container_status_not_found(self, mock_cmd):
        """Should handle container not existing."""
        mock_cmd.return_value = MagicMock(returncode=1, stdout="", stderr="No such object")
        info = tunnel_setup._get_container_status()
        assert info["exists"] is False
        assert info["running"] is False
        assert info["status"] == "not_found"

    @patch.object(tunnel_setup, "_run_cmd")
    def test_get_container_status_stopped(self, mock_cmd):
        """Should correctly report a stopped container."""
        mock_cmd.return_value = MagicMock(
            returncode=0,
            stdout='{"running":false,"exit_code":255,"restart_count":12,"status":"exited"}',
        )
        info = tunnel_setup._get_container_status()
        assert info["exists"] is True
        assert info["running"] is False
        assert info["exit_code"] == 255
        assert info["restart_count"] == 12


# ---------------------------------------------------------------------------
# Command Parsing
# ---------------------------------------------------------------------------


class TestCommandParsing:
    """Tests for main() argument dispatch."""

    @patch.object(tunnel_setup, "cmd_status", return_value=0)
    def test_no_args_runs_status(self, mock_status):
        """No arguments should default to status."""
        rc = tunnel_setup.main([])
        assert rc == 0
        mock_status.assert_called_once()

    @patch.object(tunnel_setup, "cmd_status", return_value=0)
    def test_status_subcommand(self, mock_status):
        """Explicit 'status' subcommand."""
        rc = tunnel_setup.main(["status"])
        assert rc == 0
        mock_status.assert_called_once()

    @patch.object(tunnel_setup, "cmd_stop", return_value=0)
    def test_stop_subcommand(self, mock_stop):
        """'stop' subcommand dispatches correctly."""
        rc = tunnel_setup.main(["stop"])
        assert rc == 0
        mock_stop.assert_called_once()

    @patch.object(tunnel_setup, "cmd_start", return_value=0)
    def test_start_subcommand(self, mock_start):
        """'start' subcommand dispatches correctly."""
        rc = tunnel_setup.main(["start"])
        assert rc == 0
        mock_start.assert_called_once()

    @patch.object(tunnel_setup, "cmd_logs", return_value=0)
    def test_logs_subcommand(self, mock_logs):
        """'logs' subcommand dispatches correctly."""
        rc = tunnel_setup.main(["logs"])
        assert rc == 0
        mock_logs.assert_called_once()

    def test_set_token_missing_arg(self):
        """'set-token' without a token should fail with exit code 2."""
        rc = tunnel_setup.main(["set-token"])
        assert rc == 2

    def test_unknown_subcommand(self):
        """Unknown subcommand should return non-zero."""
        rc = tunnel_setup.main(["nonexistent"])
        assert rc != 0

    @patch.object(tunnel_setup, "cmd_help", return_value=0)
    def test_help_subcommand(self, mock_help):
        """'help' subcommand dispatches correctly."""
        tunnel_setup.main(["help"])
        mock_help.assert_called_once()


# ---------------------------------------------------------------------------
# Stop command (mocked docker)
# ---------------------------------------------------------------------------


class TestCmdStop:
    """Tests for cmd_stop with mocked docker."""

    @patch("superpowers.telegram_notify.notify", return_value=False)
    @patch("superpowers.audit.AuditLog.log")
    @patch.object(tunnel_setup, "_run_cmd")
    def test_stop_success(self, mock_cmd, mock_audit, mock_notify):
        """Successful stop should return 0."""
        mock_cmd.return_value = MagicMock(returncode=0, stdout="", stderr="")
        rc = tunnel_setup.cmd_stop()
        assert rc == 0
        mock_cmd.assert_called_once_with(["docker", "stop", tunnel_setup.CONTAINER_NAME])

    @patch.object(tunnel_setup, "_run_cmd")
    def test_stop_failure(self, mock_cmd):
        """Failed stop should return 1."""
        mock_cmd.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error: no such container"
        )
        rc = tunnel_setup.cmd_stop()
        assert rc == 1


# ---------------------------------------------------------------------------
# Logs command (mocked docker)
# ---------------------------------------------------------------------------


class TestCmdLogs:
    """Tests for cmd_logs with mocked docker."""

    @patch.object(tunnel_setup, "_run_cmd")
    def test_logs_success(self, mock_cmd):
        """Should print logs and return 0."""
        mock_cmd.return_value = MagicMock(
            returncode=0,
            stdout="2024-01-01 tunnel connected\n",
            stderr="",
        )
        rc = tunnel_setup.cmd_logs()
        assert rc == 0
        mock_cmd.assert_called_once_with(
            ["docker", "logs", "--tail", "30", tunnel_setup.CONTAINER_NAME],
            timeout=15,
        )

    @patch.object(tunnel_setup, "_run_cmd")
    def test_logs_no_container(self, mock_cmd):
        """Should return 1 when container doesn't exist."""
        mock_cmd.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: no such container",
        )
        rc = tunnel_setup.cmd_logs()
        assert rc == 1
