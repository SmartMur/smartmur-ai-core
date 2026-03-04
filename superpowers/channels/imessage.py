"""iMessage channel adapter using macOS AppleScript."""

from __future__ import annotations

import subprocess
import sys

from superpowers.channels.base import Channel, ChannelType, SendResult


class IMessageChannel(Channel):
    channel_type = ChannelType.imessage

    def send(self, target: str, message: str) -> SendResult:
        if sys.platform != "darwin":
            return SendResult(
                ok=False,
                channel="imessage",
                target=target,
                error="iMessage requires macOS",
            )

        escaped_msg = message.replace("\\", "\\\\").replace('"', '\\"')
        escaped_target = target.replace("\\", "\\\\").replace('"', '\\"')

        script = f'tell application "Messages" to send "{escaped_msg}" to buddy "{escaped_target}"'

        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            return SendResult(
                ok=True,
                channel="imessage",
                target=target,
                message="sent",
            )
        except subprocess.CalledProcessError as exc:
            return SendResult(
                ok=False,
                channel="imessage",
                target=target,
                error=exc.stderr.strip() or "osascript failed",
            )
        except FileNotFoundError:
            return SendResult(
                ok=False,
                channel="imessage",
                target=target,
                error="osascript not found",
            )
        except subprocess.TimeoutExpired:
            return SendResult(
                ok=False,
                channel="imessage",
                target=target,
                error="osascript timed out",
            )

    def test_connection(self) -> SendResult:
        if sys.platform != "darwin":
            return SendResult(
                ok=False,
                channel="imessage",
                target="",
                error="iMessage requires macOS",
            )

        script = 'tell application "System Events" to (name of processes) contains "Messages"'

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            output = result.stdout.strip()
            running = output == "true"
            return SendResult(
                ok=True,
                channel="imessage",
                target="",
                message=f"Messages.app running={running}",
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            err = exc.stderr.strip() if hasattr(exc, "stderr") and exc.stderr else str(exc)
            return SendResult(
                ok=False,
                channel="imessage",
                target="",
                error=err,
            )
