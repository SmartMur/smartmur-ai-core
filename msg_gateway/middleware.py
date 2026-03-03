"""Security middleware for the message gateway.

Provides:
- Webhook signature validation (Telegram, Slack, Discord) -- fail-closed
- Per-IP rate limiting with token bucket algorithm
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Health-check paths exempt from all middleware checks
# ---------------------------------------------------------------------------
HEALTH_PATHS: set[str] = {"/health", "/api/health"}


# ===========================================================================
# Webhook Signature Validation
# ===========================================================================

def _verify_telegram(request: Request, body: bytes) -> bool:
    """Validate Telegram webhook via X-Telegram-Bot-Api-Secret-Token header.

    Telegram sends a configurable secret token in this header when delivering
    webhook updates.  The expected value is set via TELEGRAM_WEBHOOK_SECRET.
    """
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not expected:
        # No secret configured -- reject (fail-closed)
        logger.warning("TELEGRAM_WEBHOOK_SECRET not set; rejecting webhook")
        return False
    actual = request.headers.get("x-telegram-bot-api-secret-token", "")
    return hmac.compare_digest(actual, expected)


def _verify_slack(request: Request, body: bytes) -> bool:
    """Validate Slack webhook via X-Slack-Signature + X-Slack-Request-Timestamp.

    Uses Slack's v0 signing scheme: HMAC-SHA256 of "v0:{timestamp}:{body}".
    """
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not signing_secret:
        logger.warning("SLACK_SIGNING_SECRET not set; rejecting webhook")
        return False

    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")
    if not timestamp or not signature:
        return False

    # Reject requests older than 5 minutes to prevent replay attacks
    try:
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("Slack webhook timestamp too old")
            return False
    except ValueError:
        return False

    basestring = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}"
    computed = "v0=" + hmac.new(
        signing_secret.encode(), basestring.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def _verify_discord(request: Request, body: bytes) -> bool:
    """Validate Discord webhook via X-Signature-Ed25519 + X-Signature-Timestamp.

    Discord uses Ed25519 signatures.  We require the PyNaCl library for
    verification.  If PyNaCl is unavailable we reject (fail-closed).
    """
    public_key_hex = os.environ.get("DISCORD_PUBLIC_KEY", "")
    if not public_key_hex:
        logger.warning("DISCORD_PUBLIC_KEY not set; rejecting webhook")
        return False

    signature = request.headers.get("x-signature-ed25519", "")
    timestamp = request.headers.get("x-signature-timestamp", "")
    if not signature or not timestamp:
        return False

    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(
            timestamp.encode() + body,
            bytes.fromhex(signature),
        )
        return True
    except ImportError:
        logger.warning("PyNaCl not installed; cannot verify Discord signature")
        return False
    except (BadSignatureError, ValueError, Exception) as exc:
        logger.warning("Discord signature verification failed: %s", exc)
        return False


# Map path prefixes to verification functions
_WEBHOOK_VERIFIERS: dict[str, callable] = {
    "/webhook/telegram": _verify_telegram,
    "/webhook/slack": _verify_slack,
    "/webhook/discord": _verify_discord,
}


class WebhookSignatureMiddleware(BaseHTTPMiddleware):
    """Fail-closed webhook signature validation.

    All POST requests to ``/webhook/*`` paths MUST carry a valid signature.
    Requests without a valid signature receive a 401 Unauthorized response.

    Set ``WEBHOOK_REQUIRE_SIGNATURE=false`` to disable (not recommended).
    """

    async def dispatch(self, request: Request, call_next):
        # Skip non-POST or health endpoints
        if request.method != "POST" or request.url.path in HEALTH_PATHS:
            return await call_next(request)

        # Only validate webhook paths
        path = request.url.path
        verifier = None
        for prefix, fn in _WEBHOOK_VERIFIERS.items():
            if path.startswith(prefix):
                verifier = fn
                break

        if verifier is None:
            # Not a webhook path -- pass through
            return await call_next(request)

        # Check if signature validation is enabled
        require_sig = os.environ.get("WEBHOOK_REQUIRE_SIGNATURE", "true").lower()
        if require_sig in ("false", "0", "no"):
            return await call_next(request)

        # Read body for signature verification
        body = await request.body()

        if not verifier(request, body):
            logger.warning(
                "Webhook signature validation failed for %s from %s",
                path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing webhook signature"},
            )

        return await call_next(request)


# ===========================================================================
# Token Bucket Rate Limiter
# ===========================================================================

@dataclass
class _TokenBucket:
    """Simple token bucket for rate limiting."""

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        self.tokens = self.capacity

    def consume(self) -> bool:
        """Try to consume one token.  Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP token-bucket rate limiter.

    Configurable via environment variables:
    - ``RATE_LIMIT_PER_IP``: max requests per minute per IP (default 60)
    - ``RATE_LIMIT_PER_USER``: max requests per minute per authenticated user (default 120)

    Health-check endpoints are exempt.
    """

    def __init__(self, app, per_ip: int | None = None, per_user: int | None = None):
        super().__init__(app)
        self._per_ip = per_ip or int(os.environ.get("RATE_LIMIT_PER_IP", "60"))
        self._per_user = per_user or int(os.environ.get("RATE_LIMIT_PER_USER", "120"))
        # Buckets keyed by IP or "user:{username}"
        self._ip_buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(
                capacity=self._per_ip,
                refill_rate=self._per_ip / 60.0,
            )
        )
        self._user_buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(
                capacity=self._per_user,
                refill_rate=self._per_user / 60.0,
            )
        )
        self._last_cleanup = time.monotonic()

    def _cleanup_stale_buckets(self) -> None:
        """Remove buckets not used in the last 10 minutes to prevent memory leak."""
        now = time.monotonic()
        if now - self._last_cleanup < 600:
            return
        self._last_cleanup = now
        threshold = now - 600
        for store in (self._ip_buckets, self._user_buckets):
            stale = [k for k, v in store.items() if v.last_refill < threshold]
            for k in stale:
                del store[k]

    async def dispatch(self, request: Request, call_next):
        # Exempt health endpoints
        if request.url.path in HEALTH_PATHS:
            return await call_next(request)

        self._cleanup_stale_buckets()

        client_ip = request.client.host if request.client else "unknown"
        bucket = self._ip_buckets[client_ip]

        if not bucket.consume():
            logger.warning("Rate limit exceeded for IP %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60"},
            )

        # If there's an authenticated user, also check user bucket
        # (user is typically set by auth middleware upstream)
        username = getattr(request.state, "user", None) if hasattr(request, "state") else None
        if username:
            user_bucket = self._user_buckets[f"user:{username}"]
            if not user_bucket.consume():
                logger.warning("Rate limit exceeded for user %s", username)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"},
                )

        return await call_next(request)
