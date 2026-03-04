"""SQLite-backed stores for conversations, notifications, and jobs."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from superpowers.config import get_data_dir


def _db_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "dashboard.db"


class ConversationsDB:
    """Conversation history stored in SQLite."""

    def __init__(self, db_path: Path | None = None):
        self._path = db_path or _db_path()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

    def create(self, title: str = "New conversation") -> dict:
        cid = str(uuid.uuid4())[:8]
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, messages, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (cid, title, "[]", now, now),
            )
        return {"id": cid, "title": title, "messages": [], "created_at": now, "updated_at": now}

    def list(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, cid: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, title, messages, created_at, updated_at FROM conversations WHERE id = ?",
                (cid,),
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["messages"] = json.loads(d["messages"])
        return d

    def add_message(self, cid: str, role: str, content: str) -> dict | None:
        conv = self.get(cid)
        if conv is None:
            return None
        msgs = conv["messages"]
        msgs.append({"role": role, "content": content, "ts": time.time()})
        now = time.time()
        # Auto-title from first user message
        title = conv["title"]
        if title == "New conversation" and role == "user":
            title = content[:60] + ("..." if len(content) > 60 else "")
        with self._conn() as conn:
            conn.execute(
                "UPDATE conversations SET messages = ?, title = ?, updated_at = ? WHERE id = ?",
                (json.dumps(msgs), title, now, cid),
            )
        conv["messages"] = msgs
        conv["title"] = title
        conv["updated_at"] = now
        return conv

    def delete(self, cid: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
        return cur.rowcount > 0


class NotificationsDB:
    """Notification center backed by SQLite."""

    def __init__(self, db_path: Path | None = None):
        self._path = db_path or _db_path()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    level TEXT NOT NULL DEFAULT 'info',
                    read INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)

    def add(self, source: str, title: str, detail: str = "", level: str = "info") -> dict:
        nid = str(uuid.uuid4())[:8]
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO notifications (id, source, title, detail, level, read, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
                (nid, source, title, detail, level, now),
            )
        return {
            "id": nid,
            "source": source,
            "title": title,
            "detail": detail,
            "level": level,
            "read": False,
            "created_at": now,
        }

    def list(self, limit: int = 50, unread_only: bool = False) -> list[dict]:
        with self._conn() as conn:
            if unread_only:
                rows = conn.execute(
                    "SELECT * FROM notifications WHERE read = 0 ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) | {"read": bool(dict(r)["read"])} for r in rows]

    def unread_count(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM notifications WHERE read = 0"
            ).fetchone()
        return row["cnt"] if row else 0

    def mark_read(self, nid: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (nid,))
        return cur.rowcount > 0

    def mark_all_read(self) -> int:
        with self._conn() as conn:
            cur = conn.execute("UPDATE notifications SET read = 1 WHERE read = 0")
        return cur.rowcount

    def delete(self, nid: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM notifications WHERE id = ?", (nid,))
        return cur.rowcount > 0


class JobsDB:
    """Job monitor backed by SQLite."""

    def __init__(self, db_path: Path | None = None):
        self._path = db_path or _db_path()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    job_type TEXT NOT NULL DEFAULT 'shell',
                    status TEXT NOT NULL DEFAULT 'queued',
                    started_at REAL,
                    completed_at REAL,
                    duration REAL,
                    output TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL
                )
            """)

    def create(self, name: str, job_type: str = "shell") -> dict:
        jid = str(uuid.uuid4())[:8]
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO jobs (id, name, job_type, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
                (jid, name, job_type, now),
            )
        return {
            "id": jid,
            "name": name,
            "job_type": job_type,
            "status": "queued",
            "started_at": None,
            "completed_at": None,
            "duration": None,
            "output": "",
            "error": "",
            "created_at": now,
        }

    def start(self, jid: str) -> bool:
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
                (now, jid),
            )
        return cur.rowcount > 0

    def complete(self, jid: str, output: str = "", error: str = "") -> bool:
        now = time.time()
        with self._conn() as conn:
            row = conn.execute("SELECT started_at FROM jobs WHERE id = ?", (jid,)).fetchone()
            duration = now - row["started_at"] if row and row["started_at"] else 0
            stat = "failed" if error else "completed"
            cur = conn.execute(
                "UPDATE jobs SET status = ?, completed_at = ?, duration = ?, output = ?, error = ? WHERE id = ?",
                (stat, now, duration, output[:4000], error[:2000], jid),
            )
        return cur.rowcount > 0

    def get(self, jid: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (jid,)).fetchone()
        return dict(row) if row else None

    def list(self, limit: int = 50, status: str | None = None) -> list[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, jid: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ?", (jid,))
        return cur.rowcount > 0


class RsyncDB:
    """Rsync job persistence backed by SQLite."""

    def __init__(self, db_path: Path | None = None):
        self._path = db_path or _db_path()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rsync_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    source_host TEXT NOT NULL DEFAULT '',
                    source_path TEXT NOT NULL,
                    source_user TEXT NOT NULL DEFAULT 'root',
                    dest_host TEXT NOT NULL DEFAULT '',
                    dest_path TEXT NOT NULL,
                    dest_user TEXT NOT NULL DEFAULT 'root',
                    options TEXT NOT NULL DEFAULT '{}',
                    ssh_key TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress TEXT NOT NULL DEFAULT '{}',
                    stats TEXT NOT NULL DEFAULT '{}',
                    output TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    pid INTEGER,
                    started_at REAL,
                    completed_at REAL,
                    created_at REAL NOT NULL
                )
            """)

    def create(
        self,
        source_path: str,
        dest_path: str,
        name: str = "",
        source_host: str = "",
        source_user: str = "root",
        dest_host: str = "",
        dest_user: str = "root",
        options: str = "{}",
        ssh_key: str = "",
    ) -> dict:
        jid = str(uuid.uuid4())[:8]
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO rsync_jobs
                   (id, name, source_host, source_path, source_user,
                    dest_host, dest_path, dest_user, options, ssh_key, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (jid, name, source_host, source_path, source_user,
                 dest_host, dest_path, dest_user, options, ssh_key, now),
            )
        return self.get(jid)  # type: ignore[return-value]

    def update_status(self, jid: str, status: str, **fields) -> bool:
        sets = ["status = ?"]
        vals: list = [status]
        for k, v in fields.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(jid)
        with self._conn() as conn:
            cur = conn.execute(
                f"UPDATE rsync_jobs SET {', '.join(sets)} WHERE id = ?", vals
            )
        return cur.rowcount > 0

    def update_progress(self, jid: str, progress_json: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE rsync_jobs SET progress = ? WHERE id = ?",
                (progress_json, jid),
            )
        return cur.rowcount > 0

    def complete(self, jid: str, status: str, stats_json: str, output: str, error: str) -> bool:
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                """UPDATE rsync_jobs
                   SET status = ?, stats = ?, output = ?, error = ?, completed_at = ?
                   WHERE id = ?""",
                (status, stats_json, output[:50000], error[:10000], now, jid),
            )
        return cur.rowcount > 0

    def get(self, jid: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM rsync_jobs WHERE id = ?", (jid,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        for key in ("options", "progress", "stats"):
            try:
                d[key] = json.loads(d[key]) if d[key] else {}
            except (json.JSONDecodeError, TypeError):
                d[key] = {}
        return d

    def list(self, limit: int = 50, status: str | None = None) -> list[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM rsync_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM rsync_jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            for key in ("options", "progress", "stats"):
                try:
                    d[key] = json.loads(d[key]) if d[key] else {}
                except (json.JSONDecodeError, TypeError):
                    d[key] = {}
            results.append(d)
        return results

    def delete(self, jid: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM rsync_jobs WHERE id = ?", (jid,))
        return cur.rowcount > 0
