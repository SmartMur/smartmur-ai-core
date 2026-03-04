"""Tests for CLI memory subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_memory import memory_group
from superpowers.memory.base import MemoryCategory, MemoryEntry, MemoryStoreError


def _make_entry(**kwargs):
    defaults = dict(
        id=1,
        category=MemoryCategory.fact,
        key="test-key",
        value="test-value",
        tags=["t1"],
        project="myproj",
        created_at="2026-01-01",
        accessed_at="2026-01-02",
        access_count=3,
    )
    defaults.update(kwargs)
    return MemoryEntry(**defaults)


# --- memory remember ---


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_remember_happy(mock_cls):
    store = MagicMock()
    store.remember.return_value = _make_entry()
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["remember", "test-key", "test-value"])
    assert result.exit_code == 0
    assert "Remembered" in result.output
    assert "test-key" in result.output


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_remember_with_options(mock_cls):
    store = MagicMock()
    store.remember.return_value = _make_entry(category=MemoryCategory.preference)
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(
        memory_group,
        ["remember", "mykey", "myval", "-c", "preference", "-t", "a,b", "-p", "proj"],
    )
    assert result.exit_code == 0
    store.remember.assert_called_once_with(
        "mykey", "myval", category="preference", tags=["a", "b"], project="proj"
    )


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_remember_error(mock_cls):
    store = MagicMock()
    store.remember.side_effect = MemoryStoreError("db locked")
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["remember", "k", "v"])
    assert result.exit_code != 0
    assert "db locked" in result.output


# --- memory recall ---


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_recall_found(mock_cls):
    store = MagicMock()
    store.recall.return_value = _make_entry()
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["recall", "test-key"])
    assert result.exit_code == 0
    assert "test-key" in result.output
    assert "test-value" in result.output
    assert "myproj" in result.output


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_recall_not_found(mock_cls):
    store = MagicMock()
    store.recall.return_value = None
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["recall", "missing"])
    assert result.exit_code != 0
    assert "Not found" in result.output


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_recall_with_category(mock_cls):
    store = MagicMock()
    store.recall.return_value = _make_entry()
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["recall", "test-key", "-c", "fact"])
    assert result.exit_code == 0
    store.recall.assert_called_once_with("test-key", category="fact")


# --- memory search ---


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_search_results(mock_cls):
    store = MagicMock()
    store.search.return_value = [_make_entry(), _make_entry(id=2, key="other")]
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["search", "test"])
    assert result.exit_code == 0
    assert "test-key" in result.output


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_search_no_results(mock_cls):
    store = MagicMock()
    store.search.return_value = []
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["search", "nothing"])
    assert result.exit_code == 0
    assert "No matches" in result.output


# --- memory forget ---


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_forget_found(mock_cls):
    store = MagicMock()
    store.forget.return_value = True
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["forget", "test-key"])
    assert result.exit_code == 0
    assert "Forgot" in result.output


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_forget_not_found(mock_cls):
    store = MagicMock()
    store.forget.return_value = False
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["forget", "missing"])
    assert result.exit_code != 0
    assert "Not found" in result.output


# --- memory list ---


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_list_with_entries(mock_cls):
    store = MagicMock()
    store.list_memories.return_value = [_make_entry()]
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["list"])
    assert result.exit_code == 0
    assert "test-key" in result.output


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_list_empty(mock_cls):
    store = MagicMock()
    store.list_memories.return_value = []
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["list"])
    assert result.exit_code == 0
    assert "No memories stored" in result.output


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_list_with_filters(mock_cls):
    store = MagicMock()
    store.list_memories.return_value = []
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["list", "-c", "preference", "-p", "proj", "-n", "10"])
    assert result.exit_code == 0
    store.list_memories.assert_called_once_with(category="preference", project="proj", limit=10)


# --- memory stats ---


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_stats(mock_cls):
    store = MagicMock()
    store.stats.return_value = {
        "total": 42,
        "by_category": {"fact": 30, "preference": 12},
        "oldest": "2025-01-01",
        "newest": "2026-03-01",
    }
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["stats"])
    assert result.exit_code == 0
    assert "42" in result.output
    assert "fact" in result.output


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_stats_empty(mock_cls):
    store = MagicMock()
    store.stats.return_value = {
        "total": 0,
        "by_category": {},
        "oldest": None,
        "newest": None,
    }
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["stats"])
    assert result.exit_code == 0
    assert "0" in result.output


# --- memory decay ---


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_decay_default(mock_cls):
    store = MagicMock()
    store.decay.return_value = 5
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["decay"])
    assert result.exit_code == 0
    assert "5" in result.output
    assert "90" in result.output
    store.decay.assert_called_once_with(days=90)


@patch("superpowers.cli_memory.MemoryStore")
def test_memory_decay_custom_days(mock_cls):
    store = MagicMock()
    store.decay.return_value = 0
    mock_cls.return_value = store
    runner = CliRunner()
    result = runner.invoke(memory_group, ["decay", "-d", "30"])
    assert result.exit_code == 0
    store.decay.assert_called_once_with(days=30)


# --- memory context ---


@patch("superpowers.cli_memory.ContextBuilder")
@patch("superpowers.cli_memory.MemoryStore")
def test_memory_context_with_data(mock_store_cls, mock_ctx_cls):
    builder = MagicMock()
    builder.build_context.return_value = "Injected context here."
    mock_ctx_cls.return_value = builder
    runner = CliRunner()
    result = runner.invoke(memory_group, ["context"])
    assert result.exit_code == 0
    assert "Injected context here" in result.output


@patch("superpowers.cli_memory.ContextBuilder")
@patch("superpowers.cli_memory.MemoryStore")
def test_memory_context_empty(mock_store_cls, mock_ctx_cls):
    builder = MagicMock()
    builder.build_context.return_value = ""
    mock_ctx_cls.return_value = builder
    runner = CliRunner()
    result = runner.invoke(memory_group, ["context"])
    assert result.exit_code == 0
    assert "No context to inject" in result.output
