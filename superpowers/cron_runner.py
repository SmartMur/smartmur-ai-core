"""Entry point for the cron daemon — launched by launchd."""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

LOG_DIR = Path.home() / ".claude-superpowers" / "logs"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "cron-daemon.log"

    logger = logging.getLogger("cron-daemon")
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

    # Import CronEngine (built by another agent)
    from superpowers.cron_engine import CronEngine

    engine = CronEngine()
    job_count = len(engine.jobs) if hasattr(engine, "jobs") else 0

    logger.info("=" * 50)
    logger.info("claude-superpowers cron daemon starting")
    logger.info("PID: %d", os.getpid())
    logger.info("Jobs loaded: %d", job_count)
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
        engine.start()  # blocks until engine.stop() is called
    except Exception:
        logger.exception("Cron engine crashed")
        sys.exit(1)

    logger.info("Cron daemon stopped cleanly (PID %d)", os.getpid())


if __name__ == "__main__":
    main()
