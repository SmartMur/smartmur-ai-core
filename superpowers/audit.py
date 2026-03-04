"""Append-only audit log — JSON Lines format."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class AuditLog:
    def __init__(self, log_path: Path | None = None):
        if log_path is None:
            from superpowers.config import get_data_dir

            log_path = get_data_dir() / "audit.log"
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, action: str, detail: str, source: str = "", metadata: dict | None = None) -> None:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "action": action,
            "detail": detail,
            "source": source,
        }
        if metadata is not None:
            entry["metadata"] = metadata
        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def tail(self, n: int = 20) -> list[dict]:
        if not self._path.exists():
            return []
        lines = self._path.read_text().splitlines()
        entries = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def search(self, query: str, limit: int = 50) -> list[dict]:
        if not self._path.exists():
            return []
        query_lower = query.lower()
        results = []
        for line in self._path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            if query_lower in line.lower():
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(results) >= limit:
                    break
        return results

    @property
    def path(self) -> Path:
        return self._path
