"""Tests for Telegram webhook endpoint, secret validation, typing, and reactions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from msg_gateway.telegram.api import ApiResponse, TelegramApi
from msg_gateway.telegram.types import Update
from msg_gateway.telegram.webhook import WebhookHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update_dict(
    text: str = "hello",
    chat_id: int = 100,
    message_id: int = 1,
    update_id: int = 12345,
) -> dict:
    """Build a minimal Telegram Update dict."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": 42, "is_bot": False, "first_name": "Alice"},
            "text": text,
            "date": 1700000000,
        },
    }


def _make_callback_update_dict(
    data: str = "mode:chat",
    chat_id: int = 100,
    update_id: int = 12346,
) -> dict:
    """Build a Telegram Update dict with a callback_query."""
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "cb_123",
            "from": {"id": 42, "is_bot": False, "first_name": "Alice"},
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id, "type": "private"},
                "text": "old message",
                "date": 1700000000,
            },
            "data": data,
        },
    }


# ---------------------------------------------------------------------------
# WebhookHandler — Secret Validation
# ---------------------------------------------------------------------------


class TestWebhookSecretValidation:
    def test_no_secret_configured_accepts_all(self):
        handler = WebhookHandler(secret_token="")
        assert handler.validate_secret("") is True
        assert handler.validate_secret("anything") is True

    def test_secret_configured_rejects_empty(self):
        handler = WebhookHandler(secret_token="my-secret-123")
        assert handler.validate_secret("") is False

    def test_secret_configured_rejects_wrong_token(self):
        handler = WebhookHandler(secret_token="my-secret-123")
        assert handler.validate_secret("wrong-token") is False

    def test_secret_configured_accepts_correct_token(self):
        handler = WebhookHandler(secret_token="my-secret-123")
        assert handler.validate_secret("my-secret-123") is True

    def test_has_secret_property(self):
        assert WebhookHandler(secret_token="").has_secret is False
        assert WebhookHandler(secret_token="abc").has_secret is True

    def test_secret_is_case_sensitive(self):
        handler = WebhookHandler(secret_token="MySecret")
        assert handler.validate_secret("mysecret") is False
        assert handler.validate_secret("MYSECRET") is False
        assert handler.validate_secret("MySecret") is True


# ---------------------------------------------------------------------------
# WebhookHandler — Update Processing
# ---------------------------------------------------------------------------


class TestWebhookProcessUpdate:
    def test_process_empty_data_returns_false(self):
        handler = WebhookHandler()
        assert handler.process_update({}) is False

    def test_process_none_data_returns_false(self):
        handler = WebhookHandler()
        assert handler.process_update(None) is False

    def test_process_valid_update_calls_handler(self):
        mock_handler = MagicMock()
        handler = WebhookHandler(update_handler=mock_handler)

        data = _make_update_dict(text="test message")
        result = handler.process_update(data)

        assert result is True
        mock_handler.assert_called_once()
        update_arg = mock_handler.call_args[0][0]
        assert isinstance(update_arg, Update)
        assert update_arg.update_id == 12345

    def test_process_update_without_handler_returns_false(self):
        handler = WebhookHandler()
        data = _make_update_dict()
        assert handler.process_update(data) is False

    def test_process_update_handler_exception_returns_false(self):
        mock_handler = MagicMock(side_effect=RuntimeError("boom"))
        handler = WebhookHandler(update_handler=mock_handler)
        data = _make_update_dict()
        assert handler.process_update(data) is False

    def test_process_callback_query_update(self):
        mock_handler = MagicMock()
        handler = WebhookHandler(update_handler=mock_handler)
        data = _make_callback_update_dict()
        result = handler.process_update(data)
        assert result is True
        update_arg = mock_handler.call_args[0][0]
        assert update_arg.callback_query is not None


# ---------------------------------------------------------------------------
# FastAPI Webhook Endpoint Tests
# ---------------------------------------------------------------------------


class TestWebhookEndpoint:
    """Test the /webhook/telegram FastAPI route."""

    @pytest.fixture
    def client(self):
        """Create a test client with a mock poller registered."""
        from fastapi.testclient import TestClient

        from msg_gateway.app import app, set_telegram_poller

        # Create a mock poller with a webhook handler
        mock_poller = MagicMock()
        mock_handler = WebhookHandler(
            secret_token="test-secret",
            update_handler=MagicMock(),
        )
        mock_poller.webhook_handler = mock_handler
        set_telegram_poller(mock_poller)

        client = TestClient(app)
        yield client

        # Cleanup
        set_telegram_poller(None)

    @pytest.fixture
    def client_no_secret(self):
        """Create a test client with no webhook secret configured."""
        from fastapi.testclient import TestClient

        from msg_gateway.app import app, set_telegram_poller

        mock_poller = MagicMock()
        mock_handler = WebhookHandler(
            secret_token="",
            update_handler=MagicMock(),
        )
        mock_poller.webhook_handler = mock_handler
        set_telegram_poller(mock_poller)

        client = TestClient(app)
        yield client

        set_telegram_poller(None)

    def test_webhook_with_valid_secret(self, client):
        data = _make_update_dict()
        resp = client.post(
            "/webhook/telegram",
            json=data,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_webhook_rejects_missing_secret(self, client):
        data = _make_update_dict()
        resp = client.post("/webhook/telegram", json=data)
        assert resp.status_code == 403

    def test_webhook_rejects_wrong_secret(self, client):
        data = _make_update_dict()
        resp = client.post(
            "/webhook/telegram",
            json=data,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        assert resp.status_code == 403

    def test_webhook_accepts_without_secret_when_not_configured(self, client_no_secret):
        data = _make_update_dict()
        resp = client_no_secret.post("/webhook/telegram", json=data)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_webhook_returns_503_when_no_poller(self):
        from fastapi.testclient import TestClient

        from msg_gateway.app import app, set_telegram_poller

        set_telegram_poller(None)
        client = TestClient(app)
        resp = client.post("/webhook/telegram", json=_make_update_dict())
        assert resp.status_code == 503

    def test_webhook_rejects_invalid_json(self, client):
        resp = client.post(
            "/webhook/telegram",
            content=b"not json",
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Typing Indicator Tests
# ---------------------------------------------------------------------------


class TestTypingIndicator:
    def test_send_chat_action_typing(self, monkeypatch):
        """TelegramApi.send_chat_action sends typing action."""
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        api.send_chat_action("42")

        assert "sendChatAction" in captured["url"]
        assert captured["data"]["chat_id"] == "42"
        assert captured["data"]["action"] == "typing"

    def test_send_chat_action_custom_action(self, monkeypatch):
        """send_chat_action supports custom actions."""
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        api.send_chat_action("42", action="upload_document")

        assert captured["data"]["action"] == "upload_document"


# ---------------------------------------------------------------------------
# Reaction Tests
# ---------------------------------------------------------------------------


class TestMessageReaction:
    def test_set_message_reaction_default_thumbsup(self, monkeypatch):
        """set_message_reaction sends thumbs up by default."""
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        api.set_message_reaction("42", 99)

        assert "setMessageReaction" in captured["url"]
        assert captured["data"]["chat_id"] == "42"
        assert captured["data"]["message_id"] == 99
        assert captured["data"]["reaction"][0]["type"] == "emoji"
        assert captured["data"]["reaction"][0]["emoji"] == "\U0001f44d"

    def test_set_message_reaction_custom_emoji(self, monkeypatch):
        """set_message_reaction supports custom reaction emoji."""
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        api.set_message_reaction("42", 99, reaction="\u2764\ufe0f")

        assert captured["data"]["reaction"][0]["emoji"] == "\u2764\ufe0f"

    def test_set_message_reaction_fire_and_forget(self, monkeypatch):
        """set_message_reaction does not raise on error."""
        api = TelegramApi(bot_token="123:ABC")

        def mock_urlopen(req, **kw):
            import urllib.error

            raise urllib.error.URLError("network error")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        # Should not raise
        api.set_message_reaction("42", 99)


# ---------------------------------------------------------------------------
# Webhook API Methods
# ---------------------------------------------------------------------------


class TestSetWebhookApi:
    def test_set_webhook_basic(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True, "result": True}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        result = api.set_webhook("https://example.com/webhook/telegram")

        assert result.ok is True
        assert "setWebhook" in captured["url"]
        assert captured["data"]["url"] == "https://example.com/webhook/telegram"

    def test_set_webhook_with_secret(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True, "result": True}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        api.set_webhook(
            "https://example.com/webhook/telegram",
            secret_token="my-secret",
        )

        assert captured["data"]["secret_token"] == "my-secret"

    def test_set_webhook_without_secret_omits_field(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True, "result": True}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        api.set_webhook("https://example.com/webhook")

        assert "secret_token" not in captured["data"]

    def test_delete_webhook(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True, "result": True}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        result = api.delete_webhook()

        assert result.ok is True
        assert "deleteWebhook" in captured["url"]

    def test_get_file(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        captured = {}

        def mock_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data) if req.data else None
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(
                {
                    "ok": True,
                    "result": {"file_id": "abc", "file_path": "photos/file_0.jpg"},
                }
            ).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        result = api.get_file("abc")

        assert result.ok is True
        assert "getFile" in captured["url"]
        assert result.result["file_path"] == "photos/file_0.jpg"


# ---------------------------------------------------------------------------
# Poller — Reaction on incoming message
# ---------------------------------------------------------------------------


class TestPollerReaction:
    def test_handle_update_sends_reaction(self):
        """The poller sends a reaction when processing an authorized message."""
        from msg_gateway.telegram.poller import TelegramPoller

        poller = TelegramPoller(
            bot_token="123:ABC",
            allowed_chat_ids=["100"],
        )
        poller._api = MagicMock(spec=TelegramApi)
        poller._api.send_message.return_value = ApiResponse(ok=True)
        poller._api.set_message_reaction = MagicMock()
        poller._api.send_chat_action = MagicMock()

        # Patch _route_conversation to avoid Claude CLI call
        poller._route_conversation = MagicMock()

        update = Update.from_dict(_make_update_dict(text="hello", chat_id=100, message_id=42))
        poller._handle_update(update)

        poller._api.set_message_reaction.assert_called_once_with("100", 42)

    def test_handle_update_no_reaction_for_unauthorized(self):
        """No reaction for unauthorized messages."""
        from msg_gateway.telegram.poller import TelegramPoller

        poller = TelegramPoller(
            bot_token="123:ABC",
            allowed_chat_ids=["100"],
        )
        poller._api = MagicMock(spec=TelegramApi)

        update = Update.from_dict(_make_update_dict(text="hello", chat_id=999))
        poller._handle_update(update)

        poller._api.set_message_reaction.assert_not_called()


# ---------------------------------------------------------------------------
# Poller — Typing Indicator Integration
# ---------------------------------------------------------------------------


class TestPollerTyping:
    def test_conversation_worker_sends_typing(self):
        """_conversation_worker sends typing indicator before Claude call."""
        from msg_gateway.telegram.poller import TelegramPoller

        poller = TelegramPoller(
            bot_token="123:ABC",
            allowed_chat_ids=["100"],
        )
        poller._api = MagicMock(spec=TelegramApi)
        poller._api.send_message.return_value = ApiResponse(ok=True)

        # Mock Claude subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Claude response",
                stderr="",
                returncode=0,
            )
            poller._conversation_worker("test", "100", "chat")

        poller._api.send_chat_action.assert_called_with("100")
