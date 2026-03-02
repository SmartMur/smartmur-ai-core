"""Inline keyboard callback query handler."""

from __future__ import annotations

import logging
from typing import Callable

from msg_gateway.telegram.api import TelegramApi
from msg_gateway.telegram.types import CallbackQuery

logger = logging.getLogger(__name__)


class CallbackHandler:
    """Routes callback queries from inline keyboard buttons."""

    def __init__(self, api: TelegramApi, chat_modes: dict[str, str] | None = None):
        self._api = api
        self._chat_modes = chat_modes or {}
        self._handlers: dict[str, Callable] = {
            "skill": self._handle_skill,
            "mode": self._handle_mode,
            "confirm": self._handle_confirm,
            "cancel": self._handle_cancel,
        }

    def handle(self, query: CallbackQuery) -> None:
        """Route a callback query to the appropriate handler."""
        if not query.data:
            self._api.answer_callback_query(query.id, "No data")
            return

        # Parse callback data format: "prefix:value" or just "prefix"
        parts = query.data.split(":", 1)
        prefix = parts[0]
        value = parts[1] if len(parts) > 1 else ""

        handler = self._handlers.get(prefix)
        if handler:
            try:
                handler(query, value)
            except Exception as exc:
                logger.error("Callback handler error for %s: %s", query.data, exc)
                self._api.answer_callback_query(query.id, f"Error: {exc}", show_alert=True)
        else:
            self._api.answer_callback_query(query.id, f"Unknown action: {prefix}")

    def _handle_skill(self, query: CallbackQuery, skill_name: str) -> None:
        """Handle skill selection from keyboard."""
        chat_id = query.chat_id
        self._api.answer_callback_query(query.id, f"Running {skill_name}...")

        self._api.send_message(chat_id, f"Running skill: {skill_name}...")
        try:
            from superpowers.skill_loader import SkillLoader
            from superpowers.skill_registry import SkillRegistry
            registry = SkillRegistry()
            loader = SkillLoader()
            skill = registry.get(skill_name)
            result = loader.run(skill)
            output = (result.stdout + result.stderr).strip()[:3000]
            status = "completed" if result.returncode == 0 else "failed"
            self._api.send_message(chat_id, f"Skill {skill_name} {status}:\n\n{output}")
        except Exception as exc:
            self._api.send_message(chat_id, f"Skill execution error: {exc}")

    def _handle_mode(self, query: CallbackQuery, mode: str) -> None:
        """Handle mode switch from keyboard."""
        chat_id = query.chat_id
        if mode in ("chat", "skill"):
            self._chat_modes[chat_id] = mode
            self._api.answer_callback_query(query.id, f"Mode: {mode}")
            self._api.send_message(chat_id, f"Mode switched to: {mode}")
        else:
            self._api.answer_callback_query(query.id, f"Unknown mode: {mode}")

    def _handle_confirm(self, query: CallbackQuery, value: str) -> None:
        """Handle confirmation button."""
        self._api.answer_callback_query(query.id, "Confirmed")
        self._api.send_message(query.chat_id, f"Action confirmed: {value}")

    def _handle_cancel(self, query: CallbackQuery, value: str) -> None:
        """Handle cancel button."""
        self._api.answer_callback_query(query.id, "Cancelled")
        self._api.send_message(query.chat_id, "Action cancelled.")
