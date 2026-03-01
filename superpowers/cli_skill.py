from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from superpowers.auto_install import (
    BUILTIN_TEMPLATES,
    check_and_install,
    install_from_template,
    suggest_skill,
)
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


@click.command("link")
def skill_link():
    """Regenerate all slash command symlinks."""
    registry = SkillRegistry()
    registry.discover()
    created = registry.sync_slash_commands()
    console.print(f"[green]Synced {len(created)} slash command(s)[/green]")
    for path in created:
        console.print(f"  {path} -> {path.resolve()}")


# --- SkillHub sync subgroup ---

@click.group("sync")
def skill_sync():
    """Sync skills with the SkillHub repo."""


@skill_sync.command("push")
@click.argument("name")
def sync_push(name: str):
    """Push a local skill to SkillHub."""
    from superpowers.skillhub import SkillHub

    hub = SkillHub()
    result = hub.push(name)
    if result.action == "error":
        console.print(f"[red]Error:[/red] {result.message}")
        raise SystemExit(1)
    elif result.action == "up-to-date":
        console.print(f"[yellow]{name}[/yellow] is already up to date.")
    else:
        console.print(f"[green]Pushed[/green] {name} to SkillHub.")


@skill_sync.command("pull")
@click.argument("name", required=False, default=None)
def sync_pull(name: str | None):
    """Pull skill(s) from SkillHub. Omit name to pull all."""
    from superpowers.skillhub import SkillHub

    hub = SkillHub()
    results = hub.pull(name)
    for r in results:
        if r.action == "error":
            console.print(f"[red]{r.skill_name}:[/red] {r.message}")
        else:
            console.print(f"[green]Pulled[/green] {r.skill_name}")
    errors = [r for r in results if r.action == "error"]
    if errors:
        raise SystemExit(1)


@skill_sync.command("list")
def sync_list():
    """List skills available in SkillHub."""
    from superpowers.skillhub import SkillHub

    hub = SkillHub()
    skills = hub.list_remote()
    if not skills:
        console.print("[yellow]No skills found in SkillHub.[/yellow]")
        return

    table = Table(title="SkillHub")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Description")
    for s in skills:
        table.add_row(s["name"], s["version"], s["description"])
    console.print(table)


@skill_sync.command("diff")
@click.argument("name")
def sync_diff(name: str):
    """Show diff between local and SkillHub version of a skill."""
    from superpowers.skillhub import SkillHub

    hub = SkillHub()
    output = hub.diff(name)
    console.print(output)


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


@click.command("auto-install")
@click.argument("description")
@click.option("--template", "-t", default=None, help="Install from a built-in template instead of matching.")
@click.option("--dry-run", is_flag=True, help="Show what would be installed without doing it.")
def skill_auto_install(description: str, template: str | None, dry_run: bool):
    """Auto-create and install a skill from a description or template."""
    if dry_run:
        suggestion = suggest_skill(description)
        console.print("[bold]Suggested skill:[/bold]")
        console.print(f"  Name:        {suggestion['name']}")
        console.print(f"  Description: {suggestion['description']}")
        console.print(f"  Tags:        {', '.join(suggestion['tags'])}")
        console.print(f"  Script type: {suggestion['script_type']}")
        if suggestion.get("template"):
            console.print(f"  Template:    {suggestion['template']}")
        else:
            console.print("  Template:    (none -- will scaffold generic skill)")
        return

    if template:
        try:
            name = install_from_template(template)
            console.print(f"[green]Installed template:[/green] {name}")
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)
        return

    name = check_and_install(description)
    if name:
        console.print(f"[green]Skill ready:[/green] {name}")
    else:
        console.print("[red]Could not create a skill from that description.[/red]")
        raise SystemExit(1)
