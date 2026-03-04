"""Tests for notification profiles."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from superpowers.channels.base import ChannelError, SendResult
from superpowers.channels.registry import ChannelRegistry
from superpowers.profiles import NotificationProfile, ProfileManager, ProfileTarget

# --- Profile loading ---


class TestProfileManager:
    def test_load_empty_file(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("")

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)
        assert pm.list_profiles() == []

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.yaml"

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)
        assert pm.list_profiles() == []

    def test_load_single_profile(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("""
critical:
  - channel: slack
    target: "#alerts"
  - channel: telegram
    target: "123456"
""")

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)

        profiles = pm.list_profiles()
        assert len(profiles) == 1
        assert profiles[0].name == "critical"
        assert len(profiles[0].targets) == 2
        assert profiles[0].targets[0].channel == "slack"
        assert profiles[0].targets[0].target == "#alerts"
        assert profiles[0].targets[1].channel == "telegram"

    def test_load_multiple_profiles(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("""
critical:
  - channel: slack
    target: "#alerts"
info:
  - channel: slack
    target: "#general"
daily:
  - channel: email
    target: admin@test.com
""")

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)
        assert len(pm.list_profiles()) == 3

    def test_load_ignores_invalid_entries(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("""
valid:
  - channel: slack
    target: "#test"
invalid_string: "not a list"
invalid_entries:
  - just_a_string
  - channel: slack
    target: "#ok"
""")

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)

        profiles = {p.name: p for p in pm.list_profiles()}
        assert "valid" in profiles
        assert len(profiles["valid"].targets) == 1
        assert "invalid_string" not in profiles
        assert "invalid_entries" in profiles
        assert len(profiles["invalid_entries"].targets) == 1

    def test_load_corrupt_yaml(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("{{{{not yaml}}")

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)
        assert pm.list_profiles() == []

    def test_get_profile(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("""
alerts:
  - channel: slack
    target: "#alerts"
""")

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)

        p = pm.get("alerts")
        assert p.name == "alerts"
        assert len(p.targets) == 1

    def test_get_missing_profile(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("")

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)

        with pytest.raises(KeyError, match="Profile not found"):
            pm.get("nonexistent")


# --- Profile dispatch ---


class TestProfileDispatch:
    def test_send_fans_out(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("""
alerts:
  - channel: slack
    target: "#alerts"
  - channel: telegram
    target: "123456"
""")

        mock_slack = MagicMock()
        mock_slack.send.return_value = SendResult(ok=True, channel="slack", target="#alerts")

        mock_telegram = MagicMock()
        mock_telegram.send.return_value = SendResult(ok=True, channel="telegram", target="123456")

        reg = MagicMock(spec=ChannelRegistry)
        reg.get.side_effect = lambda name: {"slack": mock_slack, "telegram": mock_telegram}[name]

        pm = ProfileManager(reg, profiles_path=path)
        results = pm.send("alerts", "test message")

        assert len(results) == 2
        assert all(r.ok for r in results)
        mock_slack.send.assert_called_once_with("#alerts", "test message")
        mock_telegram.send.assert_called_once_with("123456", "test message")

    def test_send_partial_failure(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("""
mixed:
  - channel: slack
    target: "#test"
  - channel: discord
    target: "999"
""")

        mock_slack = MagicMock()
        mock_slack.send.return_value = SendResult(ok=True, channel="slack", target="#test")

        reg = MagicMock(spec=ChannelRegistry)
        reg.get.side_effect = lambda name: (
            {
                "slack": mock_slack,
            }.get(name)
            or (_ for _ in ()).throw(ChannelError("Discord not configured"))
        )

        pm = ProfileManager(reg, profiles_path=path)
        results = pm.send("mixed", "hello")

        assert len(results) == 2
        assert results[0].ok
        assert not results[1].ok
        assert "not configured" in results[1].error

    def test_send_missing_profile(self, tmp_path):
        path = tmp_path / "profiles.yaml"
        path.write_text("")

        reg = MagicMock(spec=ChannelRegistry)
        pm = ProfileManager(reg, profiles_path=path)

        with pytest.raises(KeyError):
            pm.send("ghost", "hello")


# --- Dataclass tests ---


class TestProfileDataclasses:
    def test_profile_target(self):
        t = ProfileTarget(channel="slack", target="#test")
        assert t.channel == "slack"
        assert t.target == "#test"

    def test_notification_profile(self):
        p = NotificationProfile(
            name="test",
            targets=[ProfileTarget(channel="slack", target="#x")],
        )
        assert p.name == "test"
        assert len(p.targets) == 1

    def test_notification_profile_defaults(self):
        p = NotificationProfile(name="empty")
        assert p.targets == []
