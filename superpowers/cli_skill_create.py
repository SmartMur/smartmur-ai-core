from __future__ import annotations

import click
from rich.console import Console
from rich.tree import Tree

from superpowers.skill_creator import create_skill
from superpowers.skill_registry import SkillRegistry

console = Console()


@click.command("create")
@click.option("--name", "-n", prompt="Skill name (kebab-case)", help="Name for the new skill")
@click.option(
    "--description", "-d", prompt="Description", help="Short description of what the skill does"
)
@click.option(
    "--type",
    "script_type",
    type=click.Choice(["bash", "python"], case_sensitive=False),
    default="bash",
    prompt="Script type",
    help="bash or python",
)
@click.option("--permission", "-p", multiple=True, help="Permissions (repeatable)")
@click.option("--trigger", "-t", multiple=True, help="Triggers (repeatable)")
def skill_create(
    name: str,
    description: str,
    script_type: str,
    permission: tuple[str, ...],
    trigger: tuple[str, ...],
) -> None:
    """Scaffold a new Claude Superpowers skill."""
    permissions = list(permission) if permission else None
    triggers = list(trigger) if trigger else None

    skill_dir = create_skill(
        name=name,
        description=description,
        script_type=script_type,
        permissions=permissions,
        triggers=triggers,
    )

    # Pretty output
    tree = Tree(f"[bold green]{skill_dir.name}/[/]")
    for f in sorted(skill_dir.iterdir()):
        tree.add(f"[cyan]{f.name}[/]")
    console.print()
    console.print("[bold]Created skill:[/]")
    console.print(tree)

    # Auto-sync slash commands
    console.print()
    console.print("[dim]Syncing slash commands...[/]")
    registry = SkillRegistry()
    synced = registry.sync_slash_commands()
    if synced:
        for s in synced:
            console.print(f"  [green]linked[/] {s}")
    else:
        console.print("  [yellow]No slash_command skills to sync[/]")

    console.print()
    console.print(
        f"[bold green]Done.[/] Edit [cyan]{skill_dir / ('run.py' if script_type == 'python' else 'run.sh')}[/] to implement your skill."
    )
