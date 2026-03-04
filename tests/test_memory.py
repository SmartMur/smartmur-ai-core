"""Tests for the persistent memory subsystem."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from superpowers.memory.base import MemoryCategory, MemoryEntry, MemoryStoreError
from superpowers.memory.context import ContextBuilder
from superpowers.memory.store import MemoryStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return MemoryStore(db_path=tmp_path / "test_memory.db")


@pytest.fixture
def populated_store(store):
    store.remember("truenas-ssh", "ray@192.168.13.69", category="fact", tags=["infra"])
    store.remember("prefer-ruff", "Use ruff over flake8", category="preference")
    store.remember("db-host", "timescale.local:5432", category="project_context", project="hommie")
    return store


# ---------------------------------------------------------------------------
# MemoryEntry dataclass
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    def test_create_basic(self):
        entry = MemoryEntry(id=1, category=MemoryCategory.fact, key="k", value="v")
        assert entry.id == 1
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.tags == []
        assert entry.project == ""
        assert entry.access_count == 0

    def test_create_with_all_fields(self):
        entry = MemoryEntry(
            id=42,
            category=MemoryCategory.preference,
            key="editor",
            value="neovim",
            tags=["tools"],
            project="dotfiles",
            created_at="2026-01-01T00:00:00",
            accessed_at="2026-03-01T00:00:00",
            access_count=5,
        )
        assert entry.category == MemoryCategory.preference
        assert entry.tags == ["tools"]
        assert entry.access_count == 5

    def test_category_enum_values(self):
        assert MemoryCategory.fact.value == "fact"
        assert MemoryCategory.preference.value == "preference"
        assert MemoryCategory.project_context.value == "project_context"
        assert MemoryCategory.conversation_summary.value == "conversation_summary"


# ---------------------------------------------------------------------------
# MemoryStore — remember
# ---------------------------------------------------------------------------


class TestRemember:
    def test_basic_remember(self, store):
        entry = store.remember("my-key", "my-value")
        assert entry.key == "my-key"
        assert entry.value == "my-value"
        assert entry.category == MemoryCategory.fact
        assert entry.id > 0

    def test_remember_with_category(self, store):
        entry = store.remember("k", "v", category="preference")
        assert entry.category == MemoryCategory.preference

    def test_remember_with_tags(self, store):
        entry = store.remember("k", "v", tags=["infra", "ssh"])
        assert entry.tags == ["infra", "ssh"]

    def test_remember_with_project(self, store):
        entry = store.remember("k", "v", project="hommie")
        assert entry.project == "hommie"

    def test_remember_sets_timestamps(self, store):
        entry = store.remember("k", "v")
        assert entry.created_at != ""
        assert entry.accessed_at != ""

    def test_invalid_category_raises(self, store):
        with pytest.raises(MemoryStoreError, match="Invalid category"):
            store.remember("k", "v", category="bogus")

    def test_upsert_updates_value(self, store):
        store.remember("k", "old-value")
        entry = store.remember("k", "new-value")
        assert entry.value == "new-value"

    def test_upsert_increments_access_count(self, store):
        store.remember("k", "v1")
        entry = store.remember("k", "v2")
        assert entry.access_count >= 1

    def test_same_key_different_categories(self, store):
        e1 = store.remember("k", "v1", category="fact")
        e2 = store.remember("k", "v2", category="preference")
        assert e1.id != e2.id
        assert e1.value == "v1"
        assert e2.value == "v2"

    def test_same_key_different_projects(self, store):
        e1 = store.remember("db-host", "localhost", project="alpha")
        e2 = store.remember("db-host", "remote.host", project="beta")
        assert e1.id != e2.id
        assert e1.value == "localhost"
        assert e2.value == "remote.host"


# ---------------------------------------------------------------------------
# MemoryStore — recall
# ---------------------------------------------------------------------------


class TestRecall:
    def test_recall_existing(self, store):
        store.remember("k", "v")
        entry = store.recall("k")
        assert entry is not None
        assert entry.value == "v"

    def test_recall_missing(self, store):
        assert store.recall("nonexistent") is None

    def test_recall_updates_accessed_at(self, store):
        store.remember("k", "v")
        entry = store.recall("k")
        assert entry.access_count >= 1

    def test_recall_increments_access_count(self, store):
        store.remember("k", "v")
        store.recall("k")
        entry = store.recall("k")
        assert entry.access_count >= 2

    def test_recall_with_category_filter(self, store):
        store.remember("k", "fact-val", category="fact")
        store.remember("k", "pref-val", category="preference")
        entry = store.recall("k", category="preference")
        assert entry.value == "pref-val"

    def test_recall_with_project_filter(self, store):
        store.remember("host", "a.local", project="alpha")
        store.remember("host", "b.local", project="beta")
        entry = store.recall("host", project="beta")
        assert entry.value == "b.local"


# ---------------------------------------------------------------------------
# MemoryStore — search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_by_key(self, populated_store):
        results = populated_store.search("ssh")
        assert len(results) == 1
        assert results[0].key == "truenas-ssh"

    def test_search_by_value(self, populated_store):
        results = populated_store.search("ruff")
        assert len(results) == 1
        assert results[0].key == "prefer-ruff"

    def test_search_no_match(self, populated_store):
        results = populated_store.search("zzz-nonexistent")
        assert results == []

    def test_search_with_category_filter(self, populated_store):
        results = populated_store.search("r", category="preference")
        assert all(e.category == MemoryCategory.preference for e in results)

    def test_search_with_project_filter(self, populated_store):
        results = populated_store.search("host", project="hommie")
        assert len(results) == 1
        assert results[0].project == "hommie"

    def test_search_limit(self, store):
        for i in range(10):
            store.remember(f"item-{i}", f"value-{i}")
        results = store.search("item", limit=3)
        assert len(results) == 3

    def test_search_case_insensitive_like(self, store):
        store.remember("SSH-KEY", "my-pubkey")
        results = store.search("ssh")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# MemoryStore — forget
# ---------------------------------------------------------------------------


class TestForget:
    def test_forget_existing(self, store):
        store.remember("k", "v")
        assert store.forget("k") is True
        assert store.recall("k") is None

    def test_forget_missing(self, store):
        assert store.forget("nonexistent") is False

    def test_forget_with_category(self, store):
        store.remember("k", "v1", category="fact")
        store.remember("k", "v2", category="preference")
        store.forget("k", category="fact")
        assert store.recall("k", category="fact") is None
        assert store.recall("k", category="preference") is not None

    def test_forget_preserves_others(self, store):
        store.remember("keep", "yes")
        store.remember("drop", "no")
        store.forget("drop")
        assert store.recall("keep") is not None


# ---------------------------------------------------------------------------
# MemoryStore — list_memories
# ---------------------------------------------------------------------------


class TestListMemories:
    def test_list_empty(self, store):
        assert store.list_memories() == []

    def test_list_all(self, populated_store):
        entries = populated_store.list_memories()
        assert len(entries) == 3

    def test_list_by_category(self, populated_store):
        entries = populated_store.list_memories(category="fact")
        assert len(entries) == 1
        assert entries[0].key == "truenas-ssh"

    def test_list_by_project(self, populated_store):
        entries = populated_store.list_memories(project="hommie")
        assert len(entries) == 1
        assert entries[0].key == "db-host"

    def test_list_limit(self, store):
        for i in range(10):
            store.remember(f"k{i}", f"v{i}")
        entries = store.list_memories(limit=5)
        assert len(entries) == 5


# ---------------------------------------------------------------------------
# MemoryStore — stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self, store):
        s = store.stats()
        assert s["total"] == 0
        assert s["by_category"] == {}
        assert s["oldest"] is None
        assert s["newest"] is None

    def test_stats_populated(self, populated_store):
        s = populated_store.stats()
        assert s["total"] == 3
        assert s["by_category"]["fact"] == 1
        assert s["by_category"]["preference"] == 1
        assert s["by_category"]["project_context"] == 1
        assert s["oldest"] is not None
        assert s["newest"] is not None


# ---------------------------------------------------------------------------
# MemoryStore — decay
# ---------------------------------------------------------------------------


class TestDecay:
    def test_decay_removes_old_entries(self, store):
        store.remember("old", "stale")
        # Manually backdate the accessed_at
        old_date = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        with store._conn() as conn:
            conn.execute(
                "UPDATE memories SET accessed_at = ? WHERE key = ?",
                (old_date, "old"),
            )
        store.remember("fresh", "new")
        count = store.decay(days=90)
        assert count == 1
        assert store.recall("old") is None
        assert store.recall("fresh") is not None

    def test_decay_returns_zero_when_nothing_stale(self, store):
        store.remember("fresh", "new")
        assert store.decay(days=90) == 0

    def test_decay_custom_days(self, store):
        store.remember("k", "v")
        old_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        with store._conn() as conn:
            conn.execute(
                "UPDATE memories SET accessed_at = ? WHERE key = ?",
                (old_date, "k"),
            )
        assert store.decay(days=5) == 1
        assert store.decay(days=5) == 0


# ---------------------------------------------------------------------------
# ContextBuilder
# ---------------------------------------------------------------------------


class TestContextBuilder:
    def test_empty_store(self, store):
        builder = ContextBuilder(store)
        assert builder.build_context() == ""

    def test_builds_markdown(self, populated_store):
        builder = ContextBuilder(populated_store)
        ctx = builder.build_context()
        assert "## Remembered Context" in ctx
        assert "truenas-ssh" in ctx
        assert "prefer-ruff" in ctx

    def test_project_filter(self, populated_store):
        builder = ContextBuilder(populated_store)
        ctx = builder.build_context(project="hommie")
        assert "db-host" in ctx
        assert "truenas-ssh" not in ctx

    def test_includes_tags(self, populated_store):
        builder = ContextBuilder(populated_store)
        ctx = builder.build_context()
        assert "infra" in ctx

    def test_inject_hook_delegates(self, populated_store):
        builder = ContextBuilder(populated_store)
        assert builder.inject_hook() == builder.build_context()

    def test_inject_hook_with_project(self, populated_store):
        builder = ContextBuilder(populated_store)
        assert builder.inject_hook(project="hommie") == builder.build_context(project="hommie")

    def test_limit_respected(self, store):
        for i in range(20):
            store.remember(f"k{i}", f"v{i}")
        builder = ContextBuilder(store)
        ctx = builder.build_context(limit=5)
        # Should have header + empty line + 5 entries + trailing empty line
        lines = [line for line in ctx.strip().split("\n") if line.startswith("- **")]
        assert len(lines) == 5


# ---------------------------------------------------------------------------
# MemoryStore — DB initialization
# ---------------------------------------------------------------------------


class TestDBInit:
    def test_creates_db_file(self, tmp_path):
        db = tmp_path / "new.db"
        MemoryStore(db_path=db)
        assert db.exists()

    def test_creates_parent_dirs(self, tmp_path):
        db = tmp_path / "sub" / "dir" / "memory.db"
        MemoryStore(db_path=db)
        assert db.exists()

    def test_idempotent_init(self, tmp_path):
        db = tmp_path / "memory.db"
        s1 = MemoryStore(db_path=db)
        s1.remember("k", "v")
        s2 = MemoryStore(db_path=db)
        assert s2.recall("k").value == "v"
