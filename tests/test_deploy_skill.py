"""Tests for the deploy skill — skills/deploy/run.py."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import deploy skill module by absolute path to avoid name collisions
_deploy_run = Path(__file__).resolve().parent.parent / "skills" / "deploy" / "run.py"
_spec = importlib.util.spec_from_file_location("deploy_run", _deploy_run)
deploy_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deploy_mod)


class TestGitPull:
    def test_git_pull_success(self):
        fake = subprocess.CompletedProcess(
            args=["git", "pull", "--ff-only"],
            returncode=0,
            stdout="Already up to date.\n",
            stderr="",
        )
        with patch.object(deploy_mod, "_run_cmd", return_value=fake) as mock:
            ok, detail = deploy_mod.step_git_pull()
            assert ok is True
            assert "Already up to date" in detail
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert args == ["git", "pull", "--ff-only"]

    def test_git_pull_failure(self):
        fake = subprocess.CompletedProcess(
            args=["git", "pull", "--ff-only"],
            returncode=1,
            stdout="",
            stderr="fatal: Not a git repository",
        )
        with patch.object(deploy_mod, "_run_cmd", return_value=fake):
            ok, detail = deploy_mod.step_git_pull()
            assert ok is False
            assert "Not a git repository" in detail

    def test_git_pull_uses_ff_only(self):
        """Ensure we never do a merge pull — ff-only is mandatory."""
        fake = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr=""
        )
        with patch.object(deploy_mod, "_run_cmd", return_value=fake) as mock:
            deploy_mod.step_git_pull()
            args = mock.call_args[0][0]
            assert "--ff-only" in args


class TestDockerBuild:
    def test_docker_build_success(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Successfully built abc123", stderr=""
        )
        with patch.object(deploy_mod, "_run_cmd", return_value=fake):
            ok, detail = deploy_mod.step_docker_build()
            assert ok is True

    def test_docker_build_failure(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="ERROR: failed to build"
        )
        with patch.object(deploy_mod, "_run_cmd", return_value=fake):
            ok, detail = deploy_mod.step_docker_build()
            assert ok is False
            assert "failed to build" in detail

    def test_docker_build_command_uses_no_cache(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr=""
        )
        with patch.object(deploy_mod, "_run_cmd", return_value=fake) as mock:
            deploy_mod.step_docker_build()
            args = mock.call_args[0][0]
            assert "--no-cache" in args
            assert "docker" in args
            assert "compose" in args
            assert "build" in args


class TestDockerUp:
    def test_docker_up_success(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Container started", stderr=""
        )
        with patch.object(deploy_mod, "_run_cmd", return_value=fake):
            ok, detail = deploy_mod.step_docker_up()
            assert ok is True

    def test_docker_up_failure(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="port already in use"
        )
        with patch.object(deploy_mod, "_run_cmd", return_value=fake):
            ok, detail = deploy_mod.step_docker_up()
            assert ok is False


class TestHealthCheck:
    def test_health_check_success(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status":"ok"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            ok, body = deploy_mod.step_health_check(
                url="http://localhost:8200/health", retries=1
            )
            assert ok is True
            assert "ok" in body

    def test_health_check_failure_after_retries(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionError("refused")):
            ok, detail = deploy_mod.step_health_check(
                url="http://localhost:9999/health", retries=1
            )
            assert ok is False
            assert "failed" in detail

    def test_health_check_retries(self):
        """Health check retries the configured number of times."""
        call_count = 0

        def failing_urlopen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("refused")

        with patch("urllib.request.urlopen", side_effect=failing_urlopen):
            with patch("time.sleep"):
                ok, _ = deploy_mod.step_health_check(
                    url="http://localhost:9999/health", retries=3
                )
                assert ok is False
                assert call_count == 3


class TestDeployPipeline:
    def _mock_step(self, ok: bool, detail: str = "ok"):
        return lambda *a, **kw: (ok, detail)

    def test_deploy_success_returns_0(self):
        with (
            patch.object(deploy_mod, "step_git_pull", self._mock_step(True)),
            patch.object(deploy_mod, "step_pip_install", self._mock_step(True)),
            patch.object(deploy_mod, "step_docker_build", self._mock_step(True)),
            patch.object(deploy_mod, "step_docker_up", self._mock_step(True)),
            patch.object(deploy_mod, "step_health_check", self._mock_step(True)),
            patch.object(deploy_mod, "step_quick_tests", self._mock_step(True)),
            patch.object(deploy_mod, "_notify_start"),
            patch.object(deploy_mod, "_notify_done"),
            patch.object(deploy_mod, "_audit_log"),
        ):
            assert deploy_mod.deploy() == 0

    def test_deploy_git_fail_returns_2(self):
        with (
            patch.object(deploy_mod, "step_git_pull", self._mock_step(False, "conflict")),
            patch.object(deploy_mod, "_notify_start"),
            patch.object(deploy_mod, "_notify_error"),
            patch.object(deploy_mod, "_audit_log"),
        ):
            assert deploy_mod.deploy() == 2

    def test_deploy_health_fail_returns_1(self):
        with (
            patch.object(deploy_mod, "step_git_pull", self._mock_step(True)),
            patch.object(deploy_mod, "step_pip_install", self._mock_step(True)),
            patch.object(deploy_mod, "step_docker_build", self._mock_step(True)),
            patch.object(deploy_mod, "step_docker_up", self._mock_step(True)),
            patch.object(deploy_mod, "step_health_check", self._mock_step(False, "timeout")),
            patch.object(deploy_mod, "_notify_start"),
            patch.object(deploy_mod, "_notify_error"),
            patch.object(deploy_mod, "_audit_log"),
        ):
            assert deploy_mod.deploy() == 1

    def test_deploy_test_fail_returns_2(self):
        with (
            patch.object(deploy_mod, "step_git_pull", self._mock_step(True)),
            patch.object(deploy_mod, "step_pip_install", self._mock_step(True)),
            patch.object(deploy_mod, "step_docker_build", self._mock_step(True)),
            patch.object(deploy_mod, "step_docker_up", self._mock_step(True)),
            patch.object(deploy_mod, "step_health_check", self._mock_step(True)),
            patch.object(deploy_mod, "step_quick_tests", self._mock_step(False, "1 failed")),
            patch.object(deploy_mod, "_notify_start"),
            patch.object(deploy_mod, "_notify_error"),
            patch.object(deploy_mod, "_audit_log"),
        ):
            assert deploy_mod.deploy() == 2
