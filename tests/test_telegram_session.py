"""Tests for Telegram session manager (in-memory mode, no Redis)."""

from __future__ import annotations

import time

from msg_gateway.telegram.session import HistoryEntry, SessionManager

# --- HistoryEntry ---


def test_history_entry_to_dict():
    entry = HistoryEntry(role="user", content="hello", timestamp=1000.0)
    d = entry.to_dict()
    assert d == {"role": "user", "content": "hello", "timestamp": 1000.0}


def test_history_entry_from_dict():
    d = {"role": "assistant", "content": "hi there", "timestamp": 2000.0}
    entry = HistoryEntry.from_dict(d)
    assert entry.role == "assistant"
    assert entry.content == "hi there"
    assert entry.timestamp == 2000.0


def test_history_entry_from_dict_defaults():
    entry = HistoryEntry.from_dict({})
    assert entry.role == "user"
    assert entry.content == ""
    # timestamp should be filled with current time
    assert entry.timestamp > 0


def test_history_entry_roundtrip():
    original = HistoryEntry(role="user", content="test roundtrip", timestamp=12345.6)
    reconstructed = HistoryEntry.from_dict(original.to_dict())
    assert reconstructed.role == original.role
    assert reconstructed.content == original.content
    assert reconstructed.timestamp == original.timestamp


# --- SessionManager: add and get ---


def test_add_and_get_messages():
    sm = SessionManager()
    sm.add("chat1", "user", "hello")
    sm.add("chat1", "assistant", "hi there")

    history = sm.get("chat1")
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "hello"
    assert history[1].role == "assistant"
    assert history[1].content == "hi there"


def test_get_empty_returns_empty_list():
    sm = SessionManager()
    history = sm.get("nonexistent")
    assert history == []


def test_separate_chats_have_separate_history():
    sm = SessionManager()
    sm.add("chat1", "user", "msg for chat1")
    sm.add("chat2", "user", "msg for chat2")

    h1 = sm.get("chat1")
    h2 = sm.get("chat2")
    assert len(h1) == 1
    assert len(h2) == 1
    assert h1[0].content == "msg for chat1"
    assert h2[0].content == "msg for chat2"


# --- Sliding window ---


def test_sliding_window_trims_to_max_history():
    sm = SessionManager(max_history=3)
    for i in range(5):
        sm.add("chat1", "user", f"msg{i}")

    history = sm.get("chat1")
    assert len(history) == 3
    # Only the last 3 messages should remain
    assert history[0].content == "msg2"
    assert history[1].content == "msg3"
    assert history[2].content == "msg4"


def test_sliding_window_exact_boundary():
    sm = SessionManager(max_history=2)
    sm.add("chat1", "user", "first")
    sm.add("chat1", "user", "second")

    history = sm.get("chat1")
    assert len(history) == 2

    # Adding one more should trim to 2
    sm.add("chat1", "user", "third")
    history = sm.get("chat1")
    assert len(history) == 2
    assert history[0].content == "second"
    assert history[1].content == "third"


# --- TTL expiry ---


def test_ttl_expiry():
    sm = SessionManager(ttl=0.1)  # 100ms TTL
    sm.add("chat1", "user", "ephemeral message")

    # Message should be available immediately
    history = sm.get("chat1")
    assert len(history) == 1

    # Wait for TTL to expire
    time.sleep(0.2)

    history = sm.get("chat1")
    assert len(history) == 0


def test_ttl_only_expires_old_entries():
    sm = SessionManager(ttl=0.3)
    sm.add("chat1", "user", "old message")

    time.sleep(0.2)
    sm.add("chat1", "user", "new message")

    time.sleep(0.15)
    # old message (~0.35s old) should be expired, new message (~0.15s old) should remain
    history = sm.get("chat1")
    assert len(history) == 1
    assert history[0].content == "new message"


# --- clear ---


def test_clear_removes_history():
    sm = SessionManager()
    sm.add("chat1", "user", "hello")
    sm.add("chat1", "assistant", "hi")

    sm.clear("chat1")
    history = sm.get("chat1")
    assert history == []


def test_clear_nonexistent_does_not_error():
    sm = SessionManager()
    sm.clear("nonexistent")  # Should not raise


def test_clear_only_affects_target_chat():
    sm = SessionManager()
    sm.add("chat1", "user", "msg1")
    sm.add("chat2", "user", "msg2")

    sm.clear("chat1")
    assert sm.get("chat1") == []
    assert len(sm.get("chat2")) == 1


# --- format_context ---


def test_format_context_returns_formatted_conversation():
    sm = SessionManager()
    sm.add("chat1", "user", "What is Python?")
    sm.add("chat1", "assistant", "Python is a programming language.")
    sm.add("chat1", "user", "Tell me more.")

    ctx = sm.format_context("chat1")
    lines = ctx.split("\n")
    assert lines[0] == "Human: What is Python?"
    assert lines[1] == "Assistant: Python is a programming language."
    assert lines[2] == "Human: Tell me more."


def test_format_context_empty_returns_empty_string():
    sm = SessionManager()
    ctx = sm.format_context("nonexistent")
    assert ctx == ""


def test_format_context_single_message():
    sm = SessionManager()
    sm.add("chat1", "assistant", "Hello!")
    ctx = sm.format_context("chat1")
    assert ctx == "Assistant: Hello!"
