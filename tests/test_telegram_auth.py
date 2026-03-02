"""Tests for the AuthGate allowlist (msg_gateway.telegram.auth)."""

from __future__ import annotations

import pytest

from msg_gateway.telegram.auth import AuthGate


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------


class TestIsConfigured:
    def test_not_configured_when_empty(self):
        gate = AuthGate(allowed_ids=[])
        assert gate.is_configured is False

    def test_configured_with_explicit_ids(self):
        gate = AuthGate(allowed_ids=["123", "456"])
        assert gate.is_configured is True

    def test_not_configured_with_empty_env(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_CHAT_IDS", "")
        gate = AuthGate()
        assert gate.is_configured is False


# ---------------------------------------------------------------------------
# is_allowed — with configured allowlist
# ---------------------------------------------------------------------------


class TestIsAllowed:
    def test_allowed_for_allowlisted_id(self):
        gate = AuthGate(allowed_ids=["100", "200", "300"])
        assert gate.is_allowed("100") is True
        assert gate.is_allowed("200") is True
        assert gate.is_allowed("300") is True

    def test_rejected_for_unknown_id(self):
        gate = AuthGate(allowed_ids=["100", "200"])
        assert gate.is_allowed("999") is False

    def test_rejected_for_similar_but_wrong_id(self):
        gate = AuthGate(allowed_ids=["100"])
        assert gate.is_allowed("1000") is False
        assert gate.is_allowed("10") is False

    def test_string_vs_int_matters(self):
        """Chat IDs are stored as strings; numeric mismatch should fail."""
        gate = AuthGate(allowed_ids=["100"])
        assert gate.is_allowed("100") is True
        # Different string representation
        assert gate.is_allowed(" 100") is False


# ---------------------------------------------------------------------------
# is_allowed — unconfigured (secure by default)
# ---------------------------------------------------------------------------


class TestIsAllowedUnconfigured:
    def test_rejects_all_when_not_configured(self):
        gate = AuthGate(allowed_ids=[])
        assert gate.is_allowed("100") is False
        assert gate.is_allowed("200") is False

    def test_rejects_empty_string(self):
        gate = AuthGate(allowed_ids=[])
        assert gate.is_allowed("") is False


# ---------------------------------------------------------------------------
# add / remove
# ---------------------------------------------------------------------------


class TestAddRemove:
    def test_add_makes_id_allowed(self):
        gate = AuthGate(allowed_ids=[])
        assert gate.is_configured is False

        gate.add("42")
        assert gate.is_configured is True
        assert gate.is_allowed("42") is True

    def test_remove_makes_id_rejected(self):
        gate = AuthGate(allowed_ids=["42", "99"])
        assert gate.is_allowed("42") is True

        gate.remove("42")
        assert gate.is_allowed("42") is False
        # Other IDs unaffected
        assert gate.is_allowed("99") is True

    def test_remove_nonexistent_is_safe(self):
        gate = AuthGate(allowed_ids=["42"])
        # Should not raise
        gate.remove("999")
        assert gate.is_allowed("42") is True

    def test_add_duplicate_is_idempotent(self):
        gate = AuthGate(allowed_ids=["42"])
        gate.add("42")
        assert gate.is_allowed("42") is True


# ---------------------------------------------------------------------------
# Loading from environment variable
# ---------------------------------------------------------------------------


class TestEnvVarLoading:
    def test_loads_from_env_comma_separated(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_CHAT_IDS", "100,200,300")
        gate = AuthGate()
        assert gate.is_configured is True
        assert gate.is_allowed("100") is True
        assert gate.is_allowed("200") is True
        assert gate.is_allowed("300") is True
        assert gate.is_allowed("999") is False

    def test_handles_whitespace_in_env(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_CHAT_IDS", " 100 , 200 , 300 ")
        gate = AuthGate()
        assert gate.is_allowed("100") is True
        assert gate.is_allowed("200") is True
        assert gate.is_allowed("300") is True

    def test_handles_trailing_comma(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_CHAT_IDS", "100,200,")
        gate = AuthGate()
        assert gate.is_allowed("100") is True
        assert gate.is_allowed("200") is True
        assert gate.is_allowed("") is False

    def test_empty_env_not_configured(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_CHAT_IDS", "")
        gate = AuthGate()
        assert gate.is_configured is False

    def test_unset_env_not_configured(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_CHAT_IDS", raising=False)
        gate = AuthGate()
        assert gate.is_configured is False

    def test_single_id_in_env(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_CHAT_IDS", "42")
        gate = AuthGate()
        assert gate.is_configured is True
        assert gate.is_allowed("42") is True

    def test_explicit_ids_override_env(self, monkeypatch):
        """When allowed_ids is passed explicitly, env var is ignored."""
        monkeypatch.setenv("ALLOWED_CHAT_IDS", "100,200")
        gate = AuthGate(allowed_ids=["999"])
        assert gate.is_allowed("100") is False
        assert gate.is_allowed("999") is True
