"""Tests for Telegram typed dataclasses (msg_gateway.telegram.types)."""

from __future__ import annotations

import pytest

from msg_gateway.telegram.types import (
    CallbackQuery,
    Chat,
    Message,
    Update,
    User,
    Voice,
    parse_updates,
)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class TestUser:
    def test_from_dict_full(self):
        data = {
            "id": 12345,
            "is_bot": False,
            "first_name": "Alice",
            "last_name": "Smith",
            "username": "alice_s",
        }
        user = User.from_dict(data)
        assert user is not None
        assert user.id == 12345
        assert user.is_bot is False
        assert user.first_name == "Alice"
        assert user.last_name == "Smith"
        assert user.username == "alice_s"

    def test_from_dict_minimal(self):
        data = {"id": 99}
        user = User.from_dict(data)
        assert user is not None
        assert user.id == 99
        assert user.is_bot is False
        assert user.first_name == ""
        assert user.last_name == ""
        assert user.username == ""

    def test_from_dict_none(self):
        assert User.from_dict(None) is None

    def test_from_dict_empty(self):
        assert User.from_dict({}) is None


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class TestChat:
    def test_from_dict_full(self):
        data = {
            "id": -100123,
            "type": "supergroup",
            "title": "Dev Team",
            "username": "devteam",
        }
        chat = Chat.from_dict(data)
        assert chat is not None
        assert chat.id == -100123
        assert chat.type == "supergroup"
        assert chat.title == "Dev Team"
        assert chat.username == "devteam"

    def test_from_dict_private(self):
        data = {"id": 42, "type": "private"}
        chat = Chat.from_dict(data)
        assert chat is not None
        assert chat.id == 42
        assert chat.type == "private"
        assert chat.title == ""

    def test_from_dict_none(self):
        assert Chat.from_dict(None) is None

    def test_from_dict_empty(self):
        assert Chat.from_dict({}) is None

    def test_from_dict_defaults(self):
        data = {"id": 1}
        chat = Chat.from_dict(data)
        assert chat.type == "private"
        assert chat.title == ""
        assert chat.username == ""


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------


class TestVoice:
    def test_from_dict_full(self):
        data = {
            "file_id": "AwACAgIAAxkBAAI",
            "file_unique_id": "AgADJQAD",
            "duration": 5,
        }
        voice = Voice.from_dict(data)
        assert voice is not None
        assert voice.file_id == "AwACAgIAAxkBAAI"
        assert voice.file_unique_id == "AgADJQAD"
        assert voice.duration == 5

    def test_from_dict_none(self):
        assert Voice.from_dict(None) is None

    def test_from_dict_empty(self):
        assert Voice.from_dict({}) is None

    def test_from_dict_defaults(self):
        data = {"file_id": "abc"}
        voice = Voice.from_dict(data)
        assert voice.file_unique_id == ""
        assert voice.duration == 0


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class TestMessage:
    def test_from_dict_text_message(self):
        data = {
            "message_id": 101,
            "chat": {"id": 42, "type": "private"},
            "from": {"id": 99, "first_name": "Bob"},
            "text": "Hello there",
            "date": 1700000000,
        }
        msg = Message.from_dict(data)
        assert msg is not None
        assert msg.message_id == 101
        assert msg.chat is not None
        assert msg.chat.id == 42
        assert msg.from_user is not None
        assert msg.from_user.first_name == "Bob"
        assert msg.text == "Hello there"
        assert msg.date == 1700000000
        assert msg.voice is None
        assert msg.audio is None

    def test_from_dict_voice_message(self):
        data = {
            "message_id": 102,
            "chat": {"id": 42, "type": "private"},
            "voice": {
                "file_id": "voice_file_123",
                "file_unique_id": "unique_123",
                "duration": 10,
            },
            "date": 1700000001,
        }
        msg = Message.from_dict(data)
        assert msg is not None
        assert msg.voice is not None
        assert msg.voice.file_id == "voice_file_123"
        assert msg.voice.duration == 10
        assert msg.text == ""

    def test_from_dict_command_message(self):
        data = {
            "message_id": 103,
            "chat": {"id": 42, "type": "group"},
            "text": "/start@mybot extra args here",
            "date": 1700000002,
        }
        msg = Message.from_dict(data)
        assert msg is not None
        assert msg.text == "/start@mybot extra args here"

    def test_from_dict_none(self):
        assert Message.from_dict(None) is None

    def test_from_dict_empty(self):
        assert Message.from_dict({}) is None

    def test_chat_id_property(self):
        msg = Message(chat=Chat(id=42))
        assert msg.chat_id == "42"

    def test_chat_id_property_no_chat(self):
        msg = Message()
        assert msg.chat_id == ""


class TestMessageIsCommand:
    def test_is_command_true(self):
        msg = Message(text="/start")
        assert msg.is_command is True

    def test_is_command_false_regular_text(self):
        msg = Message(text="hello")
        assert msg.is_command is False

    def test_is_command_false_empty(self):
        msg = Message(text="")
        assert msg.is_command is False

    def test_is_command_slash_in_middle(self):
        msg = Message(text="not a /command")
        assert msg.is_command is False


class TestMessageCommand:
    def test_command_simple(self):
        msg = Message(text="/start")
        assert msg.command == "start"

    def test_command_with_bot_mention(self):
        msg = Message(text="/help@mybot")
        assert msg.command == "help"

    def test_command_lowercased(self):
        msg = Message(text="/START")
        assert msg.command == "start"

    def test_command_with_args(self):
        msg = Message(text="/echo hello world")
        assert msg.command == "echo"

    def test_command_with_bot_and_args(self):
        msg = Message(text="/settings@mybot dark_mode")
        assert msg.command == "settings"

    def test_command_empty_for_non_command(self):
        msg = Message(text="hello")
        assert msg.command == ""


class TestMessageCommandArgs:
    def test_command_args_present(self):
        msg = Message(text="/echo hello world")
        assert msg.command_args == "hello world"

    def test_command_args_none(self):
        msg = Message(text="/start")
        assert msg.command_args == ""

    def test_command_args_on_non_command(self):
        msg = Message(text="hello")
        assert msg.command_args == ""

    def test_command_args_preserves_whitespace(self):
        msg = Message(text="/echo   spaced   text")
        assert msg.command_args == "  spaced   text"


# ---------------------------------------------------------------------------
# CallbackQuery
# ---------------------------------------------------------------------------


class TestCallbackQuery:
    def test_from_dict_full(self):
        data = {
            "id": "cb_999",
            "from": {"id": 42, "first_name": "Alice"},
            "message": {
                "message_id": 200,
                "chat": {"id": 42, "type": "private"},
                "text": "Pick one:",
            },
            "data": "option_a",
        }
        cb = CallbackQuery.from_dict(data)
        assert cb is not None
        assert cb.id == "cb_999"
        assert cb.from_user is not None
        assert cb.from_user.first_name == "Alice"
        assert cb.message is not None
        assert cb.message.message_id == 200
        assert cb.data == "option_a"

    def test_from_dict_none(self):
        assert CallbackQuery.from_dict(None) is None

    def test_from_dict_empty(self):
        assert CallbackQuery.from_dict({}) is None

    def test_chat_id_property(self):
        cb = CallbackQuery(
            id="cb_1",
            message=Message(chat=Chat(id=42)),
        )
        assert cb.chat_id == "42"

    def test_chat_id_property_no_message(self):
        cb = CallbackQuery(id="cb_1")
        assert cb.chat_id == ""

    def test_chat_id_property_no_chat(self):
        cb = CallbackQuery(id="cb_1", message=Message())
        assert cb.chat_id == ""


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_from_dict_with_message(self):
        data = {
            "update_id": 555,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "hello",
            },
        }
        update = Update.from_dict(data)
        assert update.update_id == 555
        assert update.message is not None
        assert update.message.text == "hello"
        assert update.callback_query is None

    def test_from_dict_with_callback_query(self):
        data = {
            "update_id": 556,
            "callback_query": {
                "id": "cb_1",
                "from": {"id": 42},
                "data": "btn_click",
            },
        }
        update = Update.from_dict(data)
        assert update.update_id == 556
        assert update.message is None
        assert update.callback_query is not None
        assert update.callback_query.data == "btn_click"

    def test_from_dict_empty(self):
        update = Update.from_dict({})
        assert update.update_id == 0
        assert update.message is None
        assert update.callback_query is None


# ---------------------------------------------------------------------------
# parse_updates
# ---------------------------------------------------------------------------


class TestParseUpdates:
    def test_valid_response(self):
        data = {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "message_id": 10,
                        "chat": {"id": 42, "type": "private"},
                        "text": "first",
                    },
                },
                {
                    "update_id": 2,
                    "message": {
                        "message_id": 11,
                        "chat": {"id": 42, "type": "private"},
                        "text": "second",
                    },
                },
            ],
        }
        updates = parse_updates(data)
        assert len(updates) == 2
        assert updates[0].update_id == 1
        assert updates[0].message.text == "first"
        assert updates[1].update_id == 2
        assert updates[1].message.text == "second"

    def test_not_ok_response(self):
        data = {"ok": False, "error_code": 401, "description": "Unauthorized"}
        updates = parse_updates(data)
        assert updates == []

    def test_empty_result(self):
        data = {"ok": True, "result": []}
        updates = parse_updates(data)
        assert updates == []

    def test_missing_ok_field(self):
        data = {"result": []}
        updates = parse_updates(data)
        assert updates == []

    def test_missing_result_field(self):
        data = {"ok": True}
        updates = parse_updates(data)
        assert updates == []
