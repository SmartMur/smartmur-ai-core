"""Telegram slash command router — /start, /help, /status, /skills, /run, /mode, /history, /reset, /cancel."""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Callable

from msg_gateway.telegram.api import TelegramApi
from msg_gateway.telegram.formatting import escape_markdown_v2
from msg_gateway.telegram.keyboards import mode_keyboard, skill_list_keyboard
from msg_gateway.telegram.session import SessionManager
from msg_gateway.telegram.types import Message

logger = logging.getLogger(__name__)

# Bot command definitions for setMyCommands
COMMAND_MENU = [
    {"command": "start", "description": "Start the bot"},
    {"command": "help", "description": "Show available commands"},
    {"command": "status", "description": "Show system status"},
    {"command": "skills", "description": "List available skills"},
    {"command": "run", "description": "Run a skill by name"},
    {"command": "mode", "description": "Switch chat/skill mode"},
    {"command": "history", "description": "Show conversation history"},
    {"command": "reset", "description": "Clear conversation history"},
    {"command": "cancel", "description": "Cancel running job"},
]


class CommandRouter:
    """Routes slash commands to handler functions."""

    def __init__(
        self,
        api: TelegramApi,
        session: SessionManager,
        chat_modes: dict[str, str] | None = None,
    ):
        self._api = api
        self._session = session
        self._chat_modes = chat_modes or {}
        self._handlers: dict[str, Callable] = {
            "start": self._cmd_start,
            "help": self._cmd_help,
            "status": self._cmd_status,
            "skills": self._cmd_skills,
            "run": self._cmd_run,
            "mode": self._cmd_mode,
            "history": self._cmd_history,
            "reset": self._cmd_reset,
            "cancel": self._cmd_cancel,
        }

    def can_handle(self, message: Message) -> bool:
        return message.is_command and message.command in self._handlers

    def handle(self, message: Message) -> None:
        cmd = message.command
        handler = self._handlers.get(cmd)
        if handler:
            try:
                handler(message)
            except Exception as exc:
                logger.error("Command /%s error: %s", cmd, exc)
                self._reply(message.chat_id, f"Error executing /{cmd}: {exc}")

    def register_menu(self) -> None:
        """Register bot commands with Telegram via setMyCommands."""
        resp = self._api.set_my_commands(COMMAND_MENU)
        if resp.ok:
            logger.info("Bot command menu registered (%d commands)", len(COMMAND_MENU))
        else:
            logger.warning("Failed to register command menu: %s", resp.description)

    def _reply(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> None:
        self._api.send_message(
            chat_id, text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    # --- Command handlers ---

    def _cmd_start(self, msg: Message) -> None:
        name = msg.from_user.first_name if msg.from_user else "there"
        self._reply(
            msg.chat_id,
            f"Hey {name}! I'm your Claude Superpowers bot.\n\n"
            "Send me a message and I'll respond with Claude AI.\n"
            "Use /help to see all commands.\n"
            "Use /mode to switch between chat and skill mode.",
        )

    def _cmd_help(self, msg: Message) -> None:
        lines = ["Available commands:\n"]
        for cmd in COMMAND_MENU:
            lines.append(f"/{cmd['command']} — {cmd['description']}")
        lines.append("\nSend any text message for a Claude AI response.")
        self._reply(msg.chat_id, "\n".join(lines))

    def _cmd_status(self, msg: Message) -> None:
        mode = self._chat_modes.get(msg.chat_id, "chat")
        history = self._session.get(msg.chat_id)

        status_lines = [
            "System Status:",
            f"  Mode: {mode}",
            f"  History: {len(history)} messages",
        ]

        # Try to get cron/skill status
        try:
            result = subprocess.run(
                ["claw", "cron", "status"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                status_lines.append(f"  Cron: {result.stdout.strip()[:200]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        self._reply(msg.chat_id, "\n".join(status_lines))

    def _cmd_skills(self, msg: Message) -> None:
        try:
            from superpowers.skill_registry import SkillRegistry
            registry = SkillRegistry()
            skills = registry.list()
            if not skills:
                self._reply(msg.chat_id, "No skills installed. Use `claw skill auto-install` to add some.")
                return

            skill_names = [s.name for s in skills]
            self._reply(
                msg.chat_id,
                f"Available skills ({len(skill_names)}):\nTap one to run it.",
                reply_markup=skill_list_keyboard(skill_names),
            )
        except Exception as exc:
            self._reply(msg.chat_id, f"Could not list skills: {exc}")

    def _cmd_run(self, msg: Message) -> None:
        skill_name = msg.command_args.strip()
        if not skill_name:
            self._reply(msg.chat_id, "Usage: /run <skill_name>\n\nUse /skills to see available skills.")
            return

        self._reply(msg.chat_id, f"Running skill: {skill_name}...")
        try:
            from superpowers.skill_loader import SkillLoader
            from superpowers.skill_registry import SkillRegistry
            registry = SkillRegistry()
            loader = SkillLoader()
            skill = registry.get(skill_name)
            result = loader.run(skill)
            output = (result.stdout + result.stderr).strip()[:3000]
            status = "completed" if result.returncode == 0 else "failed"
            self._reply(msg.chat_id, f"Skill {skill_name} {status}:\n\n{output}")
        except Exception as exc:
            self._reply(msg.chat_id, f"Skill execution error: {exc}")

    def _cmd_mode(self, msg: Message) -> None:
        args = msg.command_args.strip().lower()
        current = self._chat_modes.get(msg.chat_id, "chat")

        if args in ("chat", "skill"):
            self._chat_modes[msg.chat_id] = args
            self._reply(msg.chat_id, f"Mode switched to: {args}")
            return

        self._reply(
            msg.chat_id,
            f"Current mode: {current}\n\nSelect a mode:",
            reply_markup=mode_keyboard(current),
        )

    def _cmd_history(self, msg: Message) -> None:
        entries = self._session.get(msg.chat_id)
        if not entries:
            self._reply(msg.chat_id, "No conversation history.")
            return

        lines = [f"Conversation history ({len(entries)} messages):\n"]
        for entry in entries[-10:]:  # Show last 10
            prefix = "You" if entry.role == "user" else "Bot"
            content = entry.content[:100]
            if len(entry.content) > 100:
                content += "..."
            lines.append(f"  {prefix}: {content}")

        self._reply(msg.chat_id, "\n".join(lines))

    def _cmd_reset(self, msg: Message) -> None:
        self._session.clear(msg.chat_id)
        self._reply(msg.chat_id, "Conversation history cleared.")

    def _cmd_cancel(self, msg: Message) -> None:
        # Cancel is a no-op for now — would need job tracking to implement fully
        self._reply(msg.chat_id, "No active jobs to cancel.")
