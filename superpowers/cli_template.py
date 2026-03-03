"""Click subcommands for template management."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("template")
def template_group():
    """Manage shipped configuration templates."""


@template_group.command("init")
def template_init():
    """Copy managed templates to config directory."""
    from superpowers.template_manager import TemplateManager

    tm = TemplateManager()
    installed = tm.init()
    if installed:
        for name in installed:
            console.print(f"  [green]Installed:[/green] {name}")
        console.print(f"\n[green]{len(installed)} template(s) initialized.[/green]")
    else:
        console.print("[dim]All templates already installed.[/dim]")


@template_group.command("list")
def template_list():
    """List all tracked templates and their status."""
    from superpowers.template_manager import TemplateManager

    tm = TemplateManager()
    templates = tm.list_templates()

    table = Table(title="Managed Templates", show_lines=False)
    table.add_column("Template", style="cyan")
    table.add_column("Destination")
    table.add_column("Status")

    style_map = {
        "current": "[green]current[/green]",
        "modified": "[yellow]modified[/yellow]",
        "missing": "[red]missing[/red]",
        "untracked": "[dim]untracked[/dim]",
    }

    for t in templates:
        status_str = style_map.get(t["status"], t["status"])
        table.add_row(t["name"], t["dest"], status_str)

    console.print(table)


@template_group.command("diff")
@click.argument("name", required=False)
def template_diff(name: str | None):
    """Show differences between current and shipped templates."""
    from superpowers.template_manager import TemplateManager

    tm = TemplateManager()
    diffs = tm.diff(name)

    any_diff = False
    for tname, diff_text in diffs.items():
        if diff_text:
            any_diff = True
            console.print(f"\n[bold cyan]{tname}[/bold cyan]")
            console.print(diff_text)

    if not any_diff:
        console.print("[dim]No differences found.[/dim]")


@template_group.command("reset")
@click.argument("name")
def template_reset(name: str):
    """Restore a template to its shipped version (creates backup)."""
    from superpowers.template_manager import TemplateManager

    tm = TemplateManager()
    ok = tm.reset(name)
    if ok:
        console.print(f"[green]Reset:[/green] {name} (backup created)")
    else:
        console.print(f"[red]Error:[/red] Template '{name}' not found or source missing.")
        raise SystemExit(1)


@template_group.command("upgrade")
def template_upgrade():
    """Upgrade all templates, preserving user customizations."""
    from superpowers.template_manager import TemplateManager

    tm = TemplateManager()
    actions = tm.upgrade()

    style_map = {
        "updated": "[green]updated[/green]",
        "backup_and_updated": "[yellow]backup + updated[/yellow]",
        "skipped": "[dim]skipped[/dim]",
        "missing_source": "[red]source missing[/red]",
    }

    for name, action in actions.items():
        action_str = style_map.get(action, action)
        console.print(f"  {name}: {action_str}")

    console.print(f"\n[green]Upgrade complete.[/green]")
