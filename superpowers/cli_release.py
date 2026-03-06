"""Click subcommands for release management."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.release import MigrationChecker, ReleaseError, ReleaseManager

console = Console()


@click.group("release")
def release_group():
    """Manage releases, changelogs, and migrations."""


@release_group.command("prepare")
@click.argument("version")
def release_prepare(version: str):
    """Prepare a release: validate version, check git state, build changelog."""
    rm = ReleaseManager()
    try:
        info = rm.prepare_release(version)
    except ReleaseError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    table = Table(title=f"Release Preparation: v{version}", show_lines=False)
    table.add_column("Check", style="bold cyan")
    table.add_column("Status")

    def _status(ok: bool) -> str:
        return "[green]OK[/green]" if ok else "[red]FAIL[/red]"

    table.add_row("Git clean", _status(info["clean"]))
    table.add_row("Version match", _status(info["version_match"]))
    table.add_row("pyproject.toml version", info["pyproject_version"])
    table.add_row("Last tag", info["last_tag"])
    table.add_row("Ready", _status(info["ready"]))

    console.print(table)

    if info["changelog"]:
        console.print("\n[bold]Changelog:[/bold]")
        console.print(info["changelog"])


@release_group.command("changelog")
@click.option("--from-tag", default="", help="Starting tag (default: last tag)")
@click.option("--to-ref", default="HEAD", help="Ending ref (default: HEAD)")
def release_changelog(from_tag: str, to_ref: str):
    """Show changelog since last tag (or between specified refs)."""
    rm = ReleaseManager()
    try:
        if not from_tag:
            last = rm._get_last_tag()
            from_tag = last or ""
        changelog = rm.build_changelog(from_tag, to_ref)
    except ReleaseError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    console.print(changelog)


@release_group.command("tag")
@click.argument("version")
@click.option("-m", "--message", default="", help="Tag message")
def release_tag(version: str, message: str):
    """Create an annotated git tag for a release."""
    rm = ReleaseManager()
    try:
        tag_name = rm.create_tag(version, message)
        console.print(f"[green]Created tag:[/green] [bold]{tag_name}[/bold]")
    except ReleaseError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@release_group.command("verify")
@click.argument("version")
def release_verify(version: str):
    """Verify a release: check tag exists and version matches."""
    rm = ReleaseManager()
    try:
        info = rm.verify_release(version)
    except ReleaseError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    table = Table(title=f"Release Verification: v{version}", show_lines=False)
    table.add_column("Check", style="bold cyan")
    table.add_column("Status")

    def _status(ok: bool) -> str:
        return "[green]OK[/green]" if ok else "[red]FAIL[/red]"

    table.add_row("Tag exists", _status(info["tag_exists"]))
    table.add_row("pyproject.toml match", _status(info["pyproject_match"]))
    table.add_row("Verified", _status(info["verified"]))

    console.print(table)

    if not info["verified"]:
        raise SystemExit(1)


@release_group.command("rollback")
@click.argument("version")
def release_rollback(version: str):
    """Rollback a release: delete local tag and show instructions."""
    rm = ReleaseManager()
    try:
        info = rm.rollback_release(version)
    except ReleaseError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    if info["tag_deleted"]:
        console.print(f"[red]Deleted local tag:[/red] [bold]{info['tag']}[/bold]")
    else:
        console.print(f"[yellow]Tag {info['tag']} was not found locally.[/yellow]")

    console.print("\n[bold]Rollback instructions:[/bold]")
    console.print(info["instructions"])


@release_group.command("migrate")
@click.argument("from_ver")
@click.argument("to_ver")
def release_migrate(from_ver: str, to_ver: str):
    """Generate a migration guide between two versions."""
    mc = MigrationChecker()
    guide = mc.generate_migration_guide(from_ver, to_ver)
    console.print(guide)
