"""InlineKeyboardMarkup builder helpers for Telegram."""

from __future__ import annotations

from typing import Any


def inline_button(text: str, callback_data: str) -> dict[str, str]:
    """Create a single inline keyboard button."""
    return {"text": text, "callback_data": callback_data}


def inline_keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    """Build an InlineKeyboardMarkup payload."""
    return {"inline_keyboard": rows}


def single_row(*buttons: dict[str, str]) -> dict[str, Any]:
    """Build a keyboard with a single row of buttons."""
    return inline_keyboard([list(buttons)])


def button_grid(
    items: list[tuple[str, str]],
    columns: int = 2,
) -> dict[str, Any]:
    """Build a grid of buttons from (label, callback_data) tuples."""
    buttons = [inline_button(label, data) for label, data in items]
    rows = [buttons[i:i + columns] for i in range(0, len(buttons), columns)]
    return inline_keyboard(rows)


def confirm_keyboard(
    action: str,
    confirm_data: str = "confirm",
    cancel_data: str = "cancel",
) -> dict[str, Any]:
    """Build a confirm/cancel keyboard for an action."""
    return single_row(
        inline_button(f"Yes, {action}", confirm_data),
        inline_button("Cancel", cancel_data),
    )


def skill_list_keyboard(skills: list[str]) -> dict[str, Any]:
    """Build a keyboard for skill selection."""
    items = [(name, f"skill:{name}") for name in skills[:20]]  # Telegram limit
    return button_grid(items, columns=2)


def mode_keyboard(current_mode: str = "chat") -> dict[str, Any]:
    """Build a keyboard for mode selection."""
    modes = [
        ("Chat Mode", "mode:chat"),
        ("Skill Mode", "mode:skill"),
    ]
    # Mark current mode
    items = [
        (f"{'> ' if data.endswith(current_mode) else ''}{label}", data)
        for label, data in modes
    ]
    return button_grid(items, columns=2)
