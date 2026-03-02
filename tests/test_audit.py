from __future__ import annotations

import json

from superpowers.audit import AuditLog


class TestAuditLog:
    def test_log_creates_file(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("test.action", "some detail", "unit-test")
        assert log_file.exists()

    def test_log_jsonl_format(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("skill.run", "heartbeat", "cron")

        line = log_file.read_text().strip()
        entry = json.loads(line)
        assert entry["action"] == "skill.run"
        assert entry["detail"] == "heartbeat"
        assert entry["source"] == "cron"
        assert "ts" in entry

    def test_log_multiple_entries(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("a", "first")
        audit.log("b", "second")
        audit.log("c", "third")

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_tail_returns_last_n(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        for i in range(10):
            audit.log("action", f"entry-{i}")

        result = audit.tail(3)
        assert len(result) == 3
        assert result[0]["detail"] == "entry-7"
        assert result[2]["detail"] == "entry-9"

    def test_tail_empty_log(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        assert audit.tail() == []

    def test_tail_nonexistent_file(self, tmp_path):
        log_file = tmp_path / "nope.log"
        audit = AuditLog(log_path=log_file)
        assert audit.tail() == []

    def test_search_finds_matches(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("skill.run", "heartbeat", "cron")
        audit.log("cron.execute", "backup", "scheduler")
        audit.log("skill.run", "network-scan", "manual")

        results = audit.search("skill.run")
        assert len(results) == 2
        assert results[0]["detail"] == "heartbeat"
        assert results[1]["detail"] == "network-scan"

    def test_search_case_insensitive(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("SSH.connect", "proxmox", "fabric")

        results = audit.search("ssh")
        assert len(results) == 1

    def test_search_respects_limit(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        for i in range(20):
            audit.log("repeat", f"entry-{i}")

        results = audit.search("repeat", limit=5)
        assert len(results) == 5

    def test_search_no_results(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        audit.log("action", "detail")

        results = audit.search("nonexistent")
        assert results == []

    def test_path_property(self, tmp_path):
        log_file = tmp_path / "audit.log"
        audit = AuditLog(log_path=log_file)
        assert audit.path == log_file
