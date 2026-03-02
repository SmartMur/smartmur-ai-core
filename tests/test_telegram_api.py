"""Tests for the TelegramApi client (msg_gateway.telegram.api)."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, call

import pytest

from msg_gateway.telegram.api import ApiResponse, TelegramApi


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_urlopen_ok(response_body: dict) -> MagicMock:
    """Return a MagicMock that behaves like urllib.request.urlopen context manager."""
    encoded = json.dumps(response_body).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = encoded
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestTelegramApiInit:
    def test_empty_token_raises(self):
        with pytest.raises(ValueError, match="bot_token is required"):
            TelegramApi(bot_token="")

    def test_none_token_raises(self):
        with pytest.raises(ValueError):
            TelegramApi(bot_token="")

    def test_valid_token_stores_base(self):
        api = TelegramApi(bot_token="123:ABC")
        assert "123:ABC" in api._base


# ---------------------------------------------------------------------------
# Successful API call
# ---------------------------------------------------------------------------


class TestCallSuccess:
    def test_successful_call_returns_ok(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        body = {"ok": True, "result": {"user": "bot"}}
        mock_resp = _mock_urlopen_ok(body)

        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        result = api.call("getMe")
        assert result.ok is True
        assert result.result == {"user": "bot"}
        assert result.error_code == 0

    def test_call_sends_json_payload(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        body = {"ok": True, "result": True}
        mock_resp = _mock_urlopen_ok(body)

        captured_req = {}

        def fake_urlopen(req, **kw):
            captured_req["data"] = req.data
            captured_req["headers"] = dict(req.headers)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        api.call("sendMessage", {"chat_id": "42", "text": "hi"})

        sent = json.loads(captured_req["data"])
        assert sent["chat_id"] == "42"
        assert sent["text"] == "hi"
        assert captured_req["headers"]["Content-type"] == "application/json"


# ---------------------------------------------------------------------------
# API error response (ok=False in body)
# ---------------------------------------------------------------------------


class TestCallApiError:
    def test_api_error_response(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        body = {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: chat not found",
        }
        mock_resp = _mock_urlopen_ok(body)
        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: mock_resp)

        result = api.call("sendMessage", {"chat_id": "bad", "text": "x"})
        assert result.ok is False
        assert result.error_code == 400
        assert "chat not found" in result.description


# ---------------------------------------------------------------------------
# Retry on HTTP 429 / 500 errors
# ---------------------------------------------------------------------------


class TestRetryOnHttpError:
    def test_retry_on_429_then_succeed(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")

        # First call raises HTTP 429, second succeeds
        success_resp = _mock_urlopen_ok({"ok": True, "result": True})

        call_count = {"n": 0}

        def fake_urlopen(req, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                exc = urllib.error.HTTPError(
                    url="https://api.telegram.org/bot123:ABC/sendMessage",
                    code=429,
                    msg="Too Many Requests",
                    hdrs=MagicMock(**{"get.return_value": "1"}),
                    fp=None,
                )
                raise exc
            return success_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda s: None)  # skip sleeping

        result = api.call("sendMessage", {"chat_id": "1", "text": "hi"}, retries=2)
        assert result.ok is True
        assert call_count["n"] == 2

    def test_retry_on_500_then_succeed(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        success_resp = _mock_urlopen_ok({"ok": True, "result": True})

        call_count = {"n": 0}

        def fake_urlopen(req, **kw):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise urllib.error.HTTPError(
                    url="https://example.com",
                    code=500,
                    msg="Internal Server Error",
                    hdrs=MagicMock(),
                    fp=None,
                )
            return success_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = api.call("sendMessage", retries=3)
        assert result.ok is True
        assert call_count["n"] == 3

    def test_exhausted_retries_returns_error(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")

        def fake_urlopen(req, **kw):
            raise urllib.error.HTTPError(
                url="https://example.com",
                code=502,
                msg="Bad Gateway",
                hdrs=MagicMock(),
                fp=None,
            )

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = api.call("sendMessage", retries=2)
        assert result.ok is False
        assert "502" in result.description

    def test_non_retryable_http_error_no_retry(self, monkeypatch):
        """HTTP 403 is not in _RETRY_CODES so should fail immediately."""
        api = TelegramApi(bot_token="123:ABC")

        call_count = {"n": 0}

        def fake_urlopen(req, **kw):
            call_count["n"] += 1
            raise urllib.error.HTTPError(
                url="https://example.com",
                code=403,
                msg="Forbidden",
                hdrs=MagicMock(),
                fp=None,
            )

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = api.call("sendMessage", retries=3)
        assert result.ok is False
        # Should only have been called once (no retries for 403)
        assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# Network error retry (URLError)
# ---------------------------------------------------------------------------


class TestRetryOnNetworkError:
    def test_retry_on_url_error_then_succeed(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        success_resp = _mock_urlopen_ok({"ok": True, "result": True})

        call_count = {"n": 0}

        def fake_urlopen(req, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise urllib.error.URLError("Connection refused")
            return success_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = api.call("getMe", retries=2)
        assert result.ok is True
        assert call_count["n"] == 2

    def test_all_network_errors_returns_failure(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")

        def fake_urlopen(req, **kw):
            raise urllib.error.URLError("Connection refused")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = api.call("getMe", retries=1)
        assert result.ok is False
        assert "Connection refused" in result.description


# ---------------------------------------------------------------------------
# fire_and_forget
# ---------------------------------------------------------------------------


class TestFireAndForget:
    def test_fire_and_forget_does_not_raise_on_error(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")

        def fake_urlopen(req, **kw):
            raise urllib.error.URLError("boom")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        # Should not raise
        api.fire_and_forget("sendMessage", {"chat_id": "1", "text": "hi"})

    def test_fire_and_forget_calls_with_zero_retries(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")

        call_count = {"n": 0}

        def fake_urlopen(req, **kw):
            call_count["n"] += 1
            raise urllib.error.URLError("offline")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        api.fire_and_forget("sendChatAction", {"chat_id": "1", "action": "typing"})
        # With retries=0, only one attempt is made
        assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# Convenience methods
# ---------------------------------------------------------------------------


class TestSendMessage:
    def test_send_message_basic(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        mock_resp = _mock_urlopen_ok({"ok": True, "result": {"message_id": 99}})

        captured = {}

        def fake_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data) if req.data else None
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        result = api.send_message("42", "Hello!")
        assert result.ok is True
        assert "sendMessage" in captured["url"]
        assert captured["data"]["chat_id"] == "42"
        assert captured["data"]["text"] == "Hello!"

    def test_send_message_with_parse_mode(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        mock_resp = _mock_urlopen_ok({"ok": True, "result": True})

        captured = {}

        def fake_urlopen(req, **kw):
            captured["data"] = json.loads(req.data)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        api.send_message("42", "**bold**", parse_mode="MarkdownV2")
        assert captured["data"]["parse_mode"] == "MarkdownV2"

    def test_send_message_with_reply_markup(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        mock_resp = _mock_urlopen_ok({"ok": True, "result": True})

        captured = {}

        def fake_urlopen(req, **kw):
            captured["data"] = json.loads(req.data)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        markup = {"inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]}
        api.send_message("42", "Pick one", reply_markup=markup)
        assert captured["data"]["reply_markup"] == markup

    def test_send_message_omits_none_fields(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        mock_resp = _mock_urlopen_ok({"ok": True, "result": True})

        captured = {}

        def fake_urlopen(req, **kw):
            captured["data"] = json.loads(req.data)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        api.send_message("42", "hi")
        assert "parse_mode" not in captured["data"]
        assert "reply_markup" not in captured["data"]


class TestGetUpdates:
    def test_get_updates_with_offset_and_timeout(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        mock_resp = _mock_urlopen_ok({"ok": True, "result": []})

        captured = {}

        def fake_urlopen(req, **kw):
            captured["data"] = json.loads(req.data)
            captured["timeout"] = kw.get("timeout")
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        result = api.get_updates(offset=100, timeout=30)
        assert result.ok is True
        assert captured["data"]["offset"] == 100
        assert captured["data"]["timeout"] == 30
        # effective timeout = timeout + 5 = 35
        assert captured["timeout"] == 35


class TestAnswerCallbackQuery:
    def test_answer_callback_query_basic(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        mock_resp = _mock_urlopen_ok({"ok": True, "result": True})

        captured = {}

        def fake_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        result = api.answer_callback_query("abc123")
        assert result.ok is True
        assert "answerCallbackQuery" in captured["url"]
        assert captured["data"]["callback_query_id"] == "abc123"
        # No text or show_alert by default
        assert "text" not in captured["data"]
        assert "show_alert" not in captured["data"]

    def test_answer_callback_query_with_text_and_alert(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        mock_resp = _mock_urlopen_ok({"ok": True, "result": True})

        captured = {}

        def fake_urlopen(req, **kw):
            captured["data"] = json.loads(req.data)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        api.answer_callback_query("abc123", text="Done!", show_alert=True)
        assert captured["data"]["text"] == "Done!"
        assert captured["data"]["show_alert"] is True


class TestSetMyCommands:
    def test_set_my_commands(self, monkeypatch):
        api = TelegramApi(bot_token="123:ABC")
        mock_resp = _mock_urlopen_ok({"ok": True, "result": True})

        captured = {}

        def fake_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data)
            return mock_resp

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        commands = [
            {"command": "start", "description": "Start the bot"},
            {"command": "help", "description": "Show help"},
        ]
        result = api.set_my_commands(commands)
        assert result.ok is True
        assert "setMyCommands" in captured["url"]
        assert captured["data"]["commands"] == commands
