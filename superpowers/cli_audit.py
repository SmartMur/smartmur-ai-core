"""Click subcommands for audit log."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.audit import AuditLog

console = Console()


@click.group("audit")
def audit_group():
    """View the audit log."""


@audit_group.command("tail")
@click.option("--limit", "-n", default=20, help="Number of entries to show.")
def audit_tail(limit: int):
    """Show recent audit log entries."""
    audit = AuditLog()
    entries = audit.tail(limit)

    if not entries:
        console.print("[dim]No audit log entries.[/dim]")
        return

    table = Table(title=f"Audit Log (last {limit})")
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Detail")
    table.add_column("Source", style="green")

    for entry in entries:
        table.add_row(
            entry.get("ts", "?")[:19],
            entry.get("action", ""),
            entry.get("detail", ""),
            entry.get("source", ""),
        )

    console.print(table)


@audit_group.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=50, help="Max results.")
def audit_search(query: str, limit: int):
    """Search audit log entries."""
    audit = AuditLog()
    entries = audit.search(query, limit)

    if not entries:
        console.print(f"[dim]No entries matching '{query}'.[/dim]")
        return

    table = Table(title=f"Audit Search: '{query}' ({len(entries)} results)")
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Detail")
    table.add_column("Source", style="green")

    for entry in entries:
        table.add_row(
            entry.get("ts", "?")[:19],
            entry.get("action", ""),
            entry.get("detail", ""),
            entry.get("source", ""),
        )

    console.print(table)
