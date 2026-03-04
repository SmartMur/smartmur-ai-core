"""Security-focused tests for rsync DB update constraints."""

from __future__ import annotations

import pytest

from dashboard.db import RsyncDB


def test_update_status_allows_known_fields(tmp_path):
    db = RsyncDB(db_path=tmp_path / "dashboard.db")
    job = db.create(source_path="/src", dest_path="/dst")

    ok = db.update_status(job["id"], "running", pid=1234, started_at=123.45)
    assert ok is True


def test_update_status_rejects_unknown_fields(tmp_path):
    db = RsyncDB(db_path=tmp_path / "dashboard.db")
    job = db.create(source_path="/src", dest_path="/dst")

    with pytest.raises(ValueError, match="Invalid rsync update field"):
        db.update_status(job["id"], "running", injected_column="bad")
