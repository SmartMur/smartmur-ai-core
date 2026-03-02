"""Click subcommands for the workflow engine."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.workflow.base import StepStatus, WorkflowError
from superpowers.workflow.builtins import install_builtins
from superpowers.workflow.engine import WorkflowEngine
from superpowers.workflow.loader import WorkflowLoader

console = Console()


def _loader() -> WorkflowLoader:
    return WorkflowLoader()


@click.group("workflow")
def workflow_group():
    """Run multi-step workflows."""


@workflow_group.command("list")
def workflow_list():
    """List available workflows."""
    loader = _loader()
    names = loader.list_workflows()
    if not names:
        console.print("[dim]No workflows found.[/dim]")
        console.print("  Run [cyan]claw workflow init[/cyan] to install built-in templates.")
        return

    table = Table(title="Workflows")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for name in names:
        try:
            wf = loader.load(name)
            table.add_row(name, wf.description)
        except WorkflowError:
            table.add_row(name, "[red]error loading[/red]")

    console.print(table)


@workflow_group.command("show")
@click.argument("name")
def workflow_show(name: str):
    """Show workflow steps."""
    loader = _loader()
    try:
        wf = loader.load(name)
    except WorkflowError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    console.print(f"[bold]{wf.name}[/bold] — {wf.description}")
    table = Table()
    table.add_column("#", style="dim")
    table.add_column("Step", style="cyan")
    table.add_column("Type")
    table.add_column("Command")
    table.add_column("On Failure")

    for i, step in enumerate(wf.steps, 1):
        table.add_row(str(i), step.name, step.type.value, step.command[:60], step.on_failure)

    console.print(table)

    if wf.rollback_steps:
        console.print("\n[bold yellow]Rollback steps:[/bold yellow]")
        for step in wf.rollback_steps:
            console.print(f"  - {step.name}: {step.command[:60]}")

    if wf.notify_profile:
        console.print(f"\nNotify: [cyan]{wf.notify_profile}[/cyan]")


@workflow_group.command("run")
@click.argument("name")
@click.option("--dry-run", is_flag=True, help="Show what would execute without running")
def workflow_run(name: str, dry_run: bool):
    """Execute a workflow."""
    loader = _loader()
    try:
        wf = loader.load(name)
    except WorkflowError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    if dry_run:
        console.print(f"[bold yellow]DRY RUN:[/bold yellow] {wf.name}")
    else:
        console.print(f"[bold]Running:[/bold] {wf.name}")

    engine = WorkflowEngine()
    results = engine.run(wf, dry_run=dry_run)

    table = Table()
    table.add_column("Step", style="cyan")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Output")

    for r in results:
        if r.status == StepStatus.passed:
            status = "[green]PASS[/green]"
        elif r.status == StepStatus.failed:
            status = "[red]FAIL[/red]"
        else:
            status = f"[dim]{r.status.value}[/dim]"

        duration = f"{r.duration_ms}ms" if r.duration_ms else ""
        output = (r.output or r.error)[:80]
        table.add_row(r.step_name, status, duration, output)

    console.print(table)

    passed = sum(1 for r in results if r.status == StepStatus.passed)
    failed = sum(1 for r in results if r.status == StepStatus.failed)

    if failed:
        console.print(f"\n[bold red]{failed} failed[/bold red], {passed} passed")
        raise SystemExit(1)
    else:
        console.print(f"\n[bold green]All {passed} steps passed[/bold green]")


@workflow_group.command("validate")
@click.argument("name")
def workflow_validate(name: str):
    """Validate a workflow definition."""
    loader = _loader()
    try:
        wf = loader.load(name)
    except WorkflowError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    errors = loader.validate(wf)
    if errors:
        console.print(f"[bold red]Validation errors in '{name}':[/bold red]")
        for e in errors:
            console.print(f"  - {e}")
        raise SystemExit(1)
    else:
        console.print(f"[bold green]Workflow '{name}' is valid.[/bold green]")


@workflow_group.command("init")
def workflow_init():
    """Install built-in workflow templates."""
    from superpowers.config import get_data_dir
    workflows_dir = get_data_dir() / "workflows"
    created = install_builtins(workflows_dir)
    if created:
        for name in created:
            console.print(f"  [green]Created[/green] {name}.yaml")
        console.print(f"\nWorkflows installed to: {workflows_dir}")
    else:
        console.print("[dim]All built-in workflows already exist.[/dim]")
