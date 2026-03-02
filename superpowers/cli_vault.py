"""Click subcommands for the encrypted vault."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.vault import Vault, VaultError

console = Console()


# --- Rotation subgroup ---

@click.group("rotation")
def rotation_group():
    """Credential rotation alerts."""


@rotation_group.command("check")
def rotation_check():
    """Run rotation check now and print results."""
    from superpowers.credential_rotation import (
        AlertStatus,
        CredentialRotationChecker,
    )

    v = Vault()
    try:
        keys = v.list_keys()
    except VaultError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    if not keys:
        console.print("[dim]Vault is empty — nothing to check.[/dim]")
        return

    checker = CredentialRotationChecker()
    alerts = checker.check_all(keys)

    style_map = {
        AlertStatus.ok: "green",
        AlertStatus.warning: "yellow",
        AlertStatus.expired: "bold red",
    }

    table = Table(title="Credential Rotation Status", show_lines=False)
    table.add_column("Key", style="cyan")
    table.add_column("Age (days)", justify="right")
    table.add_column("Max (days)", justify="right")
    table.add_column("Status")

    for a in alerts:
        age_str = str(a.age_days) if a.age_days >= 0 else "unknown"
        style = style_map.get(a.status, "white")
        table.add_row(a.key, age_str, str(a.max_age_days), f"[{style}]{a.status.value}[/{style}]")

    console.print(table)


@rotation_group.group("policy")
def rotation_policy():
    """Manage rotation policies."""


@rotation_policy.command("set")
@click.argument("key")
@click.argument("days", type=int)
def rotation_policy_set(key: str, days: int):
    """Set rotation policy for a vault key."""
    from superpowers.credential_rotation import CredentialRotationChecker

    if days < 1:
        console.print("[bold red]Error:[/bold red] days must be >= 1")
        raise SystemExit(1)
    checker = CredentialRotationChecker()
    checker.set_policy(key, days)
    console.print(f"[green]Policy set:[/green] [bold]{key}[/bold] = {days} days")


@rotation_policy.command("list")
def rotation_policy_list():
    """List all rotation policies."""
    from superpowers.credential_rotation import CredentialRotationChecker

    checker = CredentialRotationChecker()
    policies = checker.list_policies()

    if not policies:
        console.print("[dim]No rotation policies configured.[/dim]")
        return

    table = Table(title="Rotation Policies", show_lines=False)
    table.add_column("Key", style="cyan")
    table.add_column("Max Age (days)", justify="right")
    table.add_column("Last Rotated")

    for key, p in sorted(policies.items()):
        last = p.last_rotated if p.last_rotated else "[dim]never[/dim]"
        table.add_row(key, str(p.max_age_days), last)

    console.print(table)


@click.group("vault")
def vault_group():
    """Manage encrypted secrets."""


vault_group.add_command(rotation_group)


@vault_group.command("init")
def vault_init():
    """Initialize vault and generate age keypair."""
    v = Vault()
    try:
        pubkey = v.init()
        console.print("[bold green]Vault initialized.[/bold green]")
        console.print(f"  Identity: {v.identity_file}")
        console.print(f"  Vault:    {v.vault_path}")
        console.print(f"  Public key: [cyan]{pubkey}[/cyan]")
    except VaultError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@vault_group.command("set")
@click.argument("key")
@click.argument("value")
def vault_set(key: str, value: str):
    """Store a credential in the vault."""
    v = Vault()
    try:
        v.set(key, value)
        console.print(f"[green]Set[/green] [bold]{key}[/bold]")
    except VaultError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@vault_group.command("get")
@click.argument("key")
@click.option("--reveal", is_flag=True, help="Show the actual value instead of masked.")
def vault_get(key: str, reveal: bool):
    """Retrieve a credential from the vault."""
    v = Vault()
    try:
        value = v.get(key)
        if value is None:
            console.print(f"[yellow]Key not found:[/yellow] {key}")
            raise SystemExit(1)
        if reveal:
            console.print(value)
        else:
            masked = value[:2] + "*" * (len(value) - 4) + value[-2:] if len(value) > 4 else "****"
            console.print(f"[bold]{key}[/bold] = {masked}")
    except VaultError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@vault_group.command("list")
def vault_list():
    """List all keys in the vault."""
    v = Vault()
    try:
        keys = v.list_keys()
        if not keys:
            console.print("[dim]Vault is empty.[/dim]")
            return
        table = Table(title="Vault Keys", show_lines=False)
        table.add_column("#", style="dim", width=4)
        table.add_column("Key", style="bold cyan")
        for i, k in enumerate(keys, 1):
            table.add_row(str(i), k)
        console.print(table)
    except VaultError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@vault_group.command("delete")
@click.argument("key")
def vault_delete(key: str):
    """Remove a credential from the vault."""
    v = Vault()
    try:
        v.delete(key)
        console.print(f"[red]Deleted[/red] [bold]{key}[/bold]")
    except VaultError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)
