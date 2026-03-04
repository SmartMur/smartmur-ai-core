"""Click subcommands for the report output system."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.reporting import ReportFormatter, ReportRegistry

console = Console()


@click.group("report")
def report_group():
    """View, list, and export saved reports."""


@report_group.command("list")
@click.option("--limit", "-n", default=20, help="Max reports to show.")
def report_list(limit: int):
    """List saved reports (most recent first)."""
    registry = ReportRegistry()
    reports = registry.list_reports(limit=limit)
    if not reports:
        console.print("[dim]No saved reports.[/dim]")
        return

    table = Table(title="Saved Reports", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="cyan", width=14)
    table.add_column("Title", style="bold")
    table.add_column("Status", width=6)
    table.add_column("Started", style="dim", width=22)
    table.add_column("Duration", style="dim", width=10)

    style_map = {"pass": "green", "fail": "red", "warn": "yellow"}

    for i, r in enumerate(reports, 1):
        st = r.get("status", "")
        color = style_map.get(st, "white")
        dur = r.get("duration_seconds", 0)
        dur_str = f"{dur:.1f}s" if dur else "-"
        table.add_row(
            str(i),
            r.get("id", "?"),
            r.get("title", ""),
            f"[{color}]{st}[/{color}]",
            r.get("started_at", "")[:22],
            dur_str,
        )
    console.print(table)


@report_group.command("show")
@click.argument("report_id")
def report_show(report_id: str):
    """Display a saved report in the terminal."""
    registry = ReportRegistry()
    report = registry.get_report(report_id)
    if report is None:
        console.print(f"[bold red]Error:[/bold red] Report not found: {report_id}")
        raise SystemExit(1)
    ReportFormatter.to_terminal(report)


@report_group.command("export")
@click.argument("report_id")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "md"]),
    default="json",
    help="Export format.",
)
@click.option("--output", "-o", default=None, help="Output file path (default: stdout).")
def report_export(report_id: str, fmt: str, output: str | None):
    """Export a saved report to JSON or Markdown."""
    registry = ReportRegistry()
    report = registry.get_report(report_id)
    if report is None:
        console.print(f"[bold red]Error:[/bold red] Report not found: {report_id}")
        raise SystemExit(1)

    if fmt == "json":
        content = ReportFormatter.to_json(report)
    else:
        content = ReportFormatter.to_markdown(report)

    if output:
        from pathlib import Path

        Path(output).write_text(content)
        console.print(f"[green]Exported to {output}[/green]")
    else:
        click.echo(content)
