"""SQLite-backed persistent memory store."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from superpowers.memory.base import MemoryCategory, MemoryEntry, MemoryStoreError


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
    tags = json.loads(row["tags"]) if row["tags"] else []
    return MemoryEntry(
        id=row["id"],
        category=MemoryCategory(row["category"]),
        key=row["key"],
        value=row["value"],
        tags=tags,
        project=row["project"] or "",
        created_at=row["created_at"] or "",
        accessed_at=row["accessed_at"] or "",
        access_count=row["access_count"] or 0,
    )


class MemoryStore:
    """SQLite-backed key/value memory store with categories and search."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from superpowers.config import get_data_dir

            db_path = get_data_dir() / "memory.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    project TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    UNIQUE(category, key, project)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_category
                ON memories(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_project
                ON memories(project)
            """)

    def remember(
        self,
        key: str,
        value: str,
        category: str = "fact",
        tags: list[str] | None = None,
        project: str = "",
    ) -> MemoryEntry:
        if category not in {c.value for c in MemoryCategory}:
            raise MemoryStoreError(f"Invalid category: {category}")
        now = _now()
        tags_json = json.dumps(tags or [])
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO memories (category, key, value, tags, project, created_at, accessed_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(category, key, project) DO UPDATE SET
                    value = excluded.value,
                    tags = excluded.tags,
                    accessed_at = excluded.accessed_at,
                    access_count = access_count + 1
                """,
                (category, key, value, tags_json, project, now, now),
            )
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM memories WHERE category = ? AND key = ? AND project = ?",
                    (category, key, project),
                ).fetchone()
            return _row_to_entry(row)

    def recall(
        self,
        key: str,
        category: str | None = None,
        project: str | None = None,
    ) -> MemoryEntry | None:
        clauses = ["key = ?"]
        params: list[str] = [key]
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if project is not None:
            clauses.append("project = ?")
            params.append(project)
        where = " AND ".join(clauses)
        with self._conn() as conn:
            row = conn.execute(f"SELECT * FROM memories WHERE {where}", params).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE memories SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                (_now(), row["id"]),
            )
            updated = conn.execute("SELECT * FROM memories WHERE id = ?", (row["id"],)).fetchone()
            return _row_to_entry(updated)

    def search(
        self,
        query: str,
        category: str | None = None,
        project: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        clauses = ["(key LIKE ? OR value LIKE ?)"]
        pattern = f"%{query}%"
        params: list[str | int] = [pattern, pattern]
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if project is not None:
            clauses.append("project = ?")
            params.append(project)
        where = " AND ".join(clauses)
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM memories WHERE {where} ORDER BY accessed_at DESC LIMIT ?",
                params,
            ).fetchall()
            return [_row_to_entry(r) for r in rows]

    def forget(self, key: str, category: str | None = None) -> bool:
        clauses = ["key = ?"]
        params: list[str] = [key]
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        where = " AND ".join(clauses)
        with self._conn() as conn:
            cur = conn.execute(f"DELETE FROM memories WHERE {where}", params)
            return cur.rowcount > 0

    def list_memories(
        self,
        category: str | None = None,
        project: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        clauses: list[str] = []
        params: list[str | int] = []
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if project is not None:
            clauses.append("project = ?")
            params.append(project)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM memories {where} ORDER BY accessed_at DESC LIMIT ?",
                params,
            ).fetchall()
            return [_row_to_entry(r) for r in rows]

    def decay(self, days: int = 90) -> int:
        cutoff = datetime.now(UTC)
        from datetime import timedelta

        cutoff = (cutoff - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM memories WHERE accessed_at < ?", (cutoff,))
            return cur.rowcount

    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            cats = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM memories GROUP BY category"
            ).fetchall()
            oldest = conn.execute("SELECT MIN(created_at) FROM memories").fetchone()[0]
            newest = conn.execute("SELECT MAX(created_at) FROM memories").fetchone()[0]
            return {
                "total": total,
                "by_category": {r["category"]: r["cnt"] for r in cats},
                "oldest": oldest,
                "newest": newest,
            }
