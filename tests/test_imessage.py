"""Tests for iMessage channel adapter."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from superpowers.channels.base import ChannelType
from superpowers.channels.imessage import IMessageChannel
from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings


class TestIMessageChannel:
    def test_channel_type(self):
        ch = IMessageChannel()
        assert ch.channel_type == ChannelType.imessage

    @patch("superpowers.channels.imessage.sys")
    def test_send_not_macos(self, mock_sys):
        mock_sys.platform = "linux"
        ch = IMessageChannel()
        result = ch.send("+15551234567", "hello")
        assert not result.ok
        assert "requires macOS" in result.error

    @patch("superpowers.channels.imessage.sys")
    @patch("subprocess.run")
    def test_send_success(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        ch = IMessageChannel()
        result = ch.send("+15551234567", "hello")
        assert result.ok
        assert result.channel == "imessage"
        assert result.target == "+15551234567"
        assert result.message == "sent"
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0][0] == "osascript"

    @patch("superpowers.channels.imessage.sys")
    @patch("subprocess.run")
    def test_send_osascript_error(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "osascript", stderr="Messages got an error: buddy not found",
        )
        ch = IMessageChannel()
        result = ch.send("+15551234567", "hello")
        assert not result.ok
        assert "buddy not found" in result.error

    @patch("superpowers.channels.imessage.sys")
    @patch("subprocess.run")
    def test_send_osascript_not_found(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.side_effect = FileNotFoundError("osascript")
        ch = IMessageChannel()
        result = ch.send("+15551234567", "hello")
        assert not result.ok
        assert "osascript not found" in result.error

    @patch("superpowers.channels.imessage.sys")
    @patch("subprocess.run")
    def test_send_timeout(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.side_effect = subprocess.TimeoutExpired("osascript", 30)
        ch = IMessageChannel()
        result = ch.send("+15551234567", "hello")
        assert not result.ok
        assert "timed out" in result.error

    @patch("superpowers.channels.imessage.sys")
    @patch("subprocess.run")
    def test_send_escapes_quotes(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        ch = IMessageChannel()
        ch.send("+15551234567", 'say "hello"')
        script = mock_run.call_args[0][0][2]
        assert '\\"hello\\"' in script

    @patch("superpowers.channels.imessage.sys")
    def test_test_connection_not_macos(self, mock_sys):
        mock_sys.platform = "linux"
        ch = IMessageChannel()
        result = ch.test_connection()
        assert not result.ok
        assert "requires macOS" in result.error

    @patch("superpowers.channels.imessage.sys")
    @patch("subprocess.run")
    def test_test_connection_running(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="true\n",
        )
        ch = IMessageChannel()
        result = ch.test_connection()
        assert result.ok
        assert "running=True" in result.message

    @patch("superpowers.channels.imessage.sys")
    @patch("subprocess.run")
    def test_test_connection_not_running(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="false\n",
        )
        ch = IMessageChannel()
        result = ch.test_connection()
        assert result.ok
        assert "running=False" in result.message

    @patch("superpowers.channels.imessage.sys")
    @patch("subprocess.run")
    def test_test_connection_error(self, mock_run, mock_sys):
        mock_sys.platform = "darwin"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "osascript", stderr="not allowed",
        )
        ch = IMessageChannel()
        result = ch.test_connection()
        assert not result.ok


class TestRegistryIMessage:
    def _settings(self, **overrides) -> Settings:
        defaults = {
            "slack_bot_token": "",
            "telegram_bot_token": "",
            "discord_bot_token": "",
            "smtp_host": "",
            "smtp_user": "",
            "smtp_pass": "",
            "smtp_port": 587,
            "smtp_from": "",
        }
        defaults.update(overrides)
        return Settings(**defaults)

    @patch("superpowers.channels.registry.sys")
    def test_imessage_available_on_darwin(self, mock_sys):
        mock_sys.platform = "darwin"
        reg = ChannelRegistry(self._settings())
        assert "imessage" in reg.available()

    @patch("superpowers.channels.registry.sys")
    def test_imessage_not_available_on_linux(self, mock_sys):
        mock_sys.platform = "linux"
        reg = ChannelRegistry(self._settings())
        assert "imessage" not in reg.available()

    def test_get_imessage_creates_adapter(self):
        reg = ChannelRegistry(self._settings())
        ch = reg.get("imessage")
        assert ch.channel_type == ChannelType.imessage

    def test_get_imessage_caches(self):
        reg = ChannelRegistry(self._settings())
        ch1 = reg.get("imessage")
        ch2 = reg.get("imessage")
        assert ch1 is ch2
