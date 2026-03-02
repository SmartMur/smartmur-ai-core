"""Tests for Telegram inline keyboard helpers."""

from __future__ import annotations

from msg_gateway.telegram.keyboards import (
    button_grid,
    confirm_keyboard,
    inline_button,
    inline_keyboard,
    mode_keyboard,
    single_row,
    skill_list_keyboard,
)


# --- inline_button ---


def test_inline_button_returns_correct_dict():
    btn = inline_button("Click me", "action:click")
    assert btn == {"text": "Click me", "callback_data": "action:click"}


def test_inline_button_with_empty_strings():
    btn = inline_button("", "")
    assert btn == {"text": "", "callback_data": ""}


# --- inline_keyboard ---


def test_inline_keyboard_wraps_rows():
    rows = [
        [inline_button("A", "a"), inline_button("B", "b")],
        [inline_button("C", "c")],
    ]
    kb = inline_keyboard(rows)
    assert "inline_keyboard" in kb
    assert len(kb["inline_keyboard"]) == 2
    assert len(kb["inline_keyboard"][0]) == 2
    assert len(kb["inline_keyboard"][1]) == 1


def test_inline_keyboard_empty_rows():
    kb = inline_keyboard([])
    assert kb == {"inline_keyboard": []}


def test_inline_keyboard_preserves_button_data():
    btn = inline_button("Test", "data:test")
    kb = inline_keyboard([[btn]])
    assert kb["inline_keyboard"][0][0] == {"text": "Test", "callback_data": "data:test"}


# --- single_row ---


def test_single_row_creates_one_row_keyboard():
    btn1 = inline_button("A", "a")
    btn2 = inline_button("B", "b")
    btn3 = inline_button("C", "c")

    kb = single_row(btn1, btn2, btn3)
    assert "inline_keyboard" in kb
    assert len(kb["inline_keyboard"]) == 1
    assert len(kb["inline_keyboard"][0]) == 3


def test_single_row_single_button():
    btn = inline_button("Only", "only")
    kb = single_row(btn)
    assert len(kb["inline_keyboard"]) == 1
    assert len(kb["inline_keyboard"][0]) == 1
    assert kb["inline_keyboard"][0][0]["text"] == "Only"


# --- button_grid ---


def test_button_grid_creates_grid_layout():
    items = [
        ("A", "a"),
        ("B", "b"),
        ("C", "c"),
        ("D", "d"),
        ("E", "e"),
    ]
    kb = button_grid(items, columns=2)
    rows = kb["inline_keyboard"]

    # 5 items, 2 columns -> 3 rows (2, 2, 1)
    assert len(rows) == 3
    assert len(rows[0]) == 2
    assert len(rows[1]) == 2
    assert len(rows[2]) == 1


def test_button_grid_single_column():
    items = [("A", "a"), ("B", "b"), ("C", "c")]
    kb = button_grid(items, columns=1)
    rows = kb["inline_keyboard"]

    assert len(rows) == 3
    for row in rows:
        assert len(row) == 1


def test_button_grid_exact_fit():
    items = [("A", "a"), ("B", "b"), ("C", "c"), ("D", "d")]
    kb = button_grid(items, columns=2)
    rows = kb["inline_keyboard"]

    assert len(rows) == 2
    assert len(rows[0]) == 2
    assert len(rows[1]) == 2


def test_button_grid_empty_items():
    kb = button_grid([], columns=2)
    assert kb == {"inline_keyboard": []}


def test_button_grid_button_content():
    items = [("Hello", "cb:hello"), ("World", "cb:world")]
    kb = button_grid(items, columns=2)
    row = kb["inline_keyboard"][0]

    assert row[0] == {"text": "Hello", "callback_data": "cb:hello"}
    assert row[1] == {"text": "World", "callback_data": "cb:world"}


# --- confirm_keyboard ---


def test_confirm_keyboard_has_confirm_and_cancel_buttons():
    kb = confirm_keyboard("delete everything")
    rows = kb["inline_keyboard"]

    assert len(rows) == 1  # single row
    assert len(rows[0]) == 2  # two buttons

    confirm_btn, cancel_btn = rows[0]
    assert "Yes" in confirm_btn["text"]
    assert "delete everything" in confirm_btn["text"]
    assert confirm_btn["callback_data"] == "confirm"
    assert cancel_btn["text"] == "Cancel"
    assert cancel_btn["callback_data"] == "cancel"


def test_confirm_keyboard_custom_data():
    kb = confirm_keyboard("do it", confirm_data="confirm:do_it", cancel_data="cancel:do_it")
    rows = kb["inline_keyboard"]

    confirm_btn, cancel_btn = rows[0]
    assert confirm_btn["callback_data"] == "confirm:do_it"
    assert cancel_btn["callback_data"] == "cancel:do_it"


# --- skill_list_keyboard ---


def test_skill_list_keyboard_creates_buttons_from_skill_names():
    skills = ["backup", "deploy", "monitor"]
    kb = skill_list_keyboard(skills)
    rows = kb["inline_keyboard"]

    # 3 skills, 2 columns -> 2 rows
    assert len(rows) == 2

    # Flatten all buttons and check
    all_buttons = [btn for row in rows for btn in row]
    assert len(all_buttons) == 3

    # Each button should have skill name as text and skill:name as callback
    for btn, name in zip(all_buttons, skills):
        assert btn["text"] == name
        assert btn["callback_data"] == f"skill:{name}"


def test_skill_list_keyboard_empty():
    kb = skill_list_keyboard([])
    assert kb == {"inline_keyboard": []}


def test_skill_list_keyboard_truncates_at_20():
    skills = [f"skill_{i}" for i in range(25)]
    kb = skill_list_keyboard(skills)
    all_buttons = [btn for row in kb["inline_keyboard"] for btn in row]
    # Should only have 20 buttons (Telegram limit)
    assert len(all_buttons) == 20


def test_skill_list_keyboard_single_skill():
    kb = skill_list_keyboard(["only_one"])
    rows = kb["inline_keyboard"]
    assert len(rows) == 1
    assert len(rows[0]) == 1
    assert rows[0][0]["text"] == "only_one"
    assert rows[0][0]["callback_data"] == "skill:only_one"


# --- mode_keyboard ---


def test_mode_keyboard_marks_current_mode_chat():
    kb = mode_keyboard("chat")
    rows = kb["inline_keyboard"]

    # Should have buttons in a grid
    all_buttons = [btn for row in rows for btn in row]
    assert len(all_buttons) == 2

    # Find the chat button - it should be marked with ">"
    chat_btn = None
    skill_btn = None
    for btn in all_buttons:
        if btn["callback_data"] == "mode:chat":
            chat_btn = btn
        elif btn["callback_data"] == "mode:skill":
            skill_btn = btn

    assert chat_btn is not None
    assert skill_btn is not None
    assert chat_btn["text"].startswith("> ")
    assert not skill_btn["text"].startswith("> ")


def test_mode_keyboard_marks_current_mode_skill():
    kb = mode_keyboard("skill")
    all_buttons = [btn for row in kb["inline_keyboard"] for btn in row]

    chat_btn = next(btn for btn in all_buttons if btn["callback_data"] == "mode:chat")
    skill_btn = next(btn for btn in all_buttons if btn["callback_data"] == "mode:skill")

    assert not chat_btn["text"].startswith("> ")
    assert skill_btn["text"].startswith("> ")


def test_mode_keyboard_default_is_chat():
    kb = mode_keyboard()
    all_buttons = [btn for row in kb["inline_keyboard"] for btn in row]

    chat_btn = next(btn for btn in all_buttons if btn["callback_data"] == "mode:chat")
    assert chat_btn["text"].startswith("> ")


def test_mode_keyboard_callback_data():
    kb = mode_keyboard("chat")
    all_buttons = [btn for row in kb["inline_keyboard"] for btn in row]
    callback_values = {btn["callback_data"] for btn in all_buttons}
    assert "mode:chat" in callback_values
    assert "mode:skill" in callback_values
