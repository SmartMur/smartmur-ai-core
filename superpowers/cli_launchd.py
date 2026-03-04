"""Click subcommands for `claw daemon` service management."""

from __future__ import annotations

import subprocess
import sys

import click
from rich.console import Console
from rich.table import Table

from superpowers.launchd import (
    LOG_DIR,
    install_cron_daemon,
    service_backend,
    service_label,
    service_status,
    uninstall_plist,
)

console = Console()
SERVICE_NAME = "claude-superpowers-cron"


@click.group()
def daemon():
    """Manage the cron daemon service."""


@daemon.command()
def install():
    """Install and start the daemon service."""
    try:
        path = install_cron_daemon()
        console.print(f"[green]Installed and loaded:[/green] {path}")
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]{service_backend()} command failed:[/red] {e}")
        sys.exit(1)


@daemon.command()
def uninstall():
    """Stop and remove the daemon service definition."""
    try:
        uninstall_plist(SERVICE_NAME)
        console.print("[green]Daemon uninstalled.[/green]")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, RuntimeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@daemon.command()
def status():
    """Show daemon status (PID, running state)."""
    info = service_status(SERVICE_NAME)

    table = Table(title="Cron Daemon Status")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Backend", service_backend())
    table.add_row("Service", service_label(SERVICE_NAME))
    table.add_row(
        "Running",
        "[green]Yes[/green]" if info["running"] else "[red]No[/red]",
    )
    table.add_row("PID", str(info["pid"]) if info["pid"] else "-")
    table.add_row(
        "Last Exit Code",
        str(info["exit_code"]) if info["exit_code"] is not None else "-",
    )
    console.print(table)


@daemon.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output (tail -f).")
@click.option("--lines", "-n", default=50, help="Number of lines to show.")
def logs(follow: bool, lines: int):
    """Tail the daemon log file."""
    log_file = LOG_DIR / "cron-daemon.log"
    if not log_file.exists():
        console.print(f"[yellow]Log file not found:[/yellow] {log_file}")
        sys.exit(1)

    if follow:
        console.print(f"[dim]Following {log_file} (Ctrl+C to stop)...[/dim]")
        try:
            subprocess.run(["tail", "-f", "-n", str(lines), str(log_file)])
        except KeyboardInterrupt:
            pass
    else:
        result = subprocess.run(
            ["tail", "-n", str(lines), str(log_file)],
            capture_output=True,
            text=True,
        )
        console.print(result.stdout, highlight=False)
