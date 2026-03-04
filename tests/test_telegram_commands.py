"""Tests for Telegram command router."""

from __future__ import annotations

from unittest.mock import MagicMock

from msg_gateway.telegram.api import ApiResponse, TelegramApi
from msg_gateway.telegram.commands import COMMAND_MENU, CommandRouter
from msg_gateway.telegram.session import SessionManager
from msg_gateway.telegram.types import Message

# --- Helpers ---


def _make_message(text: str, chat_id: int = 100, first_name: str = "Alice") -> Message:
    """Create a Message object from a dict, simulating Telegram's format."""
    return Message.from_dict(
        {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": 42, "is_bot": False, "first_name": first_name},
            "text": text,
            "date": 1700000000,
        }
    )


def _make_router(
    api: TelegramApi | None = None,
    session: SessionManager | None = None,
    chat_modes: dict | None = None,
) -> CommandRouter:
    if api is None:
        api = MagicMock(spec=TelegramApi)
        api.send_message.return_value = ApiResponse(ok=True)
        api.set_my_commands.return_value = ApiResponse(ok=True)
    if session is None:
        session = SessionManager()
    return CommandRouter(api=api, session=session, chat_modes=chat_modes)


# --- can_handle ---


def test_can_handle_returns_true_for_known_commands():
    router = _make_router()
    for cmd_def in COMMAND_MENU:
        msg = _make_message(f"/{cmd_def['command']}")
        assert router.can_handle(msg) is True, f"/{cmd_def['command']} should be handled"


def test_can_handle_returns_false_for_plain_text():
    router = _make_router()
    msg = _make_message("just a regular message")
    assert router.can_handle(msg) is False


def test_can_handle_returns_false_for_unknown_command():
    router = _make_router()
    msg = _make_message("/unknown_command")
    assert router.can_handle(msg) is False


def test_can_handle_with_bot_mention():
    router = _make_router()
    msg = _make_message("/start@mybot")
    assert router.can_handle(msg) is True


# --- /start ---


def test_cmd_start_sends_greeting():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    router = _make_router(api=api)

    msg = _make_message("/start", first_name="Bob")
    router.handle(msg)

    api.send_message.assert_called_once()
    args, kwargs = api.send_message.call_args
    assert args[0] == "100"  # chat_id
    assert "Bob" in args[1]  # greeting contains the user's name
    assert "Claude Superpowers" in args[1]


def test_cmd_start_without_from_user():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    router = _make_router(api=api)

    # Create message without from user
    msg = Message.from_dict(
        {
            "message_id": 1,
            "chat": {"id": 100, "type": "private"},
            "text": "/start",
            "date": 1700000000,
        }
    )
    router.handle(msg)

    api.send_message.assert_called_once()
    args, _ = api.send_message.call_args
    assert "there" in args[1]  # fallback name


# --- /help ---


def test_cmd_help_lists_commands():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    router = _make_router(api=api)

    msg = _make_message("/help")
    router.handle(msg)

    api.send_message.assert_called_once()
    args, _ = api.send_message.call_args
    response_text = args[1]

    # Every command from the menu should appear in the help text
    for cmd_def in COMMAND_MENU:
        assert f"/{cmd_def['command']}" in response_text
        assert cmd_def["description"] in response_text


# --- /reset ---


def test_cmd_reset_clears_session():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    session = SessionManager()
    session.add("100", "user", "some old message")
    session.add("100", "assistant", "some old reply")

    router = _make_router(api=api, session=session)
    msg = _make_message("/reset")
    router.handle(msg)

    # Session should be cleared
    assert session.get("100") == []

    # Should send confirmation
    api.send_message.assert_called_once()
    args, _ = api.send_message.call_args
    assert "cleared" in args[1].lower()


# --- /mode ---


def test_cmd_mode_with_args_switches_mode():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    chat_modes = {}
    router = _make_router(api=api, chat_modes=chat_modes)

    msg = _make_message("/mode chat")
    router.handle(msg)

    assert chat_modes["100"] == "chat"
    args, _ = api.send_message.call_args
    assert "chat" in args[1].lower()


def test_cmd_mode_switch_to_skill():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    chat_modes = {}
    router = _make_router(api=api, chat_modes=chat_modes)

    msg = _make_message("/mode skill")
    router.handle(msg)

    assert chat_modes["100"] == "skill"


def test_cmd_mode_without_args_shows_current_and_keyboard():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    chat_modes = {"100": "skill"}
    router = _make_router(api=api, chat_modes=chat_modes)

    msg = _make_message("/mode")
    router.handle(msg)

    api.send_message.assert_called_once()
    args, kwargs = api.send_message.call_args
    assert "skill" in args[1]  # mentions current mode
    assert kwargs.get("reply_markup") is not None  # keyboard attached


# --- /run ---


def test_cmd_run_without_args_shows_usage():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    router = _make_router(api=api)

    msg = _make_message("/run")
    router.handle(msg)

    api.send_message.assert_called_once()
    args, _ = api.send_message.call_args
    assert "usage" in args[1].lower() or "Usage" in args[1]


def test_cmd_run_with_args_attempts_execution():
    api = MagicMock(spec=TelegramApi)
    api.send_message.return_value = ApiResponse(ok=True)
    router = _make_router(api=api)

    msg = _make_message("/run my_skill")
    router.handle(msg)

    # It should call send_message at least once (the "Running skill" message)
    assert api.send_message.call_count >= 1
    first_call_args = api.send_message.call_args_list[0]
    assert "my_skill" in first_call_args[0][1]


# --- register_menu ---


def test_register_menu_calls_set_my_commands():
    api = MagicMock(spec=TelegramApi)
    api.set_my_commands.return_value = ApiResponse(ok=True)
    router = _make_router(api=api)

    router.register_menu()

    api.set_my_commands.assert_called_once_with(COMMAND_MENU)


def test_register_menu_handles_failure():
    api = MagicMock(spec=TelegramApi)
    api.set_my_commands.return_value = ApiResponse(ok=False, description="Unauthorized")
    router = _make_router(api=api)

    # Should not raise
    router.register_menu()
    api.set_my_commands.assert_called_once()


# --- Error handling ---


def test_handle_command_error_sends_error_message():
    api = MagicMock(spec=TelegramApi)
    api.send_message.side_effect = [RuntimeError("network fail"), ApiResponse(ok=True)]
    router = _make_router(api=api)

    msg = _make_message("/start")
    router.handle(msg)

    # The handler caught the exception and called _reply again with an error message
    assert api.send_message.call_count == 2
    error_call_args = api.send_message.call_args_list[1]
    assert "Error" in error_call_args[0][1]
