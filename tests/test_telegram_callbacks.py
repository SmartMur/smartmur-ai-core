"""Tests for Telegram callback query handler."""

from __future__ import annotations

from unittest.mock import MagicMock

from msg_gateway.telegram.api import ApiResponse, TelegramApi
from msg_gateway.telegram.callbacks import CallbackHandler
from msg_gateway.telegram.types import CallbackQuery

# --- Helpers ---


def _make_callback_query(data: str, chat_id: int = 100, query_id: str = "qid_123") -> CallbackQuery:
    """Create a CallbackQuery object from a dict, simulating Telegram's format."""
    return CallbackQuery.from_dict(
        {
            "id": query_id,
            "from": {"id": 42, "is_bot": False, "first_name": "Alice"},
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id, "type": "private"},
                "text": "original message",
                "date": 1700000000,
            },
            "data": data,
        }
    )


def _make_handler(
    api: TelegramApi | None = None, chat_modes: dict | None = None
) -> CallbackHandler:
    if api is None:
        api = MagicMock(spec=TelegramApi)
        api.answer_callback_query.return_value = ApiResponse(ok=True)
        api.send_message.return_value = ApiResponse(ok=True)
    return CallbackHandler(api=api, chat_modes=chat_modes)


# --- mode:chat callback ---


def test_handle_mode_chat():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)
    chat_modes = {}

    handler = _make_handler(api=api, chat_modes=chat_modes)
    query = _make_callback_query("mode:chat")
    handler.handle(query)

    # Should set chat mode
    assert chat_modes["100"] == "chat"

    # Should answer the callback query
    api.answer_callback_query.assert_called_once()
    assert "chat" in api.answer_callback_query.call_args[0][1].lower()

    # Should send a confirmation message
    api.send_message.assert_called_once()
    args, _ = api.send_message.call_args
    assert args[0] == "100"
    assert "chat" in args[1].lower()


def test_handle_mode_skill():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)
    chat_modes = {}

    handler = _make_handler(api=api, chat_modes=chat_modes)
    query = _make_callback_query("mode:skill")
    handler.handle(query)

    assert chat_modes["100"] == "skill"
    api.send_message.assert_called_once()


def test_handle_mode_unknown_mode():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    query = _make_callback_query("mode:invalid_mode")
    handler.handle(query)

    # Should answer with unknown mode, but not send a message
    api.answer_callback_query.assert_called_once()
    assert "unknown" in api.answer_callback_query.call_args[0][1].lower()
    api.send_message.assert_not_called()


# --- cancel callback ---


def test_handle_cancel():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    query = _make_callback_query("cancel:")
    handler.handle(query)

    api.answer_callback_query.assert_called_once()
    assert "cancelled" in api.answer_callback_query.call_args[0][1].lower()

    api.send_message.assert_called_once()
    args, _ = api.send_message.call_args
    assert "cancelled" in args[1].lower()


def test_handle_cancel_with_value():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    query = _make_callback_query("cancel:some_action")
    handler.handle(query)

    api.answer_callback_query.assert_called_once()
    api.send_message.assert_called_once()


# --- confirm callback ---


def test_handle_confirm():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    query = _make_callback_query("confirm:delete_all")
    handler.handle(query)

    api.answer_callback_query.assert_called_once()
    assert "confirmed" in api.answer_callback_query.call_args[0][1].lower()

    api.send_message.assert_called_once()
    args, _ = api.send_message.call_args
    assert "confirmed" in args[1].lower()
    assert "delete_all" in args[1]


# --- unknown prefix ---


def test_handle_unknown_prefix():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    query = _make_callback_query("bogus:something")
    handler.handle(query)

    api.answer_callback_query.assert_called_once()
    assert "unknown" in api.answer_callback_query.call_args[0][1].lower()
    # Should not send a chat message for unknown prefix
    api.send_message.assert_not_called()


def test_handle_prefix_only_no_value():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    query = _make_callback_query("unknown_action")
    handler.handle(query)

    api.answer_callback_query.assert_called_once()
    assert "unknown" in api.answer_callback_query.call_args[0][1].lower()


# --- empty data ---


def test_handle_empty_data():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    query = _make_callback_query("")
    handler.handle(query)

    api.answer_callback_query.assert_called_once()
    assert "no data" in api.answer_callback_query.call_args[0][1].lower()
    api.send_message.assert_not_called()


def test_handle_none_data():
    """CallbackQuery with data=None should be handled gracefully."""
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    # from_dict with empty data key produces data=""
    query = CallbackQuery.from_dict(
        {
            "id": "qid_999",
            "from": {"id": 42, "is_bot": False, "first_name": "Alice"},
            "message": {
                "message_id": 1,
                "chat": {"id": 100, "type": "private"},
                "text": "msg",
                "date": 0,
            },
            "data": "",
        }
    )
    handler.handle(query)

    api.answer_callback_query.assert_called_once()


# --- skill callback ---


def test_handle_skill_callback():
    api = MagicMock(spec=TelegramApi)
    api.answer_callback_query.return_value = ApiResponse(ok=True)
    api.send_message.return_value = ApiResponse(ok=True)

    handler = _make_handler(api=api)
    query = _make_callback_query("skill:my_cool_skill")
    handler.handle(query)

    # Should answer the callback query
    api.answer_callback_query.assert_called_once()
    assert "my_cool_skill" in api.answer_callback_query.call_args[0][1]

    # Should send at least one message (the "Running skill" message)
    assert api.send_message.call_count >= 1
    first_msg = api.send_message.call_args_list[0]
    assert "my_cool_skill" in first_msg[0][1]
