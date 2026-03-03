"""Security middleware for the dashboard application.

Provides per-IP and per-user rate limiting via a token bucket algorithm.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting
EXEMPT_PATHS: set[str] = {"/health", "/api/health"}


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
    """Per-IP token-bucket rate limiter for the dashboard.

    Configurable via environment variables:
    - ``RATE_LIMIT_PER_IP``: max requests per minute per IP (default 60)
    - ``RATE_LIMIT_PER_USER``: max requests per minute per authenticated user (default 120)

    Health-check endpoints are exempt.
    """

    def __init__(self, app, per_ip: int | None = None, per_user: int | None = None):
        super().__init__(app)
        self._per_ip = per_ip or int(os.environ.get("RATE_LIMIT_PER_IP", "60"))
        self._per_user = per_user or int(os.environ.get("RATE_LIMIT_PER_USER", "120"))
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
        """Remove buckets idle for >10 minutes to prevent memory leaks."""
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
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        self._cleanup_stale_buckets()

        client_ip = request.client.host if request.client else "unknown"
        bucket = self._ip_buckets[client_ip]

        if not bucket.consume():
            logger.warning("Rate limit exceeded for IP %s on dashboard", client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60"},
            )

        # Check user-level rate limit if an authenticated user is available
        username = getattr(request.state, "user", None) if hasattr(request, "state") else None
        if username:
            user_bucket = self._user_buckets[f"user:{username}"]
            if not user_bucket.consume():
                logger.warning("Rate limit exceeded for user %s on dashboard", username)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"},
                )

        return await call_next(request)
