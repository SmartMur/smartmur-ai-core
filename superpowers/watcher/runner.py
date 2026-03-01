"""Entry point for the watcher daemon — launched by launchd."""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

LOG_DIR = Path.home() / ".claude-superpowers" / "logs"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "watcher-daemon.log"

    logger = logging.getLogger("watcher-engine")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_file)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def main() -> None:
    logger = setup_logging()

    from superpowers.watcher.engine import WatcherEngine

    engine = WatcherEngine()
    rule_count = len(engine.list_rules())

    logger.info("=" * 50)
    logger.info("claude-superpowers watcher daemon starting")
    logger.info("PID: %d", os.getpid())
    logger.info("Rules loaded: %d", rule_count)
    logger.info("=" * 50)

    shutdown = False

    def handle_signal(signum: int, _frame) -> None:
        nonlocal shutdown
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — shutting down gracefully", sig_name)
        shutdown = True
        engine.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        engine.start()
        # Block until shutdown signal
        signal.pause()
    except Exception:
        logger.exception("Watcher engine crashed")
        sys.exit(1)

    logger.info("Watcher daemon stopped cleanly (PID %d)", os.getpid())


if __name__ == "__main__":
    main()
