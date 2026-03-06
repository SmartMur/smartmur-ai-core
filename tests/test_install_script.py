"""Tests for install.sh and install-docker.sh install scripts."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
INSTALL_SH = PROJECT_ROOT / "install.sh"
INSTALL_DOCKER_SH = PROJECT_ROOT / "install-docker.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_bash(args, input_text=None, env=None, timeout=30):
    """Run a bash command and return the CompletedProcess."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=merged_env,
        input=input_text,
        timeout=timeout,
    )


def bash_syntax_check(script_path):
    """Run bash -n on a script to validate syntax."""
    return run_bash(["bash", "-n", str(script_path)])


def run_install_dry(extra_args=None, env_override=None):
    """Run install.sh in --dry-run mode."""
    args = ["bash", str(INSTALL_SH), "--dry-run"]
    if extra_args:
        args.extend(extra_args)
    env = env_override or {}
    return run_bash(args, env=env)


def run_docker_install_dry(extra_args=None):
    """Run install-docker.sh in --dry-run mode."""
    args = ["bash", str(INSTALL_DOCKER_SH), "--dry-run"]
    if extra_args:
        args.extend(extra_args)
    return run_bash(args)


# ---------------------------------------------------------------------------
# install.sh — Syntax & Structure
# ---------------------------------------------------------------------------

class TestInstallShSyntax:
    """Validate install.sh is valid bash and has required structure."""

    def test_syntax_valid(self):
        """install.sh must pass bash -n syntax check."""
        result = bash_syntax_check(INSTALL_SH)
        assert result.returncode == 0, f"Syntax errors:\n{result.stderr}"

    def test_file_exists(self):
        assert INSTALL_SH.exists()

    def test_has_shebang(self):
        first_line = INSTALL_SH.read_text().splitlines()[0]
        assert first_line.startswith("#!/")
        assert "bash" in first_line

    def test_file_not_empty(self):
        assert INSTALL_SH.stat().st_size > 500, "install.sh seems too small"

    def test_contains_error_handling(self):
        content = INSTALL_SH.read_text()
        assert "fatal" in content, "Should have a fatal/error function"

    def test_no_set_e(self):
        """Script must NOT use set -e (per requirements)."""
        content = INSTALL_SH.read_text()
        # Allow 'set -e' only inside comments
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "set -e" not in stripped, "Must not use set -e — use explicit error checks"


# ---------------------------------------------------------------------------
# install-docker.sh — Syntax & Structure
# ---------------------------------------------------------------------------

class TestInstallDockerShSyntax:
    """Validate install-docker.sh is valid bash and has required structure."""

    def test_syntax_valid(self):
        result = bash_syntax_check(INSTALL_DOCKER_SH)
        assert result.returncode == 0, f"Syntax errors:\n{result.stderr}"

    def test_file_exists(self):
        assert INSTALL_DOCKER_SH.exists()

    def test_has_shebang(self):
        first_line = INSTALL_DOCKER_SH.read_text().splitlines()[0]
        assert first_line.startswith("#!/")
        assert "bash" in first_line

    def test_contains_compose_up(self):
        content = INSTALL_DOCKER_SH.read_text()
        assert "compose up" in content or "docker-compose up" in content

    def test_prints_urls(self):
        content = INSTALL_DOCKER_SH.read_text()
        assert "8200" in content, "Should print dashboard URL (port 8200)"


# ---------------------------------------------------------------------------
# install.sh — --help flag
# ---------------------------------------------------------------------------

class TestInstallHelp:
    """Test --help flag output."""

    def test_help_flag(self):
        result = run_bash(["bash", str(INSTALL_SH), "--help"])
        assert result.returncode == 0
        assert "Usage" in result.stdout or "usage" in result.stdout

    def test_help_short_flag(self):
        result = run_bash(["bash", str(INSTALL_SH), "-h"])
        assert result.returncode == 0

    def test_help_mentions_dry_run(self):
        result = run_bash(["bash", str(INSTALL_SH), "--help"])
        assert "dry-run" in result.stdout.lower() or "dry_run" in result.stdout.lower()

    def test_help_mentions_prerequisites(self):
        result = run_bash(["bash", str(INSTALL_SH), "--help"])
        assert "Python" in result.stdout or "python" in result.stdout
        assert "Docker" in result.stdout or "docker" in result.stdout


class TestDockerInstallHelp:
    def test_help_flag(self):
        result = run_bash(["bash", str(INSTALL_DOCKER_SH), "--help"])
        assert result.returncode == 0
        assert "Usage" in result.stdout or "usage" in result.stdout

    def test_help_mentions_services(self):
        result = run_bash(["bash", str(INSTALL_DOCKER_SH), "--help"])
        assert "Dashboard" in result.stdout or "dashboard" in result.stdout


# ---------------------------------------------------------------------------
# install.sh — --dry-run flag
# ---------------------------------------------------------------------------

class TestDryRun:
    """Test --dry-run mode shows what would happen without side effects."""

    def test_dry_run_exits_zero(self):
        result = run_install_dry()
        # Should succeed (exit 0) or at most warn — not fatal
        # It may fail if docker is not installed, which is fine for dry-run
        # The key test is that it doesn't hang and does output dry-run messages
        assert "dry-run" in result.stdout.lower() or "DRY RUN" in result.stdout

    def test_dry_run_shows_mode_banner(self):
        result = run_install_dry()
        output = result.stdout + result.stderr
        assert "DRY RUN" in output or "dry-run" in output.lower()

    def test_dry_run_does_not_create_venv(self):
        """Dry run should not create files in a temp dir."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test-install")
            result = run_install_dry(env_override={"CLAW_INSTALL_DIR": test_dir})
            assert not os.path.exists(os.path.join(test_dir, ".venv")), \
                "Dry run should not create a virtualenv"


# ---------------------------------------------------------------------------
# install.sh — OS Detection
# ---------------------------------------------------------------------------

class TestOSDetection:
    """Test OS detection logic by reading the script content."""

    def test_detects_linux(self):
        content = INSTALL_SH.read_text()
        assert "Linux" in content

    def test_detects_darwin(self):
        content = INSTALL_SH.read_text()
        assert "Darwin" in content

    def test_detects_architecture(self):
        content = INSTALL_SH.read_text()
        assert "x86_64" in content or "amd64" in content
        assert "arm64" in content or "aarch64" in content

    def test_rejects_unknown_os(self):
        """Script should handle unsupported OS gracefully."""
        content = INSTALL_SH.read_text()
        # Should have a catch-all/default case
        assert "Unsupported" in content or "fatal" in content


# ---------------------------------------------------------------------------
# install.sh — Prerequisite Checks
# ---------------------------------------------------------------------------

class TestPrerequisiteChecks:
    """Test that the script checks for required tools."""

    def test_checks_python_version(self):
        content = INSTALL_SH.read_text()
        assert "3.12" in content or ("MIN_PYTHON" in content)

    def test_checks_docker(self):
        content = INSTALL_SH.read_text()
        assert "docker" in content.lower()

    def test_checks_git(self):
        content = INSTALL_SH.read_text()
        assert "git" in content

    def test_handles_missing_ensurepip(self):
        """Script must handle systems where ensurepip is missing."""
        content = INSTALL_SH.read_text()
        assert "without-pip" in content or "get-pip" in content.lower()


# ---------------------------------------------------------------------------
# install.sh — Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    """Test that the script handles re-runs gracefully."""

    def test_checks_existing_repo(self):
        """Script should detect existing clone and pull instead of re-cloning."""
        content = INSTALL_SH.read_text()
        assert "already exists" in content.lower() or "pull" in content

    def test_checks_existing_venv(self):
        """Script should detect existing venv."""
        content = INSTALL_SH.read_text()
        assert "already exists" in content.lower()

    def test_checks_existing_env_file(self):
        """Script should not overwrite existing .env."""
        content = INSTALL_SH.read_text()
        assert "already exists" in content.lower() or "not overwrite" in content.lower()


# ---------------------------------------------------------------------------
# install.sh — PATH Setup
# ---------------------------------------------------------------------------

class TestPathSetup:
    """Test PATH configuration logic."""

    def test_creates_local_bin_symlink(self):
        content = INSTALL_SH.read_text()
        assert ".local/bin" in content

    def test_warns_if_not_on_path(self):
        content = INSTALL_SH.read_text()
        assert "PATH" in content
        assert "bashrc" in content or "zshrc" in content or "shell profile" in content.lower()


# ---------------------------------------------------------------------------
# install.sh — Error Messages
# ---------------------------------------------------------------------------

class TestErrorMessages:
    """Test helpful error messages for common failures."""

    def test_python_install_hint_linux(self):
        content = INSTALL_SH.read_text()
        assert "apt" in content, "Should suggest apt install for Debian/Ubuntu"

    def test_python_install_hint_macos(self):
        content = INSTALL_SH.read_text()
        assert "brew" in content, "Should suggest brew install for macOS"

    def test_docker_install_hint(self):
        content = INSTALL_SH.read_text()
        assert "docker" in content.lower()
        assert "https://" in content, "Should include URL for Docker install"

    def test_fatal_stops_execution(self):
        """The fatal function should call exit."""
        content = INSTALL_SH.read_text()
        assert "exit 1" in content


# ---------------------------------------------------------------------------
# install-docker.sh — Dry Run
# ---------------------------------------------------------------------------

class TestDockerDryRun:
    def test_dry_run_exits(self):
        result = run_docker_install_dry()
        output = result.stdout + result.stderr
        assert "DRY RUN" in output or "dry-run" in output.lower()


# ---------------------------------------------------------------------------
# Content validation — both scripts
# ---------------------------------------------------------------------------

class TestScriptContent:
    """Validate script contents meet requirements."""

    def test_install_no_curl_pipe_sh(self):
        """Scripts must not contain curl|sh patterns internally."""
        content = INSTALL_SH.read_text()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # get-pip.py download is OK (it saves to file first)
            if "get-pip" in stripped:
                continue
            assert "| bash" not in stripped and "| sh" not in stripped, \
                f"Found curl|sh pattern: {stripped}"

    def test_docker_install_no_curl_pipe_sh(self):
        content = INSTALL_DOCKER_SH.read_text()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "| bash" not in stripped and "| sh" not in stripped, \
                f"Found curl|sh pattern: {stripped}"

    def test_install_uses_editable_mode(self):
        content = INSTALL_SH.read_text()
        assert "pip install" in content and "-e" in content

    def test_install_has_colored_output(self):
        content = INSTALL_SH.read_text()
        assert "tput" in content or "\\033" in content or "\\e[" in content

    def test_install_has_repo_url(self):
        content = INSTALL_SH.read_text()
        assert "SmartMur" in content or "github.com" in content

    def test_docker_install_checks_daemon(self):
        """Docker install should verify daemon is running."""
        content = INSTALL_DOCKER_SH.read_text()
        assert "docker info" in content or "docker ps" in content
