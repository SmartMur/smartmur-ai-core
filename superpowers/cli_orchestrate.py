"""Click subcommands for the orchestration runner."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.orchestrator import ORCHESTRATION_COMMANDS, Orchestrator
from superpowers.workflow.base import WorkflowError

console = Console()


def _orchestrator() -> Orchestrator:
    return Orchestrator()


@click.group("orchestrate")
def orchestrate_group():
    """Run orchestration commands (security audit, health check, etc.)."""


@orchestrate_group.command("list")
def orchestrate_list():
    """Show available orchestration commands."""
    orch = _orchestrator()
    commands = orch.list_commands()

    if not commands:
        console.print("[dim]No orchestration commands available.[/dim]")
        console.print("  Run [cyan]claw workflow init[/cyan] to install workflow templates.")
        return

    table = Table(title="Orchestration Commands")
    table.add_column("Command", style="cyan")
    table.add_column("Description")
    table.add_column("Status", style="green")

    for name, desc in sorted(commands.items()):
        table.add_row(name, desc, "ready")

    # Also show registered but missing workflows
    available_names = set(commands.keys())
    for name, desc in ORCHESTRATION_COMMANDS.items():
        if name not in available_names:
            table.add_row(name, desc, "[red]missing workflow[/red]")

    console.print(table)


@orchestrate_group.command("run")
@click.argument("command")
@click.option("--repo", "repo_path", default=None, help="Repository path to run against")
@click.option("--output", "output_dir", default=None, help="Output directory for reports")
@click.option("--dry-run", is_flag=True, help="Show what would execute without running")
def orchestrate_run(command: str, repo_path: str | None, output_dir: str | None, dry_run: bool):
    """Run an orchestration command."""
    from pathlib import Path

    kwargs = {}
    if output_dir:
        kwargs["output_dir"] = Path(output_dir)

    orch = Orchestrator(**kwargs)

    if dry_run:
        console.print(f"[bold yellow]DRY RUN:[/bold yellow] {command}")
    else:
        console.print(f"[bold]Running orchestration:[/bold] {command}")

    result = orch.run(command, repo_path=repo_path, dry_run=dry_run)

    # Display step results
    table = Table()
    table.add_column("Step", style="cyan")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Output")

    for step in result.step_details:
        status_str = step["status"]
        if status_str == "passed":
            status = "[green]PASS[/green]"
        elif status_str == "failed":
            status = "[red]FAIL[/red]"
        else:
            status = f"[dim]{status_str}[/dim]"

        duration = f"{step.get('duration_ms', 0)}ms"
        output = (step.get("output") or step.get("error") or "")[:80]
        table.add_row(step["name"], status, duration, output)

    console.print(table)

    # Summary
    console.print(
        f"\n[bold]Result:[/bold] {result.steps_passed} passed, "
        f"{result.steps_failed} failed, {result.steps_skipped} skipped "
        f"({result.total_duration_ms}ms)"
    )

    if result.report_path:
        console.print(f"[dim]Report: {result.report_path}[/dim]")

    if result.summary:
        console.print(f"\n[bold]Summary:[/bold]\n{result.summary[:500]}")

    if result.status == "error":
        console.print(f"\n[bold red]Error:[/bold red] {result.summary}")
        raise SystemExit(1)
    elif result.steps_failed > 0:
        raise SystemExit(1)


@orchestrate_group.command("info")
@click.argument("command")
def orchestrate_info(command: str):
    """Show details about an orchestration command."""
    orch = _orchestrator()
    try:
        info = orch.get_command_info(command)
    except WorkflowError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    console.print(f"[bold]{info['name']}[/bold]")
    console.print(f"  {info['description']}")
    console.print(f"  Workflow: {info['workflow_name']} — {info['workflow_description']}")

    if info["notify_profile"]:
        console.print(f"  Notify: [cyan]{info['notify_profile']}[/cyan]")

    if info["has_rollback"]:
        console.print("  [yellow]Has rollback steps[/yellow]")

    console.print()
    table = Table(title="Steps")
    table.add_column("#", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Command")
    table.add_column("On Failure")

    for i, step in enumerate(info["steps"], 1):
        table.add_row(
            str(i),
            step["name"],
            step["type"],
            step["command"][:60],
            step["on_failure"],
        )

    console.print(table)
