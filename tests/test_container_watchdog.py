"""Tests for container_watchdog module."""

from __future__ import annotations

import subprocess
import threading
from unittest.mock import patch

from superpowers.container_watchdog import (
    ALL_WATCHED,
    WATCHED_CONTAINERS,
    WatchdogState,
    _get_running_containers,
    _has_restart_policy,
    _is_container_running,
    get_status,
    send_down_alert,
    send_recovery_alert,
    send_sweep_alert,
    state,
)


class TestWatchdogState:
    def setup_method(self):
        # Reset shared state between tests
        state.last_alert.clear()

    def test_can_alert_initially(self):
        s = WatchdogState()
        assert s.can_alert("test-container") is True

    def test_cannot_alert_within_cooldown(self):
        s = WatchdogState()
        s.record_alert("test-container")
        assert s.can_alert("test-container") is False

    def test_clear_alert_resets_cooldown(self):
        s = WatchdogState()
        s.record_alert("test-container")
        assert s.can_alert("test-container") is False
        s.clear_alert("test-container")
        assert s.can_alert("test-container") is True

    def test_clear_nonexistent_is_safe(self):
        s = WatchdogState()
        s.clear_alert("nonexistent")  # Should not raise

    def test_thread_safety(self):
        s = WatchdogState()
        errors = []

        def worker(name: str):
            try:
                for _ in range(100):
                    s.can_alert(name)
                    s.record_alert(name)
                    s.clear_alert(name)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"c{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


class TestConfiguration:
    def test_all_watched_populated(self):
        assert len(ALL_WATCHED) > 0

    def test_all_watched_matches_config(self):
        expected = set()
        for containers in WATCHED_CONTAINERS.values():
            expected.update(containers)
        assert ALL_WATCHED == expected

    def test_home_media_containers(self):
        home_media = WATCHED_CONTAINERS.get("/home/ray/docker/home_media", [])
        for name in ["plex", "radarr", "sonarr", "bazarr", "lidarr", "prowlarr"]:
            assert name in home_media, f"{name} missing from home_media watchlist"

    def test_no_duplicate_names(self):
        all_names = []
        for containers in WATCHED_CONTAINERS.values():
            all_names.extend(containers)
        assert len(all_names) == len(set(all_names)), "Duplicate container names in config"


class TestHelpers:
    @patch("superpowers.container_watchdog.subprocess.run")
    def test_is_container_running_true(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="true\n", stderr=""
        )
        assert _is_container_running("test") is True

    @patch("superpowers.container_watchdog.subprocess.run")
    def test_is_container_running_false(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="false\n", stderr=""
        )
        assert _is_container_running("test") is False

    @patch("superpowers.container_watchdog.subprocess.run")
    def test_is_container_running_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=10)
        assert _is_container_running("test") is False

    @patch("superpowers.container_watchdog.subprocess.run")
    def test_has_restart_policy_true(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="unless-stopped\n", stderr=""
        )
        assert _has_restart_policy("test") is True

    @patch("superpowers.container_watchdog.subprocess.run")
    def test_has_restart_policy_no(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="no\n", stderr=""
        )
        assert _has_restart_policy("test") is False

    @patch("superpowers.container_watchdog.subprocess.run")
    def test_get_running_containers(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="plex\nradarr\nsonarr\n", stderr=""
        )
        result = _get_running_containers()
        assert result == {"plex", "radarr", "sonarr"}

    @patch("superpowers.container_watchdog.subprocess.run")
    def test_get_running_containers_empty(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="\n", stderr=""
        )
        result = _get_running_containers()
        assert result == set()

    @patch("superpowers.container_watchdog.subprocess.run")
    def test_get_running_containers_error(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        result = _get_running_containers()
        assert result == set()


class TestAlerts:
    def setup_method(self):
        state.last_alert.clear()

    @patch("superpowers.container_watchdog.notify")
    def test_send_down_alert(self, mock_notify):
        mock_notify.return_value = True
        send_down_alert("plex", reason="test")
        mock_notify.assert_called_once()
        msg = mock_notify.call_args[0][0]
        assert "CONTAINER DOWN" in msg
        assert "plex" in msg

    @patch("superpowers.container_watchdog.notify")
    def test_send_down_alert_cooldown(self, mock_notify):
        mock_notify.return_value = True
        send_down_alert("plex", reason="test")
        send_down_alert("plex", reason="test again")
        # Second call should be suppressed by cooldown
        assert mock_notify.call_count == 1

    @patch("superpowers.container_watchdog.notify")
    def test_send_recovery_alert(self, mock_notify):
        mock_notify.return_value = True
        # First record a down alert
        state.record_alert("plex")
        send_recovery_alert("plex")
        mock_notify.assert_called_once()
        msg = mock_notify.call_args[0][0]
        assert "RECOVERED" in msg
        assert "plex" in msg
        # Should clear cooldown
        assert state.can_alert("plex") is True

    @patch("superpowers.container_watchdog.notify")
    def test_send_sweep_alert(self, mock_notify):
        mock_notify.return_value = True
        send_sweep_alert(["plex", "radarr", "sonarr"])
        mock_notify.assert_called_once()
        msg = mock_notify.call_args[0][0]
        assert "SWEEP" in msg
        assert "3" in msg

    @patch("superpowers.container_watchdog.notify")
    def test_alert_after_recovery_and_new_failure(self, mock_notify):
        mock_notify.return_value = True
        send_down_alert("plex", reason="first")
        assert mock_notify.call_count == 1
        # Recover
        send_recovery_alert("plex")
        assert mock_notify.call_count == 2
        # New failure should alert immediately (cooldown cleared)
        send_down_alert("plex", reason="second")
        assert mock_notify.call_count == 3


class TestGetStatus:
    @patch("superpowers.container_watchdog._get_running_containers")
    def test_all_up(self, mock_running):
        mock_running.return_value = set(ALL_WATCHED)
        status = get_status()
        assert status["down"] == 0
        assert status["up"] == len(ALL_WATCHED)
        assert status["down_containers"] == []

    @patch("superpowers.container_watchdog._get_running_containers")
    def test_some_down(self, mock_running):
        running = set(ALL_WATCHED) - {"plex", "radarr"}
        mock_running.return_value = running
        status = get_status()
        assert status["down"] == 2
        assert "plex" in status["down_containers"]
        assert "radarr" in status["down_containers"]

    @patch("superpowers.container_watchdog._get_running_containers")
    def test_all_down(self, mock_running):
        mock_running.return_value = set()
        status = get_status()
        assert status["down"] == len(ALL_WATCHED)
        assert status["up"] == 0
