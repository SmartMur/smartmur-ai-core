"""File watcher subsystem — watchdog-based directory monitoring with action dispatch."""

from __future__ import annotations

from superpowers.watcher.base import WatchAction, WatcherError, WatchRule
from superpowers.watcher.engine import WatcherEngine

__all__ = ["WatchAction", "WatcherError", "WatchRule", "WatcherEngine"]
