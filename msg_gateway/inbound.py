"""Inbound message triggers — listen for commands on Slack/Telegram and dispatch."""

from __future__ import annotations

import json
import logging
import re
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
            triggers_path = Path.home() / ".claude-superpowers" / "triggers.yaml"
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
                self.rules.append(TriggerRule(
                    pattern=entry["pattern"],
                    action=entry.get("action", "shell"),
                    command=entry["command"],
                    reply=entry.get("reply", True),
                ))

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
                    rule.command, shell=True, capture_output=True,
                    text=True, timeout=120, env={**__import__("os").environ, **env},
                )
                return result.stdout + result.stderr
            elif rule.action == "claude":
                result = subprocess.run(
                    ["claude", "-p", rule.command, "--output-format", "text"],
                    capture_output=True, text=True, timeout=300,
                )
                return result.stdout + result.stderr
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
        except Exception as exc:
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
            except Exception as exc:
                logger.error("Telegram poll error: %s", exc)
                time.sleep(5)

    def stop(self) -> None:
        self._running = False

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
                self._handle_voice(voice, chat_id)
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
            # Also respond to the transcribed content
            if text and not text.startswith("["):
                self._reply_with_claude(text, chat_id)
        finally:
            # Clean up temp file
            audio_path.unlink(missing_ok=True)
            audio_path.parent.rmdir()


    def _reply_with_claude(self, text: str, chat_id: str) -> None:
        """Send text to Claude CLI and reply with the response."""
        logger.info("Routing to Claude: %s", text[:100])
        try:
            env = {k: v for k, v in __import__("os").environ.items() if k != "CLAUDECODE"}
            result = subprocess.run(
                ["claude", "-p", text, "--output-format", "text"],
                capture_output=True, text=True, timeout=120, env=env,
            )
            reply = (result.stdout or result.stderr or "[no response]").strip()
            if reply:
                ch = self._registry.get("telegram")
                # Telegram has a 4096 char limit
                for i in range(0, len(reply), 4000):
                    ch.send(chat_id, reply[i:i + 4000])
                logger.info("Claude replied to %s (%d chars)", chat_id, len(reply))
        except subprocess.TimeoutExpired:
            ch = self._registry.get("telegram")
            ch.send(chat_id, "[Response timed out — try a shorter question]")
            logger.warning("Claude timed out for %s", chat_id)
        except FileNotFoundError:
            ch = self._registry.get("telegram")
            ch.send(chat_id, "[Claude CLI not found on this system]")
            logger.error("claude CLI not found")
        except Exception as exc:
            logger.error("Claude reply error: %s", exc)


class InboundListener:
    """Coordinates all inbound channel listeners."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings.load()
        self._registry = ChannelRegistry(self._settings)
        self._triggers = TriggerManager()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if self._settings.telegram_bot_token:
            poller = TelegramPoller(
                self._settings.telegram_bot_token,
                self._triggers,
                self._registry,
            )
            t = threading.Thread(target=poller.start, daemon=True, name="telegram-poller")
            t.start()
            self._threads.append(t)
            logger.info("Telegram inbound listener started")

        if not self._threads:
            logger.warning("No inbound listeners configured")

    def stop(self) -> None:
        # Daemon threads will be cleaned up on process exit
        pass
