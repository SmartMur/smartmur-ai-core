"""Click subcommands for pack management."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from superpowers.pack_manager import PackError, PackManager

console = Console()


@click.group("pack")
def pack_group():
    """Manage skill/workflow/agent packs."""


@pack_group.command("install")
@click.argument("source")
def pack_install(source: str):
    """Install a pack from a local directory or git URL."""
    pm = PackManager()
    try:
        manifest = pm.install(source)
        console.print(
            f"[green]Installed pack:[/green] [bold]{manifest.name}[/bold] v{manifest.version}"
        )
        if manifest.skills:
            console.print(f"  Skills:    {', '.join(manifest.skills)}")
        if manifest.workflows:
            console.print(f"  Workflows: {', '.join(manifest.workflows)}")
        if manifest.agents:
            console.print(f"  Agents:    {', '.join(manifest.agents)}")
    except PackError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@pack_group.command("update")
@click.argument("name")
def pack_update(name: str):
    """Update an installed pack by re-fetching from its source."""
    pm = PackManager()
    try:
        manifest = pm.update(name)
        console.print(
            f"[green]Updated pack:[/green] [bold]{manifest.name}[/bold] v{manifest.version}"
        )
    except PackError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@pack_group.command("list")
def pack_list():
    """List all installed packs."""
    pm = PackManager()
    packs = pm.list_installed()
    if not packs:
        console.print("[dim]No packs installed.[/dim]")
        return

    table = Table(title="Installed Packs", show_lines=False)
    table.add_column("Name", style="bold cyan")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Skills", style="green")
    table.add_column("Workflows", style="yellow")
    table.add_column("Agents", style="magenta")

    for p in packs:
        table.add_row(
            p["name"],
            p["version"],
            p["description"],
            ", ".join(p.get("skills", [])) or "-",
            ", ".join(p.get("workflows", [])) or "-",
            ", ".join(p.get("agents", [])) or "-",
        )

    console.print(table)


@pack_group.command("uninstall")
@click.argument("name")
def pack_uninstall(name: str):
    """Remove an installed pack and its artefacts."""
    pm = PackManager()
    try:
        pm.uninstall(name)
        console.print(f"[red]Uninstalled pack:[/red] [bold]{name}[/bold]")
    except PackError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@pack_group.command("validate")
@click.argument("source", type=click.Path(exists=True, file_okay=False, path_type=Path))
def pack_validate(source: Path):
    """Validate a pack directory structure and checksums."""
    pm = PackManager()
    errors = pm.validate(source)
    if errors:
        console.print("[red]Validation failed:[/red]")
        for e in errors:
            console.print(f"  - {e}")
        raise SystemExit(1)
    console.print("[green]Pack is valid.[/green]")
