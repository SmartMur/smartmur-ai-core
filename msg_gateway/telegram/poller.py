"""Refactored TelegramPoller delegating to auth, commands, callbacks, session, concurrency."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time

from msg_gateway.telegram.api import TelegramApi
from msg_gateway.telegram.attachments import AttachmentHandler
from msg_gateway.telegram.auth import AuthGate
from msg_gateway.telegram.callbacks import CallbackHandler
from msg_gateway.telegram.commands import CommandRouter
from msg_gateway.telegram.concurrency import ConcurrencyGate
from msg_gateway.telegram.formatting import smart_chunk
from msg_gateway.telegram.session import SessionManager
from msg_gateway.telegram.types import Message, Update
from msg_gateway.telegram.verification import ChatVerification
from msg_gateway.telegram.webhook import WebhookHandler

logger = logging.getLogger(__name__)


class TelegramPoller:
    """Long-poll Telegram for incoming messages with full pipeline:

    parse → auth → route (command / callback / trigger / conversation)

    Supports both polling and webhook modes via TELEGRAM_MODE config.
    """

    def __init__(
        self,
        bot_token: str,
        trigger_manager: object | None = None,  # TriggerManager from inbound.py
        *,
        redis_url: str = "",
        allowed_chat_ids: list[str] | None = None,
        max_history: int = 20,
        session_ttl: int = 3600,
        max_per_chat: int = 2,
        max_global: int = 5,
        queue_overflow: int = 10,
        webhook_secret: str = "",
        admin_chat_id: str = "",
    ):
        self._token = bot_token
        self._triggers = trigger_manager
        self._offset = 0
        self._running = False

        # Shared state
        self._chat_modes: dict[str, str] = {}  # chat_id -> "chat" or "skill"

        # Components
        self._api = TelegramApi(bot_token)
        self._auth = AuthGate(allowed_ids=allowed_chat_ids)
        self._session = SessionManager(
            redis_url=redis_url,
            max_history=max_history,
            ttl=session_ttl,
        )
        self._concurrency = ConcurrencyGate(
            max_per_chat=max_per_chat,
            max_global=max_global,
            queue_overflow=queue_overflow,
        )
        self._commands = CommandRouter(
            api=self._api,
            session=self._session,
            chat_modes=self._chat_modes,
        )
        self._callbacks = CallbackHandler(
            api=self._api,
            chat_modes=self._chat_modes,
        )
        self._attachments = AttachmentHandler(api=self._api)
        self._verification = ChatVerification(
            api=self._api,
            auth=self._auth,
            admin_chat_id=admin_chat_id,
        )
        self._webhook_handler = WebhookHandler(
            secret_token=webhook_secret,
            update_handler=self._handle_update,
        )

    @property
    def webhook_handler(self) -> WebhookHandler:
        """Expose the webhook handler for the FastAPI route."""
        return self._webhook_handler

    @property
    def api(self) -> TelegramApi:
        """Expose the API client for external use."""
        return self._api

    def start(self) -> None:
        """Start the polling loop. Blocks until stop() is called."""
        self._running = True
        # Register command menu on startup
        self._commands.register_menu()
        logger.info("Telegram poller started (auth: %s)", "configured" if self._auth.is_configured else "OPEN")

        while self._running:
            try:
                self._poll()
            except Exception as exc:
                logger.error("Telegram poll error: %s", exc)
                time.sleep(5)

    def stop(self) -> None:
        self._running = False

    def _poll(self) -> None:
        resp = self._api.get_updates(offset=self._offset)
        if not resp.ok or not resp.result:
            return

        for update_data in resp.result:
            update = Update.from_dict(update_data)
            self._offset = update.update_id + 1
            self._handle_update(update)

    def _handle_update(self, update: Update) -> None:
        """Route an update through the pipeline."""
        # --- Callback query ---
        if update.callback_query:
            cb = update.callback_query
            chat_id = cb.chat_id
            if chat_id and self._auth.is_allowed(chat_id):
                self._callbacks.handle(cb)
            elif chat_id:
                self._api.answer_callback_query(cb.id, "Unauthorized", show_alert=True)
            return

        # --- Message ---
        msg = update.message
        if not msg or not msg.chat_id:
            return

        chat_id = msg.chat_id

        # Chat verification handshake for /start from unknown users
        if msg.is_command and msg.command == "start" and not self._auth.is_allowed(chat_id):
            self._verification.handle_start(msg)
            return

        # Auth gate
        if not self._auth.is_allowed(chat_id):
            return

        # Acknowledge receipt with reaction (fire-and-forget)
        if msg.message_id:
            self._api.set_message_reaction(chat_id, msg.message_id)

        # Voice messages — transcribe and route
        voice = msg.voice or msg.audio
        if voice:
            logger.info("Voice message from %s — transcribing", chat_id)
            threading.Thread(
                target=self._handle_voice, args=(voice, chat_id),
                daemon=True,
            ).start()
            return

        # Attachment handling (photos/documents)
        if msg.has_attachment:
            logger.info("Attachment from %s — processing", chat_id)
            threading.Thread(
                target=self._handle_attachment, args=(msg, chat_id),
                daemon=True,
            ).start()
            return

        text = msg.text
        if not text:
            return

        logger.info("Text from %s: %s", chat_id, text[:100])

        # Command routing
        if self._commands.can_handle(msg):
            self._commands.handle(msg)
            return

        # Trigger matching (from existing TriggerManager)
        if self._triggers:
            rule = self._triggers.match(text)
            if rule:
                output = self._triggers.execute(rule, text)
                if rule.reply:
                    for chunk in smart_chunk(output):
                        self._api.send_message(chat_id, chunk)
                return

        # Conversation handler
        self._route_conversation(text, chat_id)

    def _handle_voice(self, voice: object, chat_id: str) -> None:
        """Download, transcribe, and reply with voice message text."""
        try:
            from superpowers.voice_transcriber import download_telegram_voice, transcribe
        except ImportError:
            self._api.send_message(chat_id, "[Voice transcription not available]")
            return

        file_id = getattr(voice, "file_id", "") or (voice.get("file_id", "") if isinstance(voice, dict) else "")
        if not file_id:
            return

        audio_path = download_telegram_voice(self._token, file_id)
        if not audio_path:
            self._api.send_message(chat_id, "[Could not download voice message]")
            return

        try:
            text = transcribe(audio_path)
            self._api.send_message(chat_id, f"Transcription:\n\n{text}")
            if text and not text.startswith("["):
                self._route_conversation(text, chat_id)
        finally:
            audio_path.unlink(missing_ok=True)
            audio_path.parent.rmdir()

    def _handle_attachment(self, msg: Message, chat_id: str) -> None:
        """Process photo/document attachments and route extracted content."""
        try:
            self._api.send_chat_action(chat_id)
            extracted = self._attachments.process_message(msg)
            if not extracted:
                self._api.send_message(chat_id, "[Could not process attachment]")
                return

            # Route the extracted content as a conversation message
            self._route_conversation(extracted, chat_id)
        except Exception as exc:
            logger.error("Attachment handling error for %s: %s", chat_id, exc)
            self._api.send_message(chat_id, f"[Attachment error: {exc}]")

    def _route_conversation(self, text: str, chat_id: str) -> None:
        """Route text through session + concurrency to Claude or intake."""
        mode = self._chat_modes.get(chat_id, "chat")
        logger.info("Routing conversation for %s (mode=%s): %s", chat_id, mode, text[:80])

        # Add to session history
        self._session.add(chat_id, "user", text)

        # Concurrency check
        if not self._concurrency.try_acquire(chat_id):
            logger.warning("Concurrency gate blocked %s", chat_id)
            self._api.send_message(
                chat_id,
                "Too many requests — please wait for current jobs to finish.",
            )
            return

        logger.info("Spawning conversation worker for %s", chat_id)
        threading.Thread(
            target=self._conversation_worker,
            args=(text, chat_id, mode),
            daemon=True,
            name=f"conv-{chat_id}",
        ).start()

    def _conversation_worker(self, text: str, chat_id: str, mode: str) -> None:
        """Process a conversation message (runs in background thread)."""
        logger.info("Conversation worker started for %s (mode=%s)", chat_id, mode)
        try:
            self._api.send_chat_action(chat_id)

            if mode == "skill":
                reply = self._skill_mode(text, chat_id)
            else:
                reply = self._chat_mode(text, chat_id)

            if reply:
                self._session.add(chat_id, "assistant", reply)
                for chunk in smart_chunk(reply):
                    self._api.send_message(chat_id, chunk)
        except Exception as exc:
            logger.error("Conversation error for %s: %s", chat_id, exc)
            self._api.send_message(chat_id, f"[Error: {exc}]")
        finally:
            self._concurrency.release(chat_id)

    def _chat_mode(self, text: str, chat_id: str) -> str:
        """Process text in chat mode — send to Claude CLI with history context."""
        logger.info("Chat mode for %s — building prompt", chat_id)
        context = self._session.format_context(chat_id)
        prompt = text
        if context:
            prompt = f"Previous conversation:\n{context}\n\nCurrent message: {text}"

        logger.info("Calling Claude CLI for %s (prompt length=%d)", chat_id, len(prompt))
        try:
            env = {
                k: v for k, v in os.environ.items()
                if k != "CLAUDECODE" and not (k == "ANTHROPIC_API_KEY" and not v)
            }
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "text"],
                capture_output=True, text=True, timeout=300, env=env,
            )
            reply = (result.stdout or result.stderr or "[no response]").strip()
            logger.info("Claude replied for %s (%d chars, rc=%d)", chat_id, len(reply), result.returncode)
            return reply
        except subprocess.TimeoutExpired:
            return "[Response timed out — try a shorter question]"
        except FileNotFoundError:
            return "[Claude CLI not found]"

    def _skill_mode(self, text: str, chat_id: str) -> str:
        """Process text in skill mode — route to intake pipeline."""
        try:
            from superpowers.intake import run_intake

            def progress_cb(msg: str) -> None:
                self._api.send_message(chat_id, f"[Progress] {msg}")

            result = run_intake(text, execute=True, progress_callback=progress_cb)
            tasks = result.get("tasks", [])
            ok = sum(1 for t in tasks if t.get("status") == "ok")
            failed = sum(1 for t in tasks if t.get("status") == "failed")
            return f"Intake complete: {ok} ok, {failed} failed, {len(tasks)} total"
        except Exception as exc:
            return f"Intake error: {exc}"
