"""Tests for channel adapters and registry."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult
from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings

# --- Base classes ---


class TestChannelType:
    def test_enum_values(self):
        assert ChannelType.slack == "slack"
        assert ChannelType.telegram == "telegram"
        assert ChannelType.discord == "discord"
        assert ChannelType.email == "email"

    def test_all_types(self):
        assert len(ChannelType) == 5


class TestSendResult:
    def test_success(self):
        r = SendResult(ok=True, channel="slack", target="#test", message="ts=123")
        assert r.ok
        assert r.error == ""

    def test_failure(self):
        r = SendResult(ok=False, channel="slack", target="#test", error="not_authed")
        assert not r.ok
        assert r.error == "not_authed"


class TestBaseChannel:
    def test_send_not_implemented(self):
        ch = Channel()
        with pytest.raises(NotImplementedError):
            ch.send("#test", "hello")

    def test_test_connection_not_implemented(self):
        ch = Channel()
        with pytest.raises(NotImplementedError):
            ch.test_connection()


# --- Slack adapter ---


class TestSlackChannel:
    def test_requires_token(self):
        from superpowers.channels.slack import SlackChannel
        with pytest.raises(ChannelError, match="token is required"):
            SlackChannel(bot_token="")

    def test_send_success(self):
        from slack_sdk import WebClient

        from superpowers.channels.slack import SlackChannel

        ch = SlackChannel(bot_token="xoxb-test")

        mock_client = MagicMock(spec=WebClient)
        mock_client.chat_postMessage.return_value = {"ts": "1234.5678"}

        with patch("slack_sdk.WebClient", return_value=mock_client):
            result = ch.send("#test", "hello")

        assert result.ok
        assert result.channel == "slack"
        assert "1234.5678" in result.message

    def test_test_connection(self):
        from slack_sdk import WebClient

        from superpowers.channels.slack import SlackChannel

        ch = SlackChannel(bot_token="xoxb-test")

        mock_client = MagicMock(spec=WebClient)
        mock_client.auth_test.return_value = {"user": "testbot", "team": "testteam"}

        with patch("slack_sdk.WebClient", return_value=mock_client):
            result = ch.test_connection()

        assert result.ok
        assert "testbot" in result.message

    def test_send_api_error(self):
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError

        from superpowers.channels.slack import SlackChannel

        ch = SlackChannel(bot_token="xoxb-test")

        mock_client = MagicMock(spec=WebClient)
        mock_resp = MagicMock()
        mock_resp.__getitem__ = lambda s, k: {"error": "channel_not_found"}[k]
        mock_client.chat_postMessage.side_effect = SlackApiError(
            "error", mock_resp,
        )

        with patch("slack_sdk.WebClient", return_value=mock_client):
            result = ch.send("#nonexistent", "hello")

        assert not result.ok
        assert "channel_not_found" in result.error


# --- Telegram adapter ---


class TestTelegramChannel:
    def test_requires_token(self):
        from superpowers.channels.telegram import TelegramChannel
        with pytest.raises(ChannelError, match="token is required"):
            TelegramChannel(bot_token="")

    def test_send_success(self, monkeypatch):
        from superpowers.channels.telegram import TelegramChannel

        ch = TelegramChannel(bot_token="123:ABC")

        response_data = json.dumps({
            "ok": True,
            "result": {"message_id": 42},
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        result = ch.send("123456", "hello")
        assert result.ok
        assert "42" in result.message

    def test_send_api_error(self, monkeypatch):
        from superpowers.channels.telegram import TelegramChannel

        ch = TelegramChannel(bot_token="123:ABC")

        response_data = json.dumps({
            "ok": False,
            "description": "Bad Request: chat not found",
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        result = ch.send("bad_chat", "hello")
        assert not result.ok
        assert "chat not found" in result.error

    def test_test_connection(self, monkeypatch):
        from superpowers.channels.telegram import TelegramChannel

        ch = TelegramChannel(bot_token="123:ABC")

        response_data = json.dumps({
            "ok": True,
            "result": {"username": "test_bot", "id": 123},
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        result = ch.test_connection()
        assert result.ok
        assert "test_bot" in result.message


# --- Discord adapter ---


class TestDiscordChannel:
    def test_requires_token(self):
        from superpowers.channels.discord import DiscordChannel
        with pytest.raises(ChannelError, match="token is required"):
            DiscordChannel(bot_token="")

    def test_send_success(self, monkeypatch):
        from superpowers.channels.discord import DiscordChannel

        ch = DiscordChannel(bot_token="test-token")

        response_data = json.dumps({"id": "999888777"}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        result = ch.send("123456789", "hello")
        assert result.ok
        assert "999888777" in result.message

    def test_test_connection(self, monkeypatch):
        from superpowers.channels.discord import DiscordChannel

        ch = DiscordChannel(bot_token="test-token")

        response_data = json.dumps({
            "username": "TestBot", "discriminator": "1234",
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        result = ch.test_connection()
        assert result.ok
        assert "TestBot" in result.message


# --- Email adapter ---


class TestEmailChannel:
    def test_requires_host(self):
        from superpowers.channels.email import EmailChannel
        with pytest.raises(ChannelError, match="SMTP host is required"):
            EmailChannel(host="", user="u", password="p")

    def test_send_success(self, monkeypatch):
        from superpowers.channels.email import EmailChannel

        ch = EmailChannel(host="smtp.test.com", user="u@test.com", password="pass")

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("smtplib.SMTP", lambda *a, **kw: mock_smtp)

        result = ch.send("dest@test.com", "Test Subject\nBody content")
        assert result.ok
        assert result.message == "sent"

    def test_send_failure(self, monkeypatch):
        import smtplib

        from superpowers.channels.email import EmailChannel

        ch = EmailChannel(host="smtp.test.com", user="u@test.com", password="pass")

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)
        mock_smtp.send_message.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")

        monkeypatch.setattr("smtplib.SMTP", lambda *a, **kw: mock_smtp)

        result = ch.send("dest@test.com", "hello")
        assert not result.ok
        assert "auth failed" in result.error

    def test_test_connection(self, monkeypatch):
        from superpowers.channels.email import EmailChannel

        ch = EmailChannel(host="smtp.test.com", user="u@test.com", password="pass", port=465)

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = lambda s: s
        mock_smtp.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("smtplib.SMTP", lambda *a, **kw: mock_smtp)

        result = ch.test_connection()
        assert result.ok
        assert "smtp.test.com" in result.message


# --- Registry ---


class TestChannelRegistry:
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
    def test_available_none(self, mock_sys):
        mock_sys.platform = "linux"
        reg = ChannelRegistry(self._settings())
        assert reg.available() == []

    def test_available_slack(self):
        reg = ChannelRegistry(self._settings(slack_bot_token="xoxb-test"))
        assert "slack" in reg.available()

    def test_available_telegram(self):
        reg = ChannelRegistry(self._settings(telegram_bot_token="123:ABC"))
        assert "telegram" in reg.available()

    def test_available_discord(self):
        reg = ChannelRegistry(self._settings(discord_bot_token="tok"))
        assert "discord" in reg.available()

    def test_available_email(self):
        reg = ChannelRegistry(self._settings(smtp_host="smtp.test.com", smtp_user="u"))
        assert "email" in reg.available()

    @patch("superpowers.channels.registry.sys")
    def test_available_all(self, mock_sys):
        mock_sys.platform = "darwin"
        reg = ChannelRegistry(self._settings(
            slack_bot_token="x", telegram_bot_token="x",
            discord_bot_token="x", smtp_host="x", smtp_user="x",
        ))
        assert len(reg.available()) == 5

    def test_get_unknown_channel(self):
        reg = ChannelRegistry(self._settings())
        with pytest.raises(ChannelError, match="Unknown channel"):
            reg.get("whatsapp")

    def test_get_caches_instance(self):
        reg = ChannelRegistry(self._settings(slack_bot_token="xoxb-test"))
        ch1 = reg.get("slack")
        ch2 = reg.get("slack")
        assert ch1 is ch2

    def test_get_slack_creates_adapter(self):
        reg = ChannelRegistry(self._settings(slack_bot_token="xoxb-test"))
        ch = reg.get("slack")
        assert ch.channel_type == ChannelType.slack

    def test_get_telegram_creates_adapter(self):
        reg = ChannelRegistry(self._settings(telegram_bot_token="123:ABC"))
        ch = reg.get("telegram")
        assert ch.channel_type == ChannelType.telegram

    def test_get_discord_creates_adapter(self):
        reg = ChannelRegistry(self._settings(discord_bot_token="tok"))
        ch = reg.get("discord")
        assert ch.channel_type == ChannelType.discord

    def test_get_email_creates_adapter(self):
        reg = ChannelRegistry(self._settings(
            smtp_host="smtp.test.com", smtp_user="u", smtp_pass="p",
        ))
        ch = reg.get("email")
        assert ch.channel_type == ChannelType.email
