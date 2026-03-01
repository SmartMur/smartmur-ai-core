"""Click subcommands for the cron/scheduler subsystem."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from superpowers.cron_engine import CronEngine

console = Console()
OUTPUT_DIR = Path.home() / ".claude-superpowers" / "cron" / "output"


def _engine() -> CronEngine:
    return CronEngine()


def _resolve_job_id(engine: CronEngine, partial_id: str) -> str | None:
    """Resolve a partial ID to a full job ID."""
    jobs = engine.list_jobs()
    matches = [j for j in jobs if j.id.startswith(partial_id)]
    if len(matches) == 1:
        return matches[0].id
    if len(matches) > 1:
        console.print(f"[yellow]Ambiguous ID '{partial_id}' matches {len(matches)} jobs. Be more specific.[/yellow]")
        return None
    console.print(f"[red]No job found matching ID '{partial_id}'[/red]")
    return None


@click.group("cron", invoke_without_command=True)
@click.pass_context
def cron_group(ctx):
    """Manage scheduled jobs."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(cron_status)


@cron_group.command("list")
def cron_list():
    """Show all scheduled jobs."""
    engine = _engine()
    jobs = engine.list_jobs()

    if not jobs:
        console.print("[dim]No jobs configured.[/dim]")
        return

    table = Table(title="Scheduled Jobs", show_lines=False)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Name", style="bold cyan")
    table.add_column("Schedule", style="green")
    table.add_column("Type", style="magenta")
    table.add_column("Command", max_width=40)
    table.add_column("Enabled", justify="center")
    table.add_column("Last Run")
    table.add_column("Status")

    for job in jobs:
        enabled = "[green]yes[/green]" if job.enabled else "[red]no[/red]"
        last_run = job.last_run.strftime("%Y-%m-%d %H:%M") if job.last_run else "-"
        status = job.last_status or "-"
        status_styled = (
            f"[green]{status}[/green]" if status == "ok"
            else f"[red]{status}[/red]" if status and status != "-"
            else status
        )
        cmd_preview = (job.command[:37] + "...") if len(job.command) > 40 else job.command

        table.add_row(
            job.id[:8],
            job.name,
            job.schedule,
            job.job_type.value if hasattr(job.job_type, "value") else str(job.job_type),
            cmd_preview,
            enabled,
            last_run,
            status_styled,
        )

    console.print(table)


@cron_group.command("add")
@click.argument("name")
@click.argument("schedule")
@click.argument("command")
@click.option("--type", "job_type", type=click.Choice(["shell", "claude", "webhook", "skill"]), default="shell", help="Job type.")
@click.option("--output", "output_channel", default="file", help="Output channel (default: file).")
@click.option("--disabled", is_flag=True, help="Create the job in disabled state.")
def cron_add(name: str, schedule: str, command: str, job_type: str, output_channel: str, disabled: bool):
    """Add a new scheduled job.

    Examples:

      claw cron add "net-scan" "every 6h" "skill:network-scan" --type skill

      claw cron add "backup-check" "daily at 09:00" "ssh root@host 'pvesh get /cluster/backup'"
    """
    engine = _engine()
    try:
        job = engine.add_job(
            name=name,
            schedule=schedule,
            command=command,
            job_type=job_type,
            output_channel=output_channel,
            enabled=not disabled,
        )
        console.print(f"[green]Added job[/green] [bold]{job.name}[/bold] (id: [dim]{job.id[:8]}[/dim])")
        console.print(f"  Schedule: {job.schedule}")
        console.print(f"  Type:     {job.job_type.value if hasattr(job.job_type, 'value') else job.job_type}")
        console.print(f"  Command:  {job.command}")
        if disabled:
            console.print("  [yellow]Created in disabled state[/yellow]")
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@cron_group.command("remove")
@click.argument("job_id")
def cron_remove(job_id: str):
    """Remove a scheduled job (supports partial ID match)."""
    engine = _engine()
    full_id = _resolve_job_id(engine, job_id)
    if not full_id:
        raise SystemExit(1)

    try:
        job = engine.get_job(full_id)
        engine.remove_job(full_id)
        console.print(f"[red]Removed[/red] job [bold]{job.name}[/bold] ({full_id[:8]})")
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@cron_group.command("enable")
@click.argument("job_id")
def cron_enable(job_id: str):
    """Enable a disabled job."""
    engine = _engine()
    full_id = _resolve_job_id(engine, job_id)
    if not full_id:
        raise SystemExit(1)

    try:
        engine.enable_job(full_id)
        job = engine.get_job(full_id)
        console.print(f"[green]Enabled[/green] job [bold]{job.name}[/bold]")
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@cron_group.command("disable")
@click.argument("job_id")
def cron_disable(job_id: str):
    """Disable a job (keeps it configured but won't run)."""
    engine = _engine()
    full_id = _resolve_job_id(engine, job_id)
    if not full_id:
        raise SystemExit(1)

    try:
        engine.disable_job(full_id)
        job = engine.get_job(full_id)
        console.print(f"[yellow]Disabled[/yellow] job [bold]{job.name}[/bold]")
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@cron_group.command("logs")
@click.argument("job_id")
@click.option("--limit", "-n", default=5, help="Number of log files to show.")
def cron_logs(job_id: str, limit: int):
    """Show recent log output for a job."""
    engine = _engine()
    full_id = _resolve_job_id(engine, job_id)
    if not full_id:
        raise SystemExit(1)

    job = engine.get_job(full_id)
    log_dir = OUTPUT_DIR / full_id

    if not log_dir.exists():
        console.print(f"[dim]No output logs yet for job '{job.name}'[/dim]")
        return

    log_files = sorted(log_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]

    if not log_files:
        console.print(f"[dim]No output logs yet for job '{job.name}'[/dim]")
        return

    console.print(f"[bold]Logs for job:[/bold] {job.name} ({full_id[:8]})\n")

    for log_file in log_files:
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        content = log_file.read_text(errors="replace")
        header = f"{log_file.name}  ({mtime.strftime('%Y-%m-%d %H:%M:%S')})"
        console.print(Panel(
            Syntax(content, "text", theme="monokai", word_wrap=True) if content.strip() else "[dim]<empty>[/dim]",
            title=header,
            border_style="blue",
        ))


@cron_group.command("run")
@click.argument("job_id")
def cron_run(job_id: str):
    """Force-run a job immediately, bypassing its schedule."""
    engine = _engine()
    full_id = _resolve_job_id(engine, job_id)
    if not full_id:
        raise SystemExit(1)

    job = engine.get_job(full_id)
    console.print(f"[bold]Running job:[/bold] {job.name} ({full_id[:8]})")
    console.print(f"  Type:    {job.job_type.value if hasattr(job.job_type, 'value') else job.job_type}")
    console.print(f"  Command: {job.command}\n")

    try:
        result = engine.run_job(full_id)
        if result and hasattr(result, "last_status"):
            status = result.last_status
            if status == "ok":
                console.print(f"[green]Job completed successfully.[/green]")
            else:
                console.print(f"[red]Job finished with status: {status}[/red]")
            if result.last_output_file:
                output_path = Path(result.last_output_file)
                if output_path.exists():
                    content = output_path.read_text(errors="replace")
                    if content.strip():
                        console.print(Panel(content, title="Output", border_style="green"))
        else:
            console.print("[green]Job triggered.[/green]")
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@cron_group.command("status")
def cron_status():
    """Show scheduler status."""
    engine = _engine()
    jobs = engine.list_jobs()
    enabled_jobs = [j for j in jobs if j.enabled]

    running = hasattr(engine, "running") and engine.running

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Scheduler", "[green]running[/green]" if running else "[yellow]stopped[/yellow]")
    table.add_row("Total jobs", str(len(jobs)))
    table.add_row("Enabled", str(len(enabled_jobs)))
    table.add_row("Disabled", str(len(jobs) - len(enabled_jobs)))

    console.print(Panel(table, title="Cron Status", border_style="cyan"))

    if enabled_jobs:
        fire_table = Table(title="Enabled Jobs", show_lines=False)
        fire_table.add_column("ID", style="dim", width=10)
        fire_table.add_column("Name", style="bold cyan")
        fire_table.add_column("Schedule", style="green")
        fire_table.add_column("Last Run")
        fire_table.add_column("Last Status")

        for job in enabled_jobs:
            last_run = job.last_run.strftime("%Y-%m-%d %H:%M") if job.last_run else "-"
            status = job.last_status or "-"
            status_styled = (
                f"[green]{status}[/green]" if status == "ok"
                else f"[red]{status}[/red]" if status and status != "-"
                else status
            )
            fire_table.add_row(job.id[:8], job.name, job.schedule, last_run, status_styled)

        console.print(fire_table)
