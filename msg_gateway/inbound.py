"""Inbound message triggers — listen for commands on Slack/Telegram and dispatch."""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class TriggerRule:
    pattern: str
    action: str  # "shell", "claude", "skill"
    command: str
    reply: bool = True
    compiled: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        self.compiled = re.compile(self.pattern, re.IGNORECASE)


class TriggerManager:
    """Load trigger rules from YAML and match incoming messages."""

    def __init__(self, triggers_path: Path | None = None):
        if triggers_path is None:
            from superpowers.config import get_data_dir

            triggers_path = get_data_dir() / "triggers.yaml"
        self._path = triggers_path
        self.rules: list[TriggerRule] = []
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = yaml.safe_load(self._path.read_text()) or []
        except (yaml.YAMLError, OSError):
            return

        for entry in data:
            if isinstance(entry, dict) and "pattern" in entry and "command" in entry:
                self.rules.append(
                    TriggerRule(
                        pattern=entry["pattern"],
                        action=entry.get("action", "shell"),
                        command=entry["command"],
                        reply=entry.get("reply", True),
                    )
                )

    def match(self, text: str) -> TriggerRule | None:
        for rule in self.rules:
            if rule.compiled.search(text):
                return rule
        return None

    def execute(self, rule: TriggerRule, message_text: str) -> str:
        """Execute a trigger rule and return the output."""
        env = {"TRIGGER_MESSAGE": message_text}
        try:
            if rule.action == "shell":
                result = subprocess.run(
                    shlex.split(rule.command),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env={**os.environ, **env},
                )
                return result.stdout + result.stderr
            elif rule.action == "claude":
                from superpowers.llm_provider import get_default_provider

                provider = get_default_provider(role="chat")
                return provider.invoke(rule.command)
            elif rule.action == "skill":
                from superpowers.skill_loader import SkillLoader
                from superpowers.skill_registry import SkillRegistry

                registry = SkillRegistry()
                loader = SkillLoader()
                skill = registry.get(rule.command)
                r = loader.run(skill)
                return r.stdout + r.stderr
            else:
                return f"Unknown action type: {rule.action}"
        except (subprocess.SubprocessError, OSError, ImportError, KeyError, RuntimeError) as exc:
            return f"Trigger execution error: {exc}"


class TelegramPoller:
    """Long-poll Telegram for incoming messages and dispatch triggers."""

    def __init__(
        self,
        bot_token: str,
        trigger_manager: TriggerManager,
        registry: ChannelRegistry,
    ):
        self._token = bot_token
        self._triggers = trigger_manager
        self._registry = registry
        self._offset = 0
        self._running = False

    def start(self) -> None:
        self._running = True
        logger.info("Telegram poller started")
        while self._running:
            try:
                self._poll()
            except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
                logger.error("Telegram poll error: %s", exc)
                time.sleep(5)

    def stop(self) -> None:
        self._running = False

    def _tg_api(self, method: str, payload: dict) -> None:
        """Fire-and-forget Telegram API call."""
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except (urllib.error.URLError, OSError):
            pass

    def _send_typing(self, chat_id: str) -> None:
        self._tg_api("sendChatAction", {"chat_id": chat_id, "action": "typing"})

    def _poll(self) -> None:
        url = f"https://api.telegram.org/bot{self._token}/getUpdates"
        params = f"?offset={self._offset}&timeout=30"
        req = urllib.request.Request(url + params)
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError):
            time.sleep(2)
            return

        if not data.get("ok"):
            return

        for update in data.get("result", []):
            self._offset = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))

            if not chat_id:
                continue

            # Handle voice messages — transcribe and reply
            voice = msg.get("voice") or msg.get("audio")
            if voice:
                logger.info("Voice message from %s — transcribing", chat_id)
                threading.Thread(
                    target=self._handle_voice,
                    args=(voice, chat_id),
                    daemon=True,
                ).start()
                continue

            text = msg.get("text", "")
            if not text:
                continue

            logger.info("Text from %s: %s", chat_id, text[:100])

            rule = self._triggers.match(text)
            if rule:
                output = self._triggers.execute(rule, text)
                if rule.reply:
                    ch = self._registry.get("telegram")
                    ch.send(chat_id, output[:4000])
            else:
                # No trigger — route to Claude for AI response
                self._reply_with_claude(text, chat_id)

    def _handle_voice(self, voice: dict, chat_id: str) -> None:
        """Download, transcribe, and reply with voice message text."""
        from superpowers.voice_transcriber import download_telegram_voice, transcribe

        file_id = voice.get("file_id")
        if not file_id:
            return

        duration = voice.get("duration", "?")
        logger.info("Voice message from %s (%ss) — transcribing", chat_id, duration)

        audio_path = download_telegram_voice(self._token, file_id)
        if not audio_path:
            ch = self._registry.get("telegram")
            ch.send(chat_id, "[Could not download voice message]")
            return

        try:
            text = transcribe(audio_path)
            ch = self._registry.get("telegram")
            ch.send(chat_id, f"🎙 *Transcription:*\n\n{text}")
            logger.info("Transcribed voice from %s: %s", chat_id, text[:100])
            if text and not text.startswith("["):
                self._reply_with_claude(text, chat_id)
        finally:
            audio_path.unlink(missing_ok=True)
            audio_path.parent.rmdir()

    def _reply_with_claude(self, text: str, chat_id: str) -> None:
        """Route to Claude in a background thread so the poller isn't blocked."""
        threading.Thread(
            target=self._claude_worker,
            args=(text, chat_id),
            daemon=True,
            name=f"claude-{chat_id}",
        ).start()

    def _claude_worker(self, text: str, chat_id: str) -> None:
        """Send text to Claude CLI and reply with the response."""
        self._send_typing(chat_id)
        logger.info("Routing to Claude: %s", text[:100])
        try:
            env = {
                k: v
                for k, v in os.environ.items()
                if k != "CLAUDECODE" and not (k == "ANTHROPIC_API_KEY" and not v)
            }
            result = subprocess.run(
                ["claude", "-p", text, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )
            reply = (result.stdout or result.stderr or "[no response]").strip()
            if reply:
                self._send_reply(chat_id, reply)
                logger.info("Claude replied to %s (%d chars)", chat_id, len(reply))
        except subprocess.TimeoutExpired:
            self._send_reply(chat_id, "[Response timed out — try a shorter question]")
            logger.warning("Claude timed out for %s", chat_id)
        except FileNotFoundError:
            self._send_reply(chat_id, "[Claude CLI not found]")
            logger.error("claude CLI not found")
        except (RuntimeError, OSError) as exc:
            logger.error("Claude reply error: %s", exc)

    def _send_reply(self, chat_id: str, text: str) -> None:
        """Send reply, splitting at Telegram's 4096 char limit."""
        ch = self._registry.get("telegram")
        for i in range(0, len(text), 4000):
            ch.send(chat_id, text[i : i + 4000])


class InboundListener:
    """Coordinates all inbound channel listeners."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings.load()
        self._registry = ChannelRegistry(self._settings)
        self._triggers = TriggerManager()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if self._settings.telegram_bot_token:
            # Use the refactored poller from msg_gateway.telegram package
            from msg_gateway.telegram.poller import TelegramPoller as NewPoller

            # Parse allowed chat IDs from settings
            allowed_ids = None
            if hasattr(self._settings, "allowed_chat_ids") and self._settings.allowed_chat_ids:
                allowed_ids = [
                    cid.strip() for cid in self._settings.allowed_chat_ids.split(",") if cid.strip()
                ]

            poller = NewPoller(
                self._settings.telegram_bot_token,
                trigger_manager=self._triggers,
                redis_url=self._settings.redis_url,
                allowed_chat_ids=allowed_ids,
                max_history=getattr(self._settings, "telegram_max_history", 20),
                session_ttl=getattr(self._settings, "telegram_session_ttl", 3600),
                max_per_chat=getattr(self._settings, "telegram_max_per_chat", 2),
                max_global=getattr(self._settings, "telegram_max_global", 5),
                queue_overflow=getattr(self._settings, "telegram_queue_overflow", 10),
                webhook_secret=getattr(self._settings, "telegram_webhook_secret", ""),
                admin_chat_id=getattr(self._settings, "telegram_admin_chat_id", ""),
            )

            mode = getattr(self._settings, "telegram_mode", "polling")
            if mode == "webhook":
                # In webhook mode, register poller with the FastAPI app
                # instead of running the polling loop
                from msg_gateway.app import set_telegram_poller

                set_telegram_poller(poller)
                # Still register command menu
                poller._commands.register_menu()
                # Set up webhook with Telegram
                webhook_url = getattr(self._settings, "telegram_webhook_url", "")
                webhook_secret = getattr(self._settings, "telegram_webhook_secret", "")
                if webhook_url:
                    resp = poller.api.set_webhook(
                        url=webhook_url,
                        secret_token=webhook_secret,
                    )
                    if resp.ok:
                        logger.info("Telegram webhook set to %s", webhook_url)
                    else:
                        logger.error("Failed to set webhook: %s", resp.description)
                logger.info("Telegram inbound listener started (webhook mode)")
            else:
                t = threading.Thread(target=poller.start, daemon=True, name="telegram-poller")
                t.start()
                self._threads.append(t)
                logger.info("Telegram inbound listener started (polling mode)")

        if not self._threads:
            logger.warning("No inbound listeners configured")

    def stop(self) -> None:
        # Daemon threads will be cleaned up on process exit
        pass
