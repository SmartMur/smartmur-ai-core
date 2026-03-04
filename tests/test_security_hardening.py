"""Tests for Phase G — Security Hardening.

Covers:
- G1: Webhook signature validation middleware (fail-closed)
- G2: Rate limiting middleware (token bucket, per-IP)
- G3: Config validation (insecure defaults, missing creds)
- G4: Channel adapter base class interface
"""

from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# G1: Webhook Signature Validation
# ---------------------------------------------------------------------------


class TestWebhookSignatureMiddleware:
    """Test fail-closed webhook signature validation."""

    def _make_app(self):
        """Create a minimal FastAPI app with the webhook middleware."""
        from fastapi import FastAPI

        from msg_gateway.middleware import (
            RateLimitMiddleware,
            WebhookSignatureMiddleware,
        )

        app = FastAPI()
        # Signature middleware goes first (outermost)
        app.add_middleware(WebhookSignatureMiddleware)
        # High rate limit so it doesn't interfere with signature tests
        app.add_middleware(RateLimitMiddleware, per_ip=10000, per_user=10000)

        @app.get("/health")
        def health():
            return {"status": "ok"}

        @app.post("/webhook/telegram")
        def telegram_webhook():
            return {"ok": True}

        @app.post("/webhook/slack")
        def slack_webhook():
            return {"ok": True}

        @app.post("/webhook/discord")
        def discord_webhook():
            return {"ok": True}

        @app.post("/send")
        def send():
            return {"ok": True}

        return app

    def test_health_endpoint_bypasses_validation(self):
        """Health endpoints should never be blocked by webhook validation."""
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_non_webhook_post_passes_through(self):
        """POST to non-webhook paths should not be affected."""
        app = self._make_app()
        client = TestClient(app)
        resp = client.post("/send", json={"test": True})
        assert resp.status_code == 200

    def test_telegram_webhook_rejected_without_secret_env(self):
        """Telegram webhook MUST be rejected when TELEGRAM_WEBHOOK_SECRET is unset."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure the secret is not set
            os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
            app = self._make_app()
            client = TestClient(app)
            resp = client.post(
                "/webhook/telegram",
                json={"update_id": 1},
            )
            assert resp.status_code == 401

    def test_telegram_webhook_rejected_with_wrong_secret(self):
        """Telegram webhook MUST be rejected with an invalid secret header."""
        with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": "correct-secret"}):
            app = self._make_app()
            client = TestClient(app)
            resp = client.post(
                "/webhook/telegram",
                json={"update_id": 1},
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            )
            assert resp.status_code == 401

    def test_telegram_webhook_accepted_with_valid_secret(self):
        """Telegram webhook should pass with correct secret header."""
        with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": "my-secret"}):
            app = self._make_app()
            client = TestClient(app)
            resp = client.post(
                "/webhook/telegram",
                json={"update_id": 1},
                headers={"X-Telegram-Bot-Api-Secret-Token": "my-secret"},
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    def test_telegram_webhook_rejected_with_no_header(self):
        """Telegram webhook MUST be rejected when the secret header is missing."""
        with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": "my-secret"}):
            app = self._make_app()
            client = TestClient(app)
            resp = client.post(
                "/webhook/telegram",
                json={"update_id": 1},
            )
            assert resp.status_code == 401

    def test_slack_webhook_rejected_without_signing_secret(self):
        """Slack webhook MUST be rejected when SLACK_SIGNING_SECRET is unset."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SLACK_SIGNING_SECRET", None)
            app = self._make_app()
            client = TestClient(app)
            resp = client.post(
                "/webhook/slack",
                json={"event": "test"},
            )
            assert resp.status_code == 401

    def test_discord_webhook_rejected_without_public_key(self):
        """Discord webhook MUST be rejected when DISCORD_PUBLIC_KEY is unset."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISCORD_PUBLIC_KEY", None)
            app = self._make_app()
            client = TestClient(app)
            resp = client.post(
                "/webhook/discord",
                json={"type": 1},
            )
            assert resp.status_code == 401

    def test_signature_validation_disabled(self):
        """When WEBHOOK_REQUIRE_SIGNATURE=false, webhooks pass without validation."""
        with patch.dict(os.environ, {"WEBHOOK_REQUIRE_SIGNATURE": "false"}):
            os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
            app = self._make_app()
            client = TestClient(app)
            resp = client.post(
                "/webhook/telegram",
                json={"update_id": 1},
            )
            assert resp.status_code == 200

    def test_signature_validation_default_enabled(self):
        """Signature validation should be enabled by default (fail-closed)."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WEBHOOK_REQUIRE_SIGNATURE", None)
            os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
            app = self._make_app()
            client = TestClient(app)
            resp = client.post(
                "/webhook/telegram",
                json={"update_id": 1},
            )
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# G2: Rate Limiting
# ---------------------------------------------------------------------------


class TestRateLimitMiddleware:
    """Test token-bucket rate limiting."""

    def _make_app(self, per_ip: int = 5, per_user: int = 10):
        """Create a minimal app with rate limiting."""
        from fastapi import FastAPI

        from msg_gateway.middleware import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, per_ip=per_ip, per_user=per_user)

        @app.get("/health")
        def health():
            return {"status": "ok"}

        @app.get("/test")
        def test_endpoint():
            return {"ok": True}

        return app

    def test_under_limit_succeeds(self):
        """Requests under the rate limit should succeed."""
        app = self._make_app(per_ip=10)
        client = TestClient(app)
        for _ in range(5):
            resp = client.get("/test")
            assert resp.status_code == 200

    def test_at_limit_still_succeeds(self):
        """Requests exactly at the bucket capacity should succeed."""
        app = self._make_app(per_ip=5)
        client = TestClient(app)
        for i in range(5):
            resp = client.get("/test")
            assert resp.status_code == 200, f"Request {i + 1} of 5 failed"

    def test_over_limit_returns_429(self):
        """Requests exceeding the rate limit should get 429."""
        app = self._make_app(per_ip=3)
        client = TestClient(app)
        # Exhaust bucket
        for _ in range(3):
            resp = client.get("/test")
            assert resp.status_code == 200
        # Next request should be rate limited
        resp = client.get("/test")
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Too many requests"
        assert "Retry-After" in resp.headers

    def test_health_endpoint_exempt(self):
        """Health endpoint should never be rate limited."""
        app = self._make_app(per_ip=2)
        client = TestClient(app)
        # Exhaust IP bucket on /test
        for _ in range(2):
            client.get("/test")
        # /test should now be limited
        resp = client.get("/test")
        assert resp.status_code == 429
        # But /health should still work
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_rate_limit_configurable_via_env(self):
        """Rate limit should respect RATE_LIMIT_PER_IP env var."""
        with patch.dict(os.environ, {"RATE_LIMIT_PER_IP": "2"}):
            from fastapi import FastAPI

            from msg_gateway.middleware import RateLimitMiddleware

            app = FastAPI()
            app.add_middleware(RateLimitMiddleware)

            @app.get("/test")
            def test_endpoint():
                return {"ok": True}

            client = TestClient(app)
            # Should allow 2 requests
            for _ in range(2):
                resp = client.get("/test")
                assert resp.status_code == 200
            # Third should be limited
            resp = client.get("/test")
            assert resp.status_code == 429

    def test_tokens_refill_over_time(self):
        """Tokens should refill over time (token bucket behavior)."""
        from msg_gateway.middleware import _TokenBucket

        bucket = _TokenBucket(capacity=2, refill_rate=100.0)  # 100/sec for fast test
        # Consume all tokens
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False
        # Wait for refill (100/sec means ~10ms per token)
        time.sleep(0.05)
        # Should have tokens again
        assert bucket.consume() is True


class TestDashboardRateLimitMiddleware:
    """Test dashboard-specific rate limiter."""

    def _make_app(self, per_ip: int = 5):
        from fastapi import FastAPI

        from dashboard.middleware import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, per_ip=per_ip)

        @app.get("/health")
        def health():
            return {"status": "ok"}

        @app.get("/api/test")
        def test_endpoint():
            return {"ok": True}

        return app

    def test_under_limit(self):
        app = self._make_app(per_ip=10)
        client = TestClient(app)
        for _ in range(5):
            resp = client.get("/api/test")
            assert resp.status_code == 200

    def test_over_limit(self):
        app = self._make_app(per_ip=3)
        client = TestClient(app)
        for _ in range(3):
            client.get("/api/test")
        resp = client.get("/api/test")
        assert resp.status_code == 429

    def test_health_exempt(self):
        app = self._make_app(per_ip=1)
        client = TestClient(app)
        client.get("/api/test")  # exhaust
        resp = client.get("/api/test")
        assert resp.status_code == 429
        resp = client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# G3: Config Validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Test security validation on Settings."""

    def _make_settings(self, **overrides):
        from superpowers.config import Settings

        defaults = {
            "dashboard_user": "myuser",
            "dashboard_pass": "a-strong-password-here",
            "environment": "development",
            "force_https": False,
            "webhook_require_signature": True,
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def test_valid_config_no_warnings(self):
        """A properly configured setup should produce no warnings."""
        s = self._make_settings()
        warnings = s.validate_security()
        assert warnings == []

    def test_missing_dashboard_user_warns(self):
        s = self._make_settings(dashboard_user="")
        warnings = s.validate_security()
        assert any("DASHBOARD_USER" in w for w in warnings)

    def test_missing_dashboard_pass_warns(self):
        s = self._make_settings(dashboard_pass="")
        warnings = s.validate_security()
        assert any("DASHBOARD_PASS" in w for w in warnings)

    def test_both_creds_missing_warns(self):
        s = self._make_settings(dashboard_user="", dashboard_pass="")
        warnings = s.validate_security()
        assert any("DASHBOARD_USER and DASHBOARD_PASS" in w for w in warnings)

    def test_insecure_user_warns(self):
        s = self._make_settings(dashboard_user="admin")
        warnings = s.validate_security()
        assert any("insecure default" in w for w in warnings)

    def test_insecure_pass_warns(self):
        s = self._make_settings(dashboard_pass="password")
        warnings = s.validate_security()
        assert any("insecure default" in w for w in warnings)

    def test_production_without_https_warns(self):
        s = self._make_settings(environment="production", force_https=False)
        warnings = s.validate_security()
        assert any("FORCE_HTTPS" in w for w in warnings)

    def test_production_with_https_no_warning(self):
        s = self._make_settings(environment="production", force_https=True)
        warnings = s.validate_security()
        assert not any("FORCE_HTTPS" in w for w in warnings)

    def test_webhook_disabled_warns(self):
        s = self._make_settings(webhook_require_signature=False)
        warnings = s.validate_security()
        assert any("WEBHOOK_REQUIRE_SIGNATURE" in w for w in warnings)

    def test_force_https_default_dev(self):
        """In dev, FORCE_HTTPS defaults to false."""
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "DASHBOARD_USER": "x",
                "DASHBOARD_PASS": "x",
            },
            clear=False,
        ):
            os.environ.pop("FORCE_HTTPS", None)
            from superpowers.config import Settings

            s = Settings.load()
            assert s.force_https is False

    def test_force_https_production_auto(self):
        """In production, FORCE_HTTPS should be auto-enabled."""
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "DASHBOARD_USER": "x",
                "DASHBOARD_PASS": "x",
            },
            clear=False,
        ):
            os.environ.pop("FORCE_HTTPS", None)
            from superpowers.config import Settings

            s = Settings.load()
            assert s.force_https is True

    def test_settings_has_security_fields(self):
        """Settings should expose all new Phase G fields."""
        from superpowers.config import Settings

        s = Settings()
        assert hasattr(s, "force_https")
        assert hasattr(s, "webhook_require_signature")
        assert hasattr(s, "rate_limit_per_ip")
        assert hasattr(s, "rate_limit_per_user")
        assert hasattr(s, "environment")

    def test_insecure_defaults_frozenset(self):
        """The insecure defaults set should contain common bad passwords."""
        from superpowers.config import _INSECURE_DEFAULTS

        assert "admin" in _INSECURE_DEFAULTS
        assert "password" in _INSECURE_DEFAULTS
        assert "changeme" in _INSECURE_DEFAULTS
        assert "12345" in _INSECURE_DEFAULTS


# ---------------------------------------------------------------------------
# G4: Channel Adapter Base Class
# ---------------------------------------------------------------------------


class TestChannelAdapterBase:
    """Test the abstract ChannelAdapter base class interface."""

    def test_cannot_instantiate_directly(self):
        """ChannelAdapter is abstract and cannot be instantiated."""
        from msg_gateway.channels.base import ChannelAdapter

        with pytest.raises(TypeError):
            ChannelAdapter()

    def test_message_dataclass(self):
        """Message should be a proper dataclass with expected fields."""
        from msg_gateway.channels.base import Message

        msg = Message(
            id="123",
            channel="telegram",
            sender_id="456",
            sender_name="testuser",
            text="hello",
        )
        assert msg.id == "123"
        assert msg.channel == "telegram"
        assert msg.sender_id == "456"
        assert msg.sender_name == "testuser"
        assert msg.text == "hello"
        assert msg.raw == {}
        assert msg.chat_id == ""
        assert msg.reply_to_id == ""
        assert msg.attachments == []
        assert msg.timestamp is not None

    def test_concrete_implementation(self):
        """A concrete subclass should implement all abstract methods."""
        from msg_gateway.channels.base import ChannelAdapter, Message

        class TestAdapter(ChannelAdapter):
            @property
            def name(self) -> str:
                return "test"

            async def receive(self, request) -> Message:
                return Message(
                    id="1",
                    channel="test",
                    sender_id="u1",
                    sender_name="Test User",
                    text="hello",
                )

            async def acknowledge(self, message: Message) -> None:
                pass

            async def start_processing_indicator(self, message: Message) -> None:
                pass

            async def send_response(self, message: Message, response: str) -> None:
                pass

        adapter = TestAdapter()
        assert adapter.name == "test"
        assert adapter.supports_streaming is False

    def test_supports_streaming_override(self):
        """Subclass can override supports_streaming."""
        from msg_gateway.channels.base import ChannelAdapter, Message

        class StreamingAdapter(ChannelAdapter):
            @property
            def name(self) -> str:
                return "streaming-test"

            @property
            def supports_streaming(self) -> bool:
                return True

            async def receive(self, request) -> Message:
                return Message(
                    id="1", channel="test", sender_id="u1", sender_name="Test", text="hello"
                )

            async def acknowledge(self, message: Message) -> None:
                pass

            async def start_processing_indicator(self, message: Message) -> None:
                pass

            async def send_response(self, message: Message, response: str) -> None:
                pass

        adapter = StreamingAdapter()
        assert adapter.supports_streaming is True

    def test_receive_is_async(self):
        """receive() should be an async method."""
        from msg_gateway.channels.base import ChannelAdapter, Message

        class SimpleAdapter(ChannelAdapter):
            @property
            def name(self) -> str:
                return "simple"

            async def receive(self, request) -> Message:
                return Message(
                    id="1", channel="simple", sender_id="u1", sender_name="Test", text="hi"
                )

            async def acknowledge(self, message: Message) -> None:
                pass

            async def start_processing_indicator(self, message: Message) -> None:
                pass

            async def send_response(self, message: Message, response: str) -> None:
                pass

        adapter = SimpleAdapter()
        coro = adapter.receive(None)
        # Should be a coroutine
        assert asyncio.iscoroutine(coro)
        # Clean up the coroutine
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(coro)
        finally:
            loop.close()
        assert isinstance(result, Message)
        assert result.text == "hi"

    def test_missing_method_raises_type_error(self):
        """Omitting a required method should prevent instantiation."""
        from msg_gateway.channels.base import ChannelAdapter, Message

        class IncompleteAdapter(ChannelAdapter):
            @property
            def name(self) -> str:
                return "incomplete"

            async def receive(self, request) -> Message:
                return Message(
                    id="1", channel="test", sender_id="u1", sender_name="Test", text="hi"
                )

            # Missing acknowledge, start_processing_indicator, send_response

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_adapter_has_required_abstract_methods(self):
        """ChannelAdapter should require name, receive, acknowledge,
        start_processing_indicator, and send_response."""
        import inspect

        from msg_gateway.channels.base import ChannelAdapter

        # Check abstract methods
        abstract_methods = set()
        for name, method in inspect.getmembers(ChannelAdapter):
            if getattr(method, "__isabstractmethod__", False):
                abstract_methods.add(name)

        assert "name" in abstract_methods
        assert "receive" in abstract_methods
        assert "acknowledge" in abstract_methods
        assert "start_processing_indicator" in abstract_methods
        assert "send_response" in abstract_methods

    def test_message_with_raw_data(self):
        """Message should preserve raw webhook data."""
        from msg_gateway.channels.base import Message

        raw = {"update_id": 123, "message": {"text": "hi"}}
        msg = Message(
            id="1",
            channel="telegram",
            sender_id="u1",
            sender_name="Test",
            text="hi",
            raw=raw,
            chat_id="c1",
            reply_to_id="r1",
            attachments=[{"type": "photo", "file_id": "abc"}],
        )
        assert msg.raw == raw
        assert msg.chat_id == "c1"
        assert msg.reply_to_id == "r1"
        assert len(msg.attachments) == 1


# ---------------------------------------------------------------------------
# G5: Token Bucket Unit Tests
# ---------------------------------------------------------------------------


class TestTokenBucket:
    """Direct unit tests for the token bucket implementation."""

    def test_initial_capacity(self):
        from msg_gateway.middleware import _TokenBucket

        bucket = _TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.tokens == 5.0

    def test_consume_decrements(self):
        from msg_gateway.middleware import _TokenBucket

        bucket = _TokenBucket(capacity=3, refill_rate=1.0)
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False

    def test_refill(self):
        from msg_gateway.middleware import _TokenBucket

        bucket = _TokenBucket(capacity=2, refill_rate=200.0)  # 200/s for fast test
        bucket.consume()
        bucket.consume()
        assert bucket.consume() is False
        time.sleep(0.02)  # 20ms * 200/s = 4 tokens refilled
        assert bucket.consume() is True

    def test_capacity_cap(self):
        """Tokens should never exceed capacity."""
        from msg_gateway.middleware import _TokenBucket

        bucket = _TokenBucket(capacity=3, refill_rate=1000.0)
        time.sleep(0.1)  # Would refill 100 tokens, but cap at 3
        # Consume: should get exactly 3 then fail
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False


# ---------------------------------------------------------------------------
# Combined middleware integration test
# ---------------------------------------------------------------------------


class TestMiddlewareIntegration:
    """Test multiple middleware layers working together."""

    def _make_app(self):
        from fastapi import FastAPI

        from msg_gateway.middleware import (
            RateLimitMiddleware,
            WebhookSignatureMiddleware,
        )

        app = FastAPI()
        app.add_middleware(WebhookSignatureMiddleware)
        app.add_middleware(RateLimitMiddleware, per_ip=100, per_user=200)

        @app.get("/health")
        def health():
            return {"status": "ok"}

        @app.post("/webhook/telegram")
        def telegram():
            return {"ok": True}

        @app.post("/send")
        def send():
            return {"ok": True}

        return app

    def test_rate_limit_plus_signature_both_active(self):
        """Both middleware layers should be active simultaneously."""
        with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": "s3cret"}):
            app = self._make_app()
            client = TestClient(app)

            # Webhook without signature: 401
            resp = client.post("/webhook/telegram", json={})
            assert resp.status_code == 401

            # Webhook with valid signature: 200
            resp = client.post(
                "/webhook/telegram",
                json={},
                headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
            )
            assert resp.status_code == 200

            # Non-webhook endpoint: 200
            resp = client.post("/send", json={})
            assert resp.status_code == 200

    def test_rate_limit_applied_to_webhooks(self):
        """Rate limiting should apply even to valid webhooks."""
        with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": "s3cret"}):
            from fastapi import FastAPI

            from msg_gateway.middleware import (
                RateLimitMiddleware,
                WebhookSignatureMiddleware,
            )

            app = FastAPI()
            app.add_middleware(WebhookSignatureMiddleware)
            app.add_middleware(RateLimitMiddleware, per_ip=3, per_user=100)

            @app.post("/webhook/telegram")
            def telegram():
                return {"ok": True}

            client = TestClient(app)
            headers = {"X-Telegram-Bot-Api-Secret-Token": "s3cret"}

            for _ in range(3):
                resp = client.post("/webhook/telegram", json={}, headers=headers)
                assert resp.status_code == 200

            resp = client.post("/webhook/telegram", json={}, headers=headers)
            assert resp.status_code == 429
