"""Standardized report output system for claude-superpowers.

Provides dataclasses for structured reports, formatters for JSON/Markdown/terminal,
and a registry for persisting reports to disk.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from superpowers.config import get_data_dir

logger = logging.getLogger(__name__)

Status = Literal["pass", "fail", "warn"]
ItemStatus = Literal["ok", "warn", "fail", "info"]


@dataclass
class ReportItem:
    """A single labelled value with a status indicator."""

    label: str
    value: str
    status: ItemStatus = "info"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReportSection:
    """A named section within a report, containing prose and/or items."""

    heading: str
    content: str = ""
    status: Status = "pass"
    items: list[ReportItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "heading": self.heading,
            "content": self.content,
            "status": self.status,
            "items": [i.to_dict() for i in self.items],
        }


@dataclass
class Report:
    """Top-level report container."""

    title: str
    command: str = ""
    status: Status = "pass"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str = ""
    sections: list[ReportSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def finish(self, status: Status | None = None) -> None:
        """Mark the report as finished, optionally overriding status."""
        self.finished_at = datetime.now(UTC).isoformat()
        if status is not None:
            self.status = status

    @property
    def duration_seconds(self) -> float:
        """Compute elapsed time if both timestamps are set."""
        if not self.started_at or not self.finished_at:
            return 0.0
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.finished_at)
            return (end - start).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    @property
    def section_count(self) -> int:
        return len(self.sections)

    @property
    def item_count(self) -> int:
        return sum(len(s.items) for s in self.sections)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "command": self.command,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "sections": [s.to_dict() for s in self.sections],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Report:
        """Reconstruct a Report from a dict (e.g. loaded from JSON)."""
        sections = []
        for sd in data.get("sections", []):
            items = [ReportItem(**i) for i in sd.get("items", [])]
            sections.append(
                ReportSection(
                    heading=sd["heading"],
                    content=sd.get("content", ""),
                    status=sd.get("status", "pass"),
                    items=items,
                )
            )
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            title=data["title"],
            command=data.get("command", ""),
            status=data.get("status", "pass"),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            sections=sections,
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_STATUS_BADGE = {"pass": "[PASS]", "fail": "[FAIL]", "warn": "[WARN]"}
_ITEM_BADGE = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]", "info": "[INFO]"}


class ReportFormatter:
    """Converts a Report to various output formats."""

    # --- JSON ---

    @staticmethod
    def to_json(report: Report, indent: int = 2) -> str:
        """Serialise to pretty-printed JSON."""
        return json.dumps(report.to_dict(), indent=indent, default=str)

    # --- Markdown ---

    @staticmethod
    def to_markdown(report: Report) -> str:
        """Render human-readable Markdown."""
        lines: list[str] = []
        badge = _STATUS_BADGE.get(report.status, "")
        lines.append(f"# {badge} {report.title}")
        lines.append("")

        # Meta table
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        if report.command:
            lines.append(f"| Command | `{report.command}` |")
        lines.append(f"| Status | **{report.status}** |")
        if report.started_at:
            lines.append(f"| Started | {report.started_at} |")
        if report.finished_at:
            lines.append(f"| Finished | {report.finished_at} |")
            lines.append(f"| Duration | {report.duration_seconds:.1f}s |")
        if report.metadata:
            for k, v in report.metadata.items():
                lines.append(f"| {k} | {v} |")
        lines.append("")

        # Sections
        for section in report.sections:
            sec_badge = _STATUS_BADGE.get(section.status, "")
            lines.append(f"## {sec_badge} {section.heading}")
            lines.append("")
            if section.content:
                lines.append(section.content)
                lines.append("")
            if section.items:
                lines.append("| Status | Label | Value |")
                lines.append("|--------|-------|-------|")
                for item in section.items:
                    ib = _ITEM_BADGE.get(item.status, "")
                    lines.append(f"| {ib} | {item.label} | {item.value} |")
                lines.append("")

        return "\n".join(lines)

    # --- Terminal (Rich) ---

    @staticmethod
    def to_terminal(report: Report) -> None:
        """Print a rich-formatted report to the console."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        style_map: dict[str, str] = {
            "pass": "bold green",
            "fail": "bold red",
            "warn": "bold yellow",
        }
        item_style_map: dict[str, str] = {
            "ok": "green",
            "fail": "red",
            "warn": "yellow",
            "info": "cyan",
        }

        # Title
        st = style_map.get(report.status, "white")
        console.print(f"\n[{st}]{_STATUS_BADGE.get(report.status, '')} {report.title}[/{st}]")
        if report.command:
            console.print(f"  [dim]Command:[/dim] {report.command}")
        console.print(f"  [dim]Started:[/dim] {report.started_at}")
        if report.finished_at:
            console.print(
                f"  [dim]Finished:[/dim] {report.finished_at}  ({report.duration_seconds:.1f}s)"
            )
        if report.metadata:
            for k, v in report.metadata.items():
                console.print(f"  [dim]{k}:[/dim] {v}")
        console.print()

        # Sections
        for section in report.sections:
            sec_st = style_map.get(section.status, "white")
            console.print(
                f"  [{sec_st}]{_STATUS_BADGE.get(section.status, '')} {section.heading}[/{sec_st}]"
            )
            if section.content:
                console.print(f"    {section.content}")
            if section.items:
                table = Table(show_header=True, padding=(0, 1), show_lines=False)
                table.add_column("Status", width=8)
                table.add_column("Label", style="bold")
                table.add_column("Value")
                for item in section.items:
                    ist = item_style_map.get(item.status, "white")
                    table.add_row(
                        f"[{ist}]{_ITEM_BADGE.get(item.status, '')}[/{ist}]",
                        item.label,
                        item.value,
                    )
                console.print(table)
            console.print()

    # --- Save ---

    @staticmethod
    def save(report: Report, output_dir: Path | None = None) -> tuple[Path, Path]:
        """Persist a report as JSON + Markdown files.

        Returns (json_path, md_path).
        """
        if output_dir is None:
            output_dir = get_data_dir() / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        base = f"{ts}_{report.id}"
        json_path = output_dir / f"{base}.json"
        md_path = output_dir / f"{base}.md"

        json_path.write_text(ReportFormatter.to_json(report))
        md_path.write_text(ReportFormatter.to_markdown(report))

        logger.info("Report saved: %s", json_path)
        return json_path, md_path


# ---------------------------------------------------------------------------
# Registry — discover and manage persisted reports
# ---------------------------------------------------------------------------


class ReportRegistry:
    """Discovers and loads reports from the reports directory."""

    def __init__(self, reports_dir: Path | None = None):
        self._dir = reports_dir or (get_data_dir() / "reports")
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def reports_dir(self) -> Path:
        return self._dir

    def list_reports(self, limit: int = 50) -> list[dict]:
        """Return summary dicts for saved reports, most recent first."""
        json_files = sorted(self._dir.glob("*.json"), reverse=True)
        results: list[dict] = []
        for jf in json_files[:limit]:
            try:
                data = json.loads(jf.read_text())
                results.append(
                    {
                        "id": data.get("id", jf.stem),
                        "title": data.get("title", ""),
                        "status": data.get("status", ""),
                        "started_at": data.get("started_at", ""),
                        "finished_at": data.get("finished_at", ""),
                        "duration_seconds": data.get("duration_seconds", 0),
                        "file": str(jf),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def get_report(self, report_id: str) -> Report | None:
        """Load a report by ID or filename stem."""
        # Try exact file match first
        for jf in self._dir.glob("*.json"):
            if report_id in jf.stem:
                try:
                    data = json.loads(jf.read_text())
                    return Report.from_dict(data)
                except (json.JSONDecodeError, OSError, KeyError):
                    continue
        return None

    def save_report(self, report: Report) -> tuple[Path, Path]:
        """Save a report to the registry directory."""
        return ReportFormatter.save(report, self._dir)

    def delete_report(self, report_id: str) -> bool:
        """Delete JSON and MD files for a report. Returns True if any deleted."""
        deleted = False
        for pattern in ("*.json", "*.md"):
            for f in self._dir.glob(pattern):
                if report_id in f.stem:
                    f.unlink()
                    deleted = True
        return deleted


# ---------------------------------------------------------------------------
# Convenience helper
# ---------------------------------------------------------------------------


def quick_report(
    title: str,
    items: list[tuple[str, str, ItemStatus]],
    command: str = "",
    metadata: dict | None = None,
) -> Report:
    """Create a simple single-section check-style report.

    Args:
        title: Report title.
        items: List of (label, value, status) tuples.
        command: Optional command that produced the report.
        metadata: Optional extra metadata dict.

    Returns:
        A finished Report with one section containing all items.
    """
    report_items = [ReportItem(label=lbl, value=v, status=s) for lbl, v, s in items]

    # Derive overall status from items
    statuses = {i.status for i in report_items}
    if "fail" in statuses:
        overall: Status = "fail"
        section_status: Status = "fail"
    elif "warn" in statuses:
        overall = "warn"
        section_status = "warn"
    else:
        overall = "pass"
        section_status = "pass"

    section = ReportSection(
        heading="Results",
        items=report_items,
        status=section_status,
    )

    report = Report(
        title=title,
        command=command,
        status=overall,
        sections=[section],
        metadata=metadata or {},
    )
    report.finish()
    return report
