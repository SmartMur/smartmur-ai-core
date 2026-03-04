"""Tests for the standardized report output system."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from superpowers.reporting import (
    Report,
    ReportFormatter,
    ReportItem,
    ReportRegistry,
    ReportSection,
    quick_report,
)

# =============================================================================
# ReportItem tests
# =============================================================================


class TestReportItem:
    def test_create_default(self):
        item = ReportItem(label="CPU", value="45%")
        assert item.label == "CPU"
        assert item.value == "45%"
        assert item.status == "info"

    def test_create_with_status(self):
        item = ReportItem(label="Disk", value="92%", status="warn")
        assert item.status == "warn"

    def test_to_dict(self):
        item = ReportItem(label="RAM", value="8GB", status="ok")
        d = item.to_dict()
        assert d == {"label": "RAM", "value": "8GB", "status": "ok"}


# =============================================================================
# ReportSection tests
# =============================================================================


class TestReportSection:
    def test_create_minimal(self):
        sec = ReportSection(heading="Health Checks")
        assert sec.heading == "Health Checks"
        assert sec.content == ""
        assert sec.status == "pass"
        assert sec.items == []

    def test_create_with_items(self):
        items = [
            ReportItem(label="Web", value="200 OK", status="ok"),
            ReportItem(label="DB", value="timeout", status="fail"),
        ]
        sec = ReportSection(heading="Services", items=items, status="fail")
        assert len(sec.items) == 2
        assert sec.status == "fail"

    def test_to_dict(self):
        sec = ReportSection(
            heading="Checks",
            content="All checks passed",
            status="pass",
            items=[ReportItem(label="A", value="1", status="ok")],
        )
        d = sec.to_dict()
        assert d["heading"] == "Checks"
        assert d["content"] == "All checks passed"
        assert len(d["items"]) == 1
        assert d["items"][0]["label"] == "A"


# =============================================================================
# Report tests
# =============================================================================


class TestReport:
    def test_create_minimal(self):
        r = Report(title="Test Report")
        assert r.title == "Test Report"
        assert r.status == "pass"
        assert r.command == ""
        assert r.sections == []
        assert r.metadata == {}
        assert len(r.id) == 12
        assert r.started_at  # auto-set

    def test_finish(self):
        r = Report(title="Test")
        assert r.finished_at == ""
        r.finish()
        assert r.finished_at != ""

    def test_finish_with_status(self):
        r = Report(title="Test")
        r.finish(status="fail")
        assert r.status == "fail"
        assert r.finished_at != ""

    def test_duration_seconds(self):
        r = Report(title="Test")
        r.started_at = "2026-01-01T00:00:00+00:00"
        r.finished_at = "2026-01-01T00:00:10+00:00"
        assert r.duration_seconds == 10.0

    def test_duration_no_finish(self):
        r = Report(title="Test")
        assert r.duration_seconds == 0.0

    def test_section_count(self):
        r = Report(title="Test", sections=[ReportSection(heading="A"), ReportSection(heading="B")])
        assert r.section_count == 2

    def test_item_count(self):
        r = Report(
            title="Test",
            sections=[
                ReportSection(
                    heading="A",
                    items=[ReportItem(label="x", value="1"), ReportItem(label="y", value="2")],
                ),
                ReportSection(heading="B", items=[ReportItem(label="z", value="3")]),
            ],
        )
        assert r.item_count == 3

    def test_to_dict(self):
        r = Report(
            title="Deploy",
            command="claw deploy",
            status="pass",
            metadata={"host": "prod"},
        )
        r.finish()
        d = r.to_dict()
        assert d["title"] == "Deploy"
        assert d["command"] == "claw deploy"
        assert d["status"] == "pass"
        assert d["metadata"] == {"host": "prod"}
        assert "id" in d
        assert "duration_seconds" in d

    def test_from_dict_roundtrip(self):
        original = Report(
            title="Roundtrip",
            command="test",
            status="warn",
            metadata={"env": "dev"},
            sections=[
                ReportSection(
                    heading="Checks",
                    content="Some content",
                    status="warn",
                    items=[ReportItem(label="A", value="ok", status="ok")],
                )
            ],
        )
        original.finish()
        d = original.to_dict()
        restored = Report.from_dict(d)
        assert restored.title == "Roundtrip"
        assert restored.command == "test"
        assert restored.status == "warn"
        assert restored.metadata == {"env": "dev"}
        assert len(restored.sections) == 1
        assert restored.sections[0].heading == "Checks"
        assert restored.sections[0].content == "Some content"
        assert len(restored.sections[0].items) == 1
        assert restored.sections[0].items[0].label == "A"


# =============================================================================
# ReportFormatter — JSON
# =============================================================================


class TestFormatterJSON:
    def test_to_json_valid(self):
        r = Report(title="JSON Test")
        r.finish()
        output = ReportFormatter.to_json(r)
        parsed = json.loads(output)
        assert parsed["title"] == "JSON Test"

    def test_to_json_with_sections(self):
        r = Report(
            title="Full",
            sections=[
                ReportSection(
                    heading="S1",
                    items=[ReportItem(label="X", value="1", status="ok")],
                )
            ],
        )
        output = ReportFormatter.to_json(r)
        parsed = json.loads(output)
        assert len(parsed["sections"]) == 1
        assert parsed["sections"][0]["items"][0]["label"] == "X"


# =============================================================================
# ReportFormatter — Markdown
# =============================================================================


class TestFormatterMarkdown:
    def test_to_markdown_title(self):
        r = Report(title="MD Test", status="pass")
        md = ReportFormatter.to_markdown(r)
        assert "# [PASS] MD Test" in md

    def test_to_markdown_fail_badge(self):
        r = Report(title="Failing", status="fail")
        md = ReportFormatter.to_markdown(r)
        assert "[FAIL]" in md

    def test_to_markdown_sections(self):
        r = Report(
            title="With Sections",
            sections=[
                ReportSection(
                    heading="Health",
                    status="warn",
                    items=[ReportItem(label="CPU", value="95%", status="warn")],
                )
            ],
        )
        md = ReportFormatter.to_markdown(r)
        assert "## [WARN] Health" in md
        assert "CPU" in md
        assert "95%" in md

    def test_to_markdown_meta_table(self):
        r = Report(title="Meta", command="claw test", metadata={"host": "prod"})
        md = ReportFormatter.to_markdown(r)
        assert "| Command | `claw test` |" in md
        assert "| host | prod |" in md

    def test_to_markdown_content_in_section(self):
        r = Report(
            title="Content",
            sections=[ReportSection(heading="Notes", content="Everything ran smoothly.")],
        )
        md = ReportFormatter.to_markdown(r)
        assert "Everything ran smoothly." in md


# =============================================================================
# ReportFormatter — Terminal (smoke test)
# =============================================================================


class TestFormatterTerminal:
    def test_to_terminal_runs(self, capsys):
        """Just ensure to_terminal doesn't crash — it uses Rich internally."""
        r = Report(
            title="Terminal Test",
            command="claw check",
            metadata={"env": "test"},
            sections=[
                ReportSection(
                    heading="Services",
                    content="Checking services",
                    status="pass",
                    items=[
                        ReportItem(label="Web", value="OK", status="ok"),
                        ReportItem(label="DB", value="slow", status="warn"),
                    ],
                ),
            ],
        )
        r.finish()
        # Should not raise
        ReportFormatter.to_terminal(r)


# =============================================================================
# ReportFormatter — Save
# =============================================================================


class TestFormatterSave:
    def test_save_creates_files(self, tmp_path):
        r = Report(title="Save Test")
        r.finish()
        json_path, md_path = ReportFormatter.save(r, output_dir=tmp_path)
        assert json_path.exists()
        assert md_path.exists()
        assert json_path.suffix == ".json"
        assert md_path.suffix == ".md"

    def test_save_json_is_valid(self, tmp_path):
        r = Report(title="Valid JSON", command="test")
        r.finish()
        json_path, _ = ReportFormatter.save(r, output_dir=tmp_path)
        data = json.loads(json_path.read_text())
        assert data["title"] == "Valid JSON"

    def test_save_md_has_content(self, tmp_path):
        r = Report(title="Valid MD")
        r.finish()
        _, md_path = ReportFormatter.save(r, output_dir=tmp_path)
        content = md_path.read_text()
        assert "Valid MD" in content


# =============================================================================
# ReportRegistry
# =============================================================================


class TestReportRegistry:
    def test_list_empty(self, tmp_path):
        reg = ReportRegistry(reports_dir=tmp_path / "reports")
        assert reg.list_reports() == []

    def test_save_and_list(self, tmp_path):
        reg = ReportRegistry(reports_dir=tmp_path / "reports")
        r = Report(title="Saved", status="pass")
        r.finish()
        reg.save_report(r)
        reports = reg.list_reports()
        assert len(reports) == 1
        assert reports[0]["title"] == "Saved"

    def test_get_report(self, tmp_path):
        reg = ReportRegistry(reports_dir=tmp_path / "reports")
        r = Report(title="Fetch Me", command="test")
        r.finish()
        reg.save_report(r)
        loaded = reg.get_report(r.id)
        assert loaded is not None
        assert loaded.title == "Fetch Me"

    def test_get_report_not_found(self, tmp_path):
        reg = ReportRegistry(reports_dir=tmp_path / "reports")
        assert reg.get_report("nonexistent") is None

    def test_delete_report(self, tmp_path):
        reg = ReportRegistry(reports_dir=tmp_path / "reports")
        r = Report(title="Delete Me")
        r.finish()
        reg.save_report(r)
        assert len(reg.list_reports()) == 1
        deleted = reg.delete_report(r.id)
        assert deleted is True
        assert len(reg.list_reports()) == 0

    def test_delete_nonexistent(self, tmp_path):
        reg = ReportRegistry(reports_dir=tmp_path / "reports")
        assert reg.delete_report("nope") is False

    def test_list_respects_limit(self, tmp_path):
        reg = ReportRegistry(reports_dir=tmp_path / "reports")
        for i in range(5):
            r = Report(title=f"Report {i}")
            r.finish()
            reg.save_report(r)
        reports = reg.list_reports(limit=3)
        assert len(reports) == 3

    def test_reports_dir_property(self, tmp_path):
        d = tmp_path / "reps"
        reg = ReportRegistry(reports_dir=d)
        assert reg.reports_dir == d


# =============================================================================
# quick_report helper
# =============================================================================


class TestQuickReport:
    def test_all_ok(self):
        r = quick_report("All Good", [("CPU", "10%", "ok"), ("RAM", "4GB", "ok")])
        assert r.status == "pass"
        assert r.title == "All Good"
        assert len(r.sections) == 1
        assert r.sections[0].heading == "Results"
        assert len(r.sections[0].items) == 2
        assert r.finished_at != ""

    def test_warn_status(self):
        r = quick_report("Mixed", [("CPU", "90%", "warn"), ("RAM", "4GB", "ok")])
        assert r.status == "warn"

    def test_fail_status(self):
        r = quick_report("Bad", [("Disk", "FULL", "fail"), ("CPU", "90%", "warn")])
        assert r.status == "fail"

    def test_with_command_and_metadata(self):
        r = quick_report(
            "Check",
            [("A", "1", "info")],
            command="claw check",
            metadata={"host": "localhost"},
        )
        assert r.command == "claw check"
        assert r.metadata == {"host": "localhost"}

    def test_quick_report_roundtrip(self, tmp_path):
        """Ensure a quick_report can be saved and loaded."""
        r = quick_report("Roundtrip", [("X", "Y", "ok")])
        json_path, _ = ReportFormatter.save(r, output_dir=tmp_path)
        data = json.loads(json_path.read_text())
        loaded = Report.from_dict(data)
        assert loaded.title == "Roundtrip"
        assert loaded.sections[0].items[0].label == "X"


# =============================================================================
# CLI tests
# =============================================================================


class TestCLI:
    @pytest.fixture()
    def runner(self):
        return CliRunner()

    @pytest.fixture()
    def populated_registry(self, tmp_path, monkeypatch):
        """Create a registry with a saved report and monkeypatch get_data_dir."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        monkeypatch.setattr("superpowers.reporting.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr(
            "superpowers.cli_report.ReportRegistry", lambda: ReportRegistry(reports_dir=reports_dir)
        )
        reg = ReportRegistry(reports_dir=reports_dir)
        r = Report(title="CLI Test Report", command="claw test", status="pass")
        r.finish()
        reg.save_report(r)
        return reg, r

    def test_list_empty(self, runner, tmp_path, monkeypatch):
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        monkeypatch.setattr(
            "superpowers.cli_report.ReportRegistry", lambda: ReportRegistry(reports_dir=reports_dir)
        )
        from superpowers.cli_report import report_group

        result = runner.invoke(report_group, ["list"])
        assert result.exit_code == 0
        assert "No saved reports" in result.output

    def test_list_with_reports(self, runner, populated_registry):
        _, report = populated_registry
        from superpowers.cli_report import report_group

        result = runner.invoke(report_group, ["list"])
        assert result.exit_code == 0
        # Rich may word-wrap long titles, so check for the report ID instead
        assert report.id in result.output

    def test_show_report(self, runner, populated_registry):
        _, report = populated_registry
        from superpowers.cli_report import report_group

        result = runner.invoke(report_group, ["show", report.id])
        assert result.exit_code == 0
        assert "CLI Test Report" in result.output

    def test_show_not_found(self, runner, tmp_path, monkeypatch):
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        monkeypatch.setattr(
            "superpowers.cli_report.ReportRegistry", lambda: ReportRegistry(reports_dir=reports_dir)
        )
        from superpowers.cli_report import report_group

        result = runner.invoke(report_group, ["show", "nonexistent"])
        assert result.exit_code != 0

    def test_export_json(self, runner, populated_registry):
        _, report = populated_registry
        from superpowers.cli_report import report_group

        result = runner.invoke(report_group, ["export", report.id, "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["title"] == "CLI Test Report"

    def test_export_md(self, runner, populated_registry):
        _, report = populated_registry
        from superpowers.cli_report import report_group

        result = runner.invoke(report_group, ["export", report.id, "--format", "md"])
        assert result.exit_code == 0
        assert "CLI Test Report" in result.output

    def test_export_to_file(self, runner, populated_registry, tmp_path):
        _, report = populated_registry
        out_file = tmp_path / "export.json"
        from superpowers.cli_report import report_group

        result = runner.invoke(
            report_group, ["export", report.id, "--format", "json", "-o", str(out_file)]
        )
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["title"] == "CLI Test Report"


# =============================================================================
# Dashboard API tests
# =============================================================================


class TestDashboardAPI:
    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        """TestClient with auth disabled and reports registry pointed at tmp_path."""
        from dashboard import deps
        from dashboard.app import app

        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        # Save a test report
        reg = ReportRegistry(reports_dir=reports_dir)
        r = Report(title="API Test", command="claw api", status="pass")
        r.finish()
        reg.save_report(r)

        # Patch the router's registry factory
        monkeypatch.setattr(
            "dashboard.routers.reports._get_registry",
            lambda: ReportRegistry(reports_dir=reports_dir),
        )

        # Disable auth
        app.dependency_overrides[deps.require_auth] = lambda: "testuser"

        yield TestClient(app), r

        app.dependency_overrides.clear()

    def test_list_reports(self, client):
        tc, _ = client
        resp = tc.get("/api/reports/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["title"] == "API Test"

    def test_list_reports_with_limit(self, client):
        tc, _ = client
        resp = tc.get("/api/reports/reports?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_report(self, client):
        tc, report = client
        resp = tc.get(f"/api/reports/reports/{report.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "API Test"
        assert data["id"] == report.id

    def test_get_report_not_found(self, client):
        tc, _ = client
        resp = tc.get("/api/reports/reports/nonexistent-id")
        assert resp.status_code == 404
