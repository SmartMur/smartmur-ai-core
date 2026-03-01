from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from superpowers.skill_loader import SkillLoader
from superpowers.skill_registry import SkillRegistry

console = Console()


@click.command("list")
def skill_list():
    """Show all skills with status."""
    registry = SkillRegistry()
    skills = registry.discover()

    table = Table(title="Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Slash Cmd", justify="center")
    table.add_column("Permissions")

    for s in skills:
        table.add_row(
            s.name,
            s.version,
            s.description,
            "[green]yes[/green]" if s.slash_command else "no",
            ", ".join(s.permissions) if s.permissions else "-",
        )

    console.print(table)


@click.command("info")
@click.argument("name")
def skill_info(name: str):
    """Show skill details."""
    registry = SkillRegistry()
    registry.discover()
    try:
        s = registry.get(name)
    except KeyError:
        console.print(f"[red]Skill not found:[/red] {name}")
        raise SystemExit(1)

    table = Table(title=f"Skill: {s.name}", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Name", s.name)
    table.add_row("Version", s.version)
    table.add_row("Description", s.description)
    table.add_row("Author", s.author)
    table.add_row("Script", str(s.script_path))
    table.add_row("Slash Command", "yes" if s.slash_command else "no")
    table.add_row("Triggers", ", ".join(s.triggers) if s.triggers else "-")
    table.add_row("Dependencies", ", ".join(s.dependencies) if s.dependencies else "-")
    table.add_row("Permissions", ", ".join(s.permissions) if s.permissions else "-")

    console.print(table)


@click.command("run")
@click.argument("name")
@click.argument("args", nargs=-1)
def skill_run(name: str, args: tuple[str, ...]):
    """Execute a skill."""
    registry = SkillRegistry()
    registry.discover()
    try:
        skill = registry.get(name)
    except KeyError:
        console.print(f"[red]Skill not found:[/red] {name}")
        raise SystemExit(1)

    parsed = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            parsed[k] = v
        else:
            parsed[a] = "true"

    loader = SkillLoader()
    console.print(f"[bold]Running skill:[/bold] {skill.name} v{skill.version}")
    result = loader.run(skill, parsed)

    if result.stdout:
        console.print(result.stdout, end="")
    if result.stderr:
        console.print(f"[yellow]{result.stderr}[/yellow]", end="")
    if result.returncode != 0:
        console.print(f"[red]Exited with code {result.returncode}[/red]")
        raise SystemExit(result.returncode)


@click.command("sync")
def skill_sync():
    """Regenerate all slash command symlinks."""
    registry = SkillRegistry()
    registry.discover()
    created = registry.sync_slash_commands()
    console.print(f"[green]Synced {len(created)} slash command(s)[/green]")
    for path in created:
        console.print(f"  {path} -> {path.resolve()}")


@click.command("validate")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path))
def skill_validate(path: Path):
    """Validate a skill directory."""
    registry = SkillRegistry()
    errors = registry.validate(path)
    if errors:
        console.print("[red]Validation failed:[/red]")
        for e in errors:
            console.print(f"  - {e}")
        raise SystemExit(1)
    console.print("[green]Skill is valid.[/green]")
