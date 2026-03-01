"""Click subcommands for file watcher management."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.watcher.base import WatcherError
from superpowers.watcher.engine import WatcherEngine

console = Console()


@click.group("watcher")
def watcher_group():
    """Manage file watchers."""


@watcher_group.command("list")
def watcher_list():
    """List configured watcher rules."""
    try:
        engine = WatcherEngine()
    except WatcherError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    rules = engine.list_rules()
    if not rules:
        console.print("[dim]No watcher rules configured.[/dim]")
        console.print("  Add rules to: ~/.claude-superpowers/watchers.yaml")
        return

    table = Table(title="Watcher Rules")
    table.add_column("Name", style="cyan")
    table.add_column("Path")
    table.add_column("Events")
    table.add_column("Action", style="green")
    table.add_column("Command")
    table.add_column("Enabled")

    for rule in rules:
        table.add_row(
            rule.name,
            rule.path,
            ", ".join(rule.events),
            rule.action.value,
            rule.command[:40],
            "[green]yes[/green]" if rule.enabled else "[red]no[/red]",
        )

    console.print(table)


@watcher_group.command("start")
def watcher_start():
    """Start the watcher daemon (foreground, Ctrl+C to stop)."""
    import signal

    try:
        engine = WatcherEngine()
    except WatcherError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    rules = engine.list_rules()
    enabled = sum(1 for r in rules if r.enabled)
    if not rules:
        console.print("[yellow]No watcher rules configured. Nothing to watch.[/yellow]")
        return

    console.print(f"[bold]Starting watcher with {enabled} enabled rules...[/bold]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")

    engine.start()

    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        console.print("[bold]Watcher stopped.[/bold]")


@watcher_group.command("test")
@click.argument("rule_name")
def watcher_test(rule_name: str):
    """Simulate a 'created' event for a rule to test its action."""
    try:
        engine = WatcherEngine()
        rule = engine.get_rule(rule_name)
    except WatcherError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    from watchdog.events import FileCreatedEvent

    # Simulate with a dummy file path based on the rule's path pattern
    from pathlib import Path

    watch_path = Path(rule.path).expanduser()
    if any(c in watch_path.name for c in ("*", "?", "[")):
        test_file = str(watch_path.parent / "test_file.tmp")
    else:
        test_file = str(watch_path / "test_file.tmp")

    console.print(f"[bold]Simulating 'created' event for rule '{rule_name}'[/bold]")
    console.print(f"  Test file: {test_file}")

    fake_event = FileCreatedEvent(test_file)
    try:
        engine._on_event(fake_event, rule)
        console.print("[bold green]Action executed.[/bold green]")
    except Exception as exc:
        console.print(f"[bold red]Action failed:[/bold red] {exc}")
        raise SystemExit(1)
