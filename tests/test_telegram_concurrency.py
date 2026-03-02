"""Tests for Telegram concurrency gate."""

from __future__ import annotations

import threading
import time

from msg_gateway.telegram.concurrency import ConcurrencyGate


# --- try_acquire / release basics ---


def test_try_acquire_returns_true_when_slots_available():
    gate = ConcurrencyGate(max_per_chat=2, max_global=5, queue_overflow=10)
    result = gate.try_acquire("chat1")
    assert result is True
    gate.release("chat1")


def test_release_frees_slots():
    gate = ConcurrencyGate(max_per_chat=1, max_global=5, queue_overflow=10)

    assert gate.try_acquire("chat1") is True
    gate.release("chat1")

    # After release, we should be able to acquire again
    assert gate.try_acquire("chat1") is True
    gate.release("chat1")


def test_multiple_chats_acquire_independently():
    gate = ConcurrencyGate(max_per_chat=1, max_global=5, queue_overflow=10)

    assert gate.try_acquire("chat1") is True
    assert gate.try_acquire("chat2") is True

    gate.release("chat1")
    gate.release("chat2")


# --- Queue overflow rejection ---


def test_queue_overflow_rejection():
    gate = ConcurrencyGate(max_per_chat=1, max_global=5, queue_overflow=1)

    # First acquire succeeds (consumes the 1 queue slot, then becomes active)
    assert gate.try_acquire("chat1") is True

    # Second attempt will try to add to queue (queued count = 1 already from first call
    # which was decremented, but now the per-chat semaphore is exhausted).
    # The first call incremented chat_queued to 1, then decremented it after acquiring.
    # So queued is back to 0. Second call increments to 1 (within overflow=1, so accepted).
    # We need a third concurrent call when queued=1 to get rejected.

    # To properly test overflow, we need to hold the slot and have queued requests
    # Let's use threads to queue up requests
    results = []
    barrier = threading.Event()

    def try_acquire_thread():
        # This will block on the per-chat semaphore because chat1 slot is held
        r = gate.try_acquire("chat1")
        results.append(r)
        if r:
            barrier.wait(timeout=2)
            gate.release("chat1")

    # Start one thread that will queue (queued goes to 1)
    t1 = threading.Thread(target=try_acquire_thread)
    t1.start()
    time.sleep(0.05)  # Let t1 queue up

    # Now queued should be 1, which equals queue_overflow=1, so next should be rejected
    assert gate.try_acquire("chat1") is False

    # Clean up: release the first slot so t1 can proceed
    gate.release("chat1")
    barrier.set()
    t1.join(timeout=2)


def test_queue_overflow_zero_rejects_immediately():
    """With queue_overflow=0, every call is rejected since queued >= overflow check fires."""
    gate = ConcurrencyGate(max_per_chat=2, max_global=5, queue_overflow=0)
    # queue_overflow=0 means even the first attempt has queued(0) >= overflow(0), rejected
    result = gate.try_acquire("chat1")
    assert result is False


# --- Stats ---


def test_stats_returns_correct_values_initial():
    gate = ConcurrencyGate(max_per_chat=2, max_global=5, queue_overflow=10)
    stats = gate.stats("chat1")
    assert stats.chat_active == 0
    assert stats.chat_queued == 0
    assert stats.global_active == 0
    assert stats.global_max == 5


def test_stats_after_acquire():
    gate = ConcurrencyGate(max_per_chat=2, max_global=5, queue_overflow=10)
    gate.try_acquire("chat1")

    stats = gate.stats("chat1")
    assert stats.chat_active == 1
    assert stats.global_active == 1
    assert stats.global_max == 5


def test_stats_after_acquire_and_release():
    gate = ConcurrencyGate(max_per_chat=2, max_global=5, queue_overflow=10)
    gate.try_acquire("chat1")
    gate.release("chat1")

    stats = gate.stats("chat1")
    assert stats.chat_active == 0
    assert stats.global_active == 0


def test_stats_multiple_acquires():
    gate = ConcurrencyGate(max_per_chat=3, max_global=10, queue_overflow=10)
    gate.try_acquire("chat1")
    gate.try_acquire("chat1")

    stats = gate.stats("chat1")
    assert stats.chat_active == 2
    assert stats.global_active == 2

    gate.release("chat1")
    gate.release("chat1")


# --- Per-chat limit ---


def test_per_chat_limit():
    """With max_per_chat=1, a second acquire from the same chat blocks until release."""
    gate = ConcurrencyGate(max_per_chat=1, max_global=5, queue_overflow=10)

    assert gate.try_acquire("chat1") is True

    acquired = threading.Event()
    done = threading.Event()

    def acquire_in_thread():
        result = gate.try_acquire("chat1")
        acquired.set()
        if result:
            done.wait(timeout=2)
            gate.release("chat1")

    t = threading.Thread(target=acquire_in_thread)
    t.start()

    # The thread should be blocked because per-chat limit is 1
    assert acquired.wait(timeout=0.1) is False, "Thread should be blocked waiting for per-chat slot"

    # Release the first slot
    gate.release("chat1")

    # Now the thread should proceed
    assert acquired.wait(timeout=2) is True, "Thread should have acquired after release"

    done.set()
    t.join(timeout=2)


def test_different_chats_not_affected_by_per_chat_limit():
    """Per-chat limit only affects the same chat, other chats can still acquire."""
    gate = ConcurrencyGate(max_per_chat=1, max_global=5, queue_overflow=10)

    assert gate.try_acquire("chat1") is True
    # Different chat should still succeed even though chat1's slot is taken
    assert gate.try_acquire("chat2") is True

    gate.release("chat1")
    gate.release("chat2")
