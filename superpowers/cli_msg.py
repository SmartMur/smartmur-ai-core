"""Click subcommands for multi-channel messaging."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.channels.base import ChannelError
from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings
from superpowers.profiles import ProfileManager

console = Console()


def _registry() -> ChannelRegistry:
    return ChannelRegistry(Settings.load())


def _profile_manager(registry: ChannelRegistry) -> ProfileManager:
    return ProfileManager(registry)


@click.group("msg")
def msg_group():
    """Send messages via Slack, Telegram, Discord, email."""


@msg_group.command("send")
@click.argument("channel")
@click.argument("target")
@click.argument("message")
def msg_send(channel: str, target: str, message: str):
    """Send a message to a channel target.

    Examples:
      claw msg send slack "#alerts" "deploy complete"
      claw msg send telegram "123456789" "hello"
      claw msg send email "user@example.com" "Subject\\nBody here"
    """
    reg = _registry()
    try:
        ch = reg.get(channel)
    except ChannelError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    result = ch.send(target, message)
    if result.ok:
        console.print(f"[bold green]Sent[/bold green] to {channel}:{target} — {result.message}")
    else:
        console.print(f"[bold red]Failed[/bold red] {channel}:{target} — {result.error}")
        raise SystemExit(1)


@msg_group.command("test")
@click.argument("channel")
def msg_test(channel: str):
    """Test connection to a channel.

    Example: claw msg test slack
    """
    reg = _registry()
    try:
        ch = reg.get(channel)
    except ChannelError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    result = ch.test_connection()
    if result.ok:
        console.print(f"[bold green]OK[/bold green] {channel} — {result.message}")
    else:
        console.print(f"[bold red]FAIL[/bold red] {channel} — {result.error}")
        raise SystemExit(1)


@msg_group.command("channels")
def msg_channels():
    """List available channels and their credential status."""
    reg = _registry()
    available = reg.available()

    all_channels = ["slack", "telegram", "discord", "email"]
    table = Table(title="Messaging Channels")
    table.add_column("Channel", style="cyan")
    table.add_column("Status")

    for ch in all_channels:
        if ch in available:
            table.add_row(ch, "[bold green]configured[/bold green]")
        else:
            table.add_row(ch, "[dim]no credentials[/dim]")

    console.print(table)


@msg_group.command("profiles")
def msg_profiles():
    """List notification profiles."""
    reg = _registry()
    pm = _profile_manager(reg)
    profiles = pm.list_profiles()

    if not profiles:
        console.print("[dim]No profiles configured.[/dim]")
        console.print(f"  Add profiles to: ~/.claude-superpowers/profiles.yaml")
        return

    table = Table(title="Notification Profiles")
    table.add_column("Profile", style="cyan")
    table.add_column("Targets")

    for p in profiles:
        targets = ", ".join(f"{t.channel}:{t.target}" for t in p.targets)
        table.add_row(p.name, targets)

    console.print(table)


@msg_group.command("notify")
@click.argument("profile")
@click.argument("message")
def msg_notify(profile: str, message: str):
    """Send a message to all targets in a notification profile.

    Example: claw msg notify critical "PVE1 backup failed"
    """
    reg = _registry()
    pm = _profile_manager(reg)
    try:
        results = pm.send(profile, message)
    except KeyError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    for r in results:
        if r.ok:
            console.print(f"  [green]OK[/green] {r.channel}:{r.target} — {r.message}")
        else:
            console.print(f"  [red]FAIL[/red] {r.channel}:{r.target} — {r.error}")

    if all(r.ok for r in results):
        console.print(f"[bold green]All targets notified for profile '{profile}'[/bold green]")
    else:
        console.print(f"[bold yellow]Some targets failed for profile '{profile}'[/bold yellow]")
        raise SystemExit(1)
