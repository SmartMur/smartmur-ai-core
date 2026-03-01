"""Redis pub/sub consumer for async message dispatch."""

from __future__ import annotations

import json
import logging

import redis

from superpowers.channels.base import ChannelError
from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings

logger = logging.getLogger(__name__)


class MessageBus:
    """Subscribes to Redis outbound:{channel} topics and dispatches messages."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings.load()
        self._registry = ChannelRegistry(self._settings)
        self._redis = redis.Redis.from_url(self._settings.redis_url)
        self._pubsub = self._redis.pubsub()
        self._running = False

    def start(self) -> None:
        channels = [f"outbound:{ch}" for ch in self._registry.available()]
        if not channels:
            logger.warning("No channels configured — bus has nothing to subscribe to")
            return

        self._pubsub.subscribe(*channels)
        self._running = True
        logger.info("Message bus subscribed to: %s", channels)

        for msg in self._pubsub.listen():
            if not self._running:
                break
            if msg["type"] != "message":
                continue

            try:
                data = json.loads(msg["data"])
                channel_name = msg["channel"].decode().split(":", 1)[1]
                target = data["target"]
                message = data["message"]

                ch = self._registry.get(channel_name)
                result = ch.send(target, message)
                if result.ok:
                    logger.info("Sent to %s:%s", channel_name, target)
                else:
                    logger.error("Failed %s:%s — %s", channel_name, target, result.error)
            except (json.JSONDecodeError, KeyError, ChannelError) as exc:
                logger.error("Bus dispatch error: %s", exc)

    def stop(self) -> None:
        self._running = False
        self._pubsub.unsubscribe()
        self._pubsub.close()
