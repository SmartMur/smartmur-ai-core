"""Tests for Telegram retry/backoff in channels adapter and cli_intake discovery."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, call, patch

import pytest

from superpowers.channels.base import SendResult
from superpowers.channels.telegram import (
    _BACKOFF_BASE,
    _MAX_RETRIES,
    TelegramChannel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ok_response(data: dict) -> MagicMock:
    """Return a mock that behaves like a urlopen context manager response."""
    raw = json.dumps(data).encode()
    mock = MagicMock()
    mock.read.return_value = raw
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _make_http_error(code: int, *, retry_after: str | None = None) -> urllib.error.HTTPError:
    """Build an HTTPError with optional Retry-After header."""
    headers = MagicMock()
    headers.get = MagicMock(side_effect=lambda key, default=None: retry_after if key == "Retry-After" else default)
    err = urllib.error.HTTPError(
        url="https://api.telegram.org/bot123:ABC/sendMessage",
        code=code,
        msg=f"HTTP {code}",
        hdrs=headers,  # type: ignore[arg-type]
        fp=io.BytesIO(b""),
    )
    # urllib.error.HTTPError sets self.headers from hdrs, but let's make sure
    err.headers = headers  # type: ignore[assignment]
    return err


# ===========================================================================
#  _api() retry tests
# ===========================================================================


class TestApiSuccessNoRetry:
    """Single successful call, no retry needed."""

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_returns_response_directly(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")
        mock_urlopen.return_value = _make_ok_response({"ok": True, "result": {"message_id": 1}})

        result = ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert result["ok"] is True
        assert result["result"]["message_id"] == 1
        mock_sleep.assert_not_called()
        assert mock_urlopen.call_count == 1


class TestApiRetriesOn429:
    """First call returns HTTP 429, second succeeds."""

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_retries_then_succeeds(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = [
            _make_http_error(429),
            _make_ok_response({"ok": True, "result": {"message_id": 2}}),
        ]

        result = ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert result["ok"] is True
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once()
        # Default backoff: 1.0 * 2^0 = 1.0
        assert mock_sleep.call_args[0][0] >= _BACKOFF_BASE


class TestApiRetriesOn500:
    """First call returns HTTP 500, second succeeds."""

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_retries_then_succeeds(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = [
            _make_http_error(500),
            _make_ok_response({"ok": True, "result": {"message_id": 3}}),
        ]

        result = ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert result["ok"] is True
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once()


class TestApiRetriesOn502503504:
    """Test all retryable server error codes."""

    @pytest.mark.parametrize("code", [502, 503, 504])
    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_retries_then_succeeds(self, mock_urlopen, mock_sleep, code):
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = [
            _make_http_error(code),
            _make_ok_response({"ok": True, "result": {"message_id": 4}}),
        ]

        result = ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert result["ok"] is True
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once()


class TestApiRetriesOnUrlError:
    """Network error (URLError), then success."""

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_retries_on_network_error(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = [
            urllib.error.URLError("Connection refused"),
            _make_ok_response({"ok": True, "result": {"message_id": 5}}),
        ]

        result = ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert result["ok"] is True
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once()


class TestApiNoRetryOn400:
    """HTTP 400 raises immediately (no retry)."""

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_raises_immediately(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = _make_http_error(400)

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert exc_info.value.code == 400
        mock_sleep.assert_not_called()
        assert mock_urlopen.call_count == 1


class TestApiNoRetryOn403:
    """HTTP 403 raises immediately."""

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_raises_immediately(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = _make_http_error(403)

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert exc_info.value.code == 403
        mock_sleep.assert_not_called()
        assert mock_urlopen.call_count == 1


class TestApiGivesUpAfterMaxRetries:
    """All attempts fail, raises the last exception."""

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_raises_after_exhausting_retries(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        # _MAX_RETRIES + 1 total attempts, all fail with 500
        mock_urlopen.side_effect = [_make_http_error(500)] * (_MAX_RETRIES + 1)

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert exc_info.value.code == 500
        assert mock_urlopen.call_count == _MAX_RETRIES + 1
        assert mock_sleep.call_count == _MAX_RETRIES

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_raises_after_exhausting_retries_url_error(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = [
            urllib.error.URLError("Connection refused")
        ] * (_MAX_RETRIES + 1)

        with pytest.raises(urllib.error.URLError):
            ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert mock_urlopen.call_count == _MAX_RETRIES + 1
        assert mock_sleep.call_count == _MAX_RETRIES


class TestApiRespectsRetryAfter:
    """HTTP 429 with Retry-After header is respected."""

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_uses_retry_after_header(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        error_429 = _make_http_error(429, retry_after="5")
        mock_urlopen.side_effect = [
            error_429,
            _make_ok_response({"ok": True, "result": {"message_id": 10}}),
        ]

        result = ch._api("sendMessage", {"chat_id": "1", "text": "hi"})

        assert result["ok"] is True
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once()
        # Should use max(backoff, Retry-After) = max(1.0, 5.0) = 5.0
        actual_wait = mock_sleep.call_args[0][0]
        assert actual_wait == 5.0


# ===========================================================================
#  send() integration with retry
# ===========================================================================


class TestSendSucceedsAfterTransientFailure:
    """send() returns ok after _api retries past a transient error."""

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_send_ok_after_retry(self, mock_urlopen, mock_sleep):
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = [
            _make_http_error(502),
            _make_ok_response({"ok": True, "result": {"message_id": 99}}),
        ]

        result = ch.send("12345", "hello world")

        assert isinstance(result, SendResult)
        assert result.ok is True
        assert "99" in result.message
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once()

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_send_fails_after_all_retries_exhausted(self, mock_urlopen, mock_sleep):
        """send() returns ok=False when _api exhausts retries (HTTPError caught by send)."""
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = [_make_http_error(500)] * (_MAX_RETRIES + 1)

        result = ch.send("12345", "hello world")

        assert isinstance(result, SendResult)
        assert result.ok is False
        assert result.error  # has some error text
        assert mock_urlopen.call_count == _MAX_RETRIES + 1

    @patch("superpowers.channels.telegram.time.sleep")
    @patch("urllib.request.urlopen")
    def test_send_returns_error_on_non_retryable(self, mock_urlopen, mock_sleep):
        """send() returns ok=False immediately for non-retryable errors."""
        ch = TelegramChannel(bot_token="123:ABC")

        mock_urlopen.side_effect = _make_http_error(400)

        result = ch.send("12345", "hello world")

        assert isinstance(result, SendResult)
        assert result.ok is False
        mock_sleep.assert_not_called()
        assert mock_urlopen.call_count == 1


# ===========================================================================
#  _discover_telegram_chat_id() retry tests
# ===========================================================================


class TestDiscoverChatIdRetries:
    """_discover_telegram_chat_id retries on network error."""

    @patch("superpowers.cli_intake.time.sleep")
    @patch("urllib.request.urlopen")
    def test_retries_on_url_error_then_succeeds(self, mock_urlopen, mock_sleep):
        from superpowers.cli_intake import _discover_telegram_chat_id

        ok_data = json.dumps({
            "ok": True,
            "result": [
                {"message": {"chat": {"id": 999}, "text": "/start"}},
            ],
        }).encode()

        ok_resp = MagicMock()
        ok_resp.read.return_value = ok_data
        ok_resp.__enter__ = lambda s: s
        ok_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            urllib.error.URLError("Connection refused"),
            ok_resp,
        ]

        result = _discover_telegram_chat_id("123:ABC")

        assert result == "999"
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    @patch("superpowers.cli_intake.time.sleep")
    @patch("urllib.request.urlopen")
    def test_returns_empty_after_all_retries_fail(self, mock_urlopen, mock_sleep):
        from superpowers.cli_intake import _discover_telegram_chat_id

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = _discover_telegram_chat_id("123:ABC")

        assert result == ""
        assert mock_urlopen.call_count == 3  # 3 attempts total
        assert mock_sleep.call_count == 2  # sleep between attempts 0->1, 1->2

    @patch("superpowers.cli_intake.time.sleep")
    @patch("urllib.request.urlopen")
    def test_returns_empty_for_blank_token(self, mock_urlopen, mock_sleep):
        from superpowers.cli_intake import _discover_telegram_chat_id

        result = _discover_telegram_chat_id("")

        assert result == ""
        mock_urlopen.assert_not_called()
        mock_sleep.assert_not_called()

    @patch("superpowers.cli_intake.time.sleep")
    @patch("urllib.request.urlopen")
    def test_exponential_backoff_timing(self, mock_urlopen, mock_sleep):
        from superpowers.cli_intake import _discover_telegram_chat_id

        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        _discover_telegram_chat_id("123:ABC")

        assert mock_sleep.call_count == 2
        # First backoff: 1.0 * 2^0 = 1.0
        assert mock_sleep.call_args_list[0] == call(1.0)
        # Second backoff: 1.0 * 2^1 = 2.0
        assert mock_sleep.call_args_list[1] == call(2.0)
