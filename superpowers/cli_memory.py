"""Click subcommands for the persistent memory store."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.memory.base import MemoryStoreError
from superpowers.memory.context import ContextBuilder
from superpowers.memory.store import MemoryStore

console = Console()


@click.group("memory")
def memory_group():
    """Persistent memory store — remember, recall, search."""


@memory_group.command("remember")
@click.argument("key")
@click.argument("value")
@click.option("--category", "-c", default="fact", help="Memory category.")
@click.option("--tags", "-t", default="", help="Comma-separated tags.")
@click.option("--project", "-p", default="", help="Project scope.")
def memory_remember(key: str, value: str, category: str, tags: str, project: str):
    """Store a memory (upserts if key exists)."""
    store = MemoryStore()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    try:
        entry = store.remember(key, value, category=category, tags=tag_list, project=project)
        console.print(
            f"[green]Remembered[/green] [bold]{entry.key}[/bold] ({entry.category.value})"
        )
    except MemoryStoreError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@memory_group.command("recall")
@click.argument("key")
@click.option("--category", "-c", default=None, help="Filter by category.")
def memory_recall(key: str, category: str | None):
    """Retrieve a memory by key."""
    store = MemoryStore()
    entry = store.recall(key, category=category)
    if entry is None:
        console.print(f"[yellow]Not found:[/yellow] {key}")
        raise SystemExit(1)
    console.print(f"[bold]{entry.key}[/bold] ({entry.category.value})")
    console.print(f"  {entry.value}")
    if entry.tags:
        console.print(f"  Tags: {', '.join(entry.tags)}")
    if entry.project:
        console.print(f"  Project: {entry.project}")
    console.print(f"  Accessed: {entry.access_count}x | Last: {entry.accessed_at}")


@memory_group.command("search")
@click.argument("query")
@click.option("--category", "-c", default=None, help="Filter by category.")
@click.option("--project", "-p", default=None, help="Filter by project.")
def memory_search(query: str, category: str | None, project: str | None):
    """Search memories by key or value."""
    store = MemoryStore()
    results = store.search(query, category=category, project=project)
    if not results:
        console.print("[dim]No matches.[/dim]")
        return
    table = Table(title=f"Search: {query}", show_lines=False)
    table.add_column("Cat", style="dim", width=10)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", max_width=60)
    table.add_column("Project", style="dim")
    for e in results:
        table.add_row(e.category.value, e.key, e.value, e.project or "-")
    console.print(table)


@memory_group.command("forget")
@click.argument("key")
@click.option("--category", "-c", default=None, help="Filter by category.")
def memory_forget(key: str, category: str | None):
    """Delete a memory."""
    store = MemoryStore()
    if store.forget(key, category=category):
        console.print(f"[red]Forgot[/red] [bold]{key}[/bold]")
    else:
        console.print(f"[yellow]Not found:[/yellow] {key}")
        raise SystemExit(1)


@memory_group.command("list")
@click.option("--category", "-c", default=None, help="Filter by category.")
@click.option("--project", "-p", default=None, help="Filter by project.")
@click.option("--limit", "-n", default=50, help="Max results.")
def memory_list(category: str | None, project: str | None, limit: int):
    """List stored memories."""
    store = MemoryStore()
    entries = store.list_memories(category=category, project=project, limit=limit)
    if not entries:
        console.print("[dim]No memories stored.[/dim]")
        return
    table = Table(title="Memories", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Cat", style="dim", width=10)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", max_width=60)
    table.add_column("Project", style="dim")
    table.add_column("Hits", style="dim", width=4)
    for i, e in enumerate(entries, 1):
        table.add_row(
            str(i), e.category.value, e.key, e.value, e.project or "-", str(e.access_count)
        )
    console.print(table)


@memory_group.command("stats")
def memory_stats():
    """Show memory store statistics."""
    store = MemoryStore()
    s = store.stats()
    console.print(f"[bold]Total memories:[/bold] {s['total']}")
    if s["by_category"]:
        for cat, cnt in sorted(s["by_category"].items()):
            console.print(f"  {cat}: {cnt}")
    if s["oldest"]:
        console.print(f"[dim]Oldest: {s['oldest']}[/dim]")
    if s["newest"]:
        console.print(f"[dim]Newest: {s['newest']}[/dim]")


@memory_group.command("decay")
@click.option("--days", "-d", default=90, help="Delete entries not accessed in N days.")
def memory_decay(days: int):
    """Delete stale memories not accessed in N days."""
    store = MemoryStore()
    count = store.decay(days=days)
    console.print(f"[yellow]Decayed {count} memories[/yellow] (older than {days} days)")


@memory_group.command("context")
@click.option("--project", "-p", default="", help="Project scope.")
def memory_context(project: str):
    """Show what auto-context would inject."""
    store = MemoryStore()
    builder = ContextBuilder(store)
    ctx = builder.build_context(project=project)
    if ctx:
        console.print(ctx)
    else:
        console.print("[dim]No context to inject.[/dim]")
