"""Click subcommands for the encrypted vault."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.vault import Vault, VaultError

console = Console()


@click.group("vault")
def vault_group():
    """Manage encrypted secrets."""


@vault_group.command("init")
def vault_init():
    """Initialize vault and generate age keypair."""
    v = Vault()
    try:
        pubkey = v.init()
        console.print(f"[bold green]Vault initialized.[/bold green]")
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
