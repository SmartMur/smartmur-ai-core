"""Tests for demo recording, screenshot generation, and demo output scripts."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"
DEMO_RECORDING = SCRIPTS_DIR / "demo-recording.sh"
GENERATE_SCREENSHOTS = SCRIPTS_DIR / "generate-screenshots.py"
GENERATE_DEMO_OUTPUT = SCRIPTS_DIR / "generate-demo-output.py"


# --- Helpers to import scripts as modules ---

def _import_script(name: str, path: Path):
    """Import a Python script as a module by file path."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def screenshots_mod():
    return _import_script("generate_screenshots", GENERATE_SCREENSHOTS)


@pytest.fixture
def demo_output_mod():
    return _import_script("generate_demo_output", GENERATE_DEMO_OUTPUT)


# =========================================================================
# 1. demo-recording.sh — bash syntax and structure
# =========================================================================


class TestDemoRecordingShell:
    """Tests for scripts/demo-recording.sh."""

    def test_file_exists(self):
        assert DEMO_RECORDING.exists(), "demo-recording.sh must exist"

    def test_valid_bash_syntax(self):
        """bash -n checks syntax without executing."""
        result = subprocess.run(
            ["bash", "-n", str(DEMO_RECORDING)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_is_executable(self):
        import os
        assert os.access(str(DEMO_RECORDING), os.X_OK), "demo-recording.sh must be executable"

    def test_has_shebang(self):
        first_line = DEMO_RECORDING.read_text().splitlines()[0]
        assert first_line.startswith("#!/"), "Must have a shebang line"
        assert "bash" in first_line

    def test_uses_venv_claw(self):
        content = DEMO_RECORDING.read_text()
        assert ".venv/bin/claw" in content, "Must use .venv/bin/claw, not bare claw"

    def test_has_record_flag(self):
        content = DEMO_RECORDING.read_text()
        assert "--record" in content, "Must support --record flag"

    def test_references_asciinema(self):
        content = DEMO_RECORDING.read_text()
        assert "asciinema" in content, "Should reference asciinema"

    def test_has_script_fallback(self):
        content = DEMO_RECORDING.read_text()
        # Should mention script(1) as fallback
        assert "script" in content.lower()

    def test_contains_key_commands(self):
        content = DEMO_RECORDING.read_text()
        for subcmd in ["status", "skill list", "cron list", "agent list", "benchmark list"]:
            assert subcmd in content, f"Must demo '{subcmd}'"


# =========================================================================
# 2. generate-screenshots.py — imports, dashboard check, capture logic
# =========================================================================


class TestGenerateScreenshots:
    """Tests for scripts/generate-screenshots.py."""

    def test_file_exists(self):
        assert GENERATE_SCREENSHOTS.exists()

    def test_imports_cleanly(self, screenshots_mod):
        assert hasattr(screenshots_mod, "main")
        assert hasattr(screenshots_mod, "check_dashboard_running")
        assert hasattr(screenshots_mod, "ROUTES")

    def test_check_dashboard_not_running(self, screenshots_mod):
        """When dashboard is not running, check returns False."""
        result = screenshots_mod.check_dashboard_running("http://127.0.0.1:19999")
        assert result is False

    def test_main_skips_when_dashboard_down(self, screenshots_mod, tmp_path, capsys):
        """main() should exit 1 with a skip message when dashboard is down."""
        rc = screenshots_mod.main([
            "--base-url", "http://127.0.0.1:19999",
            "--output-dir", str(tmp_path),
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "SKIP" in captured.out or "not running" in captured.out.lower()

    def test_output_dir_created(self, screenshots_mod, tmp_path):
        out = tmp_path / "subdir" / "screenshots"
        screenshots_mod.main([
            "--base-url", "http://127.0.0.1:19999",
            "--output-dir", str(out),
        ])
        assert out.exists(), "Output directory should be created even if dashboard is down"

    def test_routes_defined(self, screenshots_mod):
        assert len(screenshots_mod.ROUTES) >= 2
        assert len(screenshots_mod.API_ROUTES) >= 2

    def test_capture_with_urllib_mocked(self, screenshots_mod, tmp_path):
        """Mock urllib to test the capture_with_urllib function."""
        html = b"<html><body>mock</body></html>"
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = html
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            screenshots_mod.capture_with_urllib(
                "http://localhost:8200", tmp_path, None
            )
        # Should have created files for the public routes
        files = list(tmp_path.glob("*"))
        assert len(files) >= 1

    def test_get_auth_token_no_env(self, screenshots_mod):
        """Without DASHBOARD_USER/PASS, should return None."""
        with mock.patch.dict("os.environ", {}, clear=True):
            result = screenshots_mod.get_auth_token("http://localhost:8200")
        assert result is None

    def test_is_executable(self):
        import os
        assert os.access(str(GENERATE_SCREENSHOTS), os.X_OK)


# =========================================================================
# 3. generate-demo-output.py — command capture, file generation
# =========================================================================


class TestGenerateDemoOutput:
    """Tests for scripts/generate-demo-output.py."""

    def test_file_exists(self):
        assert GENERATE_DEMO_OUTPUT.exists()

    def test_imports_cleanly(self, demo_output_mod):
        assert hasattr(demo_output_mod, "main")
        assert hasattr(demo_output_mod, "run_claw")
        assert hasattr(demo_output_mod, "COMMANDS")

    def test_commands_defined(self, demo_output_mod):
        assert len(demo_output_mod.COMMANDS) >= 5
        # Each entry should be (args_list, filename, description)
        for args, fname, desc in demo_output_mod.COMMANDS:
            assert isinstance(args, list)
            assert fname.endswith(".txt")
            assert len(desc) > 0

    def test_run_claw_missing_binary(self, demo_output_mod):
        """Should handle missing binary gracefully."""
        output, rc = demo_output_mod.run_claw("/nonexistent/claw", ["status"])
        assert rc != 0
        assert "ERROR" in output or "not found" in output.lower()

    def test_run_claw_with_mock(self, demo_output_mod):
        """Mock subprocess to test run_claw."""
        mock_result = subprocess.CompletedProcess(
            args=["claw", "status"],
            returncode=0,
            stdout="All systems operational\n",
            stderr="",
        )
        with mock.patch("subprocess.run", return_value=mock_result):
            output, rc = demo_output_mod.run_claw("/fake/claw", ["status"])
        assert rc == 0
        assert "operational" in output

    def test_main_missing_claw(self, demo_output_mod, tmp_path, capsys):
        """main() with nonexistent claw should return 1."""
        rc = demo_output_mod.main([
            "--claw", "/nonexistent/bin/claw",
            "--output-dir", str(tmp_path),
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_main_generates_files(self, demo_output_mod, tmp_path):
        """With mocked subprocess, main() should create output files."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="mock output\n", stderr=""
        )
        # Create a fake claw binary
        fake_claw = tmp_path / "fake_claw"
        fake_claw.write_text("#!/bin/sh\necho mock")
        fake_claw.chmod(0o755)

        with mock.patch("subprocess.run", return_value=mock_result):
            out_dir = tmp_path / "output"
            rc = demo_output_mod.main([
                "--claw", str(fake_claw),
                "--output-dir", str(out_dir),
            ])
        assert rc == 0
        txt_files = list(out_dir.glob("*.txt"))
        assert len(txt_files) >= 5, f"Expected at least 5 .txt files, got {len(txt_files)}"

    def test_generate_header(self, demo_output_mod):
        header = demo_output_mod.generate_header("Test desc", ["status"], "/bin/claw")
        assert "Test desc" in header
        assert "status" in header

    def test_check_command_exists_mock(self, demo_output_mod):
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="help text", stderr=""
        )
        with mock.patch("subprocess.run", return_value=mock_result):
            assert demo_output_mod.check_command_exists("/fake/claw", ["llm", "list"]) is True

    def test_check_command_not_exists(self, demo_output_mod):
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=2, stdout="", stderr="Error: No such command"
        )
        with mock.patch("subprocess.run", return_value=mock_result):
            assert demo_output_mod.check_command_exists("/fake/claw", ["nope"]) is False

    def test_is_executable(self):
        import os
        assert os.access(str(GENERATE_DEMO_OUTPUT), os.X_OK)

    def test_timeout_handling(self, demo_output_mod):
        """run_claw should handle timeouts gracefully."""
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claw", timeout=5)):
            output, rc = demo_output_mod.run_claw("/fake/claw", ["status"], timeout=5)
        assert rc == 1
        assert "TIMEOUT" in output


# =========================================================================
# 4. Directory structure
# =========================================================================


class TestDirectoryStructure:
    """Verify assets directories exist."""

    def test_screenshots_dir_exists(self):
        d = PROJECT_DIR / "assets" / "screenshots"
        assert d.exists() and d.is_dir()

    def test_demo_dir_exists(self):
        d = PROJECT_DIR / "assets" / "demo"
        assert d.exists() and d.is_dir()

    def test_screenshots_gitkeep(self):
        assert (PROJECT_DIR / "assets" / "screenshots" / ".gitkeep").exists()

    def test_demo_gitkeep(self):
        assert (PROJECT_DIR / "assets" / "demo" / ".gitkeep").exists()

    def test_scripts_dir_exists(self):
        assert SCRIPTS_DIR.exists() and SCRIPTS_DIR.is_dir()
