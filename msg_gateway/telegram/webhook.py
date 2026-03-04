"""Telegram webhook handler — receives updates via HTTP POST."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from msg_gateway.telegram.types import Update

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Processes incoming Telegram webhook updates.

    This class handles the parsing and validation of webhook requests.
    The actual update processing is delegated to a callback (typically
    TelegramPoller._handle_update).
    """

    def __init__(
        self,
        secret_token: str = "",
        update_handler: Callable[[Update], None] | None = None,
    ):
        self._secret_token = secret_token
        self._update_handler = update_handler

    @property
    def has_secret(self) -> bool:
        return bool(self._secret_token)

    def validate_secret(self, provided_secret: str) -> bool:
        """Validate the X-Telegram-Bot-Api-Secret-Token header.

        Fail-closed: if a secret is configured, reject requests without
        a matching token. If no secret is configured, accept all requests.
        """
        if not self._secret_token:
            # No secret configured — accept all (not recommended for production)
            return True
        return provided_secret == self._secret_token

    def process_update(self, data: dict[str, Any]) -> bool:
        """Parse and dispatch a webhook update.

        Returns True if the update was processed successfully.
        """
        if not data:
            logger.warning("Webhook received empty update")
            return False

        try:
            update = Update.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Failed to parse webhook update: %s", exc)
            return False

        if not update.update_id:
            logger.warning("Webhook update missing update_id")
            return False

        if self._update_handler:
            try:
                self._update_handler(update)
                return True
            except (RuntimeError, KeyError, ValueError, OSError) as exc:
                logger.error("Webhook update handler error: %s", exc)
                return False

        logger.warning("No update handler registered for webhook")
        return False
