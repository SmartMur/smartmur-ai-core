"""Email channel adapter using smtplib."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult


class EmailChannel(Channel):
    channel_type = ChannelType.email

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        from_addr: str = "",
        port: int = 587,
    ):
        if not host:
            raise ChannelError("SMTP host is required")
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from = from_addr or user

    def send(self, target: str, message: str) -> SendResult:
        subject, _, body = message.partition("\n")
        if not body:
            body = subject
            subject = "Claude Superpowers notification"

        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = target
        msg["Subject"] = subject
        msg.set_content(body.strip())

        try:
            with smtplib.SMTP(self._host, self._port, timeout=15) as srv:
                srv.starttls()
                srv.login(self._user, self._password)
                srv.send_message(msg)
            return SendResult(ok=True, channel="email", target=target, message="sent")
        except smtplib.SMTPException as exc:
            return SendResult(ok=False, channel="email", target=target, error=str(exc))
        except (OSError, ConnectionError, TimeoutError) as exc:
            return SendResult(
                ok=False,
                channel="email",
                target=target,
                error=f"Unexpected error: {exc}",
            )

    def test_connection(self) -> SendResult:
        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as srv:
                srv.ehlo()
                srv.starttls()
                srv.login(self._user, self._password)
            return SendResult(
                ok=True,
                channel="email",
                target="",
                message=f"host={self._host}:{self._port}, user={self._user}",
            )
        except (smtplib.SMTPException, OSError) as exc:
            return SendResult(ok=False, channel="email", target="", error=str(exc))
        except (OSError, ConnectionError, TimeoutError) as exc:
            return SendResult(
                ok=False,
                channel="email",
                target="",
                error=f"Unexpected error: {exc}",
            )
