"""Telegram bot entry point — runs the inbound listener with Claude AI responses."""

import logging
import signal
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("telegram-bot")


def main():
    from msg_gateway.inbound import InboundListener

    logger.info("Starting Telegram bot with Claude AI responses")
    stop = threading.Event()

    def handle_signal(signum, _frame):
        logger.info("Received signal %d — shutting down", signum)
        stop.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    listener = InboundListener()
    listener.start()

    logger.info("Bot is live — listening for messages")
    stop.wait()
    logger.info("Bot stopped")


if __name__ == "__main__":
    main()
