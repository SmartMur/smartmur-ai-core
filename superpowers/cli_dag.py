"""Click subcommands for DAG-based parallel execution."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.workflow.engine import WorkflowEngine
from superpowers.workflow.loader import WorkflowLoader

console = Console()


@click.group("dag")
def dag_group():
    """DAG-based parallel task execution."""


@dag_group.command("run")
@click.argument("workflow")
@click.option("--max-workers", "-w", default=4, show_default=True, help="Max parallel workers")
@click.option("--dry-run", is_flag=True, help="Show DAG without executing")
def dag_run(workflow: str, max_workers: int, dry_run: bool):
    """Run a workflow as a dependency-aware DAG.

    Parses the workflow YAML and builds a DAG from step dependencies.
    Steps without explicit depends_on are chained sequentially.
    """
    from superpowers.dag_executor import DAGError, DAGExecutor

    loader = WorkflowLoader()
    try:
        wf = loader.load(workflow)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    dag = DAGExecutor()
    engine = WorkflowEngine()

    # Build DAG nodes from workflow steps.
    # Steps are chained: each step depends on the previous one by default
    # (matching sequential workflow behavior).
    prev_id: str | None = None
    for i, step in enumerate(wf.steps):
        node_id = f"step-{i}"
        deps = [prev_id] if prev_id else []

        def _make_action(s=step):
            def _action():
                result = engine._execute_step(s, dry_run=dry_run)
                if result.status.value == "failed":
                    raise RuntimeError(result.error or result.output or "step failed")
                return result.output
            return _action

        dag.add_node(node_id, step.name, action=_make_action(), depends_on=deps)
        prev_id = node_id

    if dry_run:
        console.print(f"[bold yellow]DRY RUN:[/bold yellow] {wf.name}")
        console.print(dag.to_ascii())
        return

    console.print(f"[bold]Running DAG:[/bold] {wf.name} (workers={max_workers})")

    try:
        dag.execute(max_workers=max_workers)
    except DAGError as exc:
        console.print(f"[bold red]DAG Error:[/bold red] {exc}")
        raise SystemExit(1)

    # Display results
    table = Table()
    table.add_column("Node", style="cyan")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Result")

    for node in dag.get_results().values():
        if node.status.value == "done":
            status = "[green]DONE[/green]"
        elif node.status.value == "failed":
            status = "[red]FAIL[/red]"
        elif node.status.value == "skipped":
            status = "[dim]SKIP[/dim]"
        else:
            status = f"[dim]{node.status.value}[/dim]"

        dur = f"{node.duration_ms}ms" if node.duration_ms else ""
        output = str(node.result or node.error or "")[:80]
        table.add_row(f"{node.id}: {node.name}", status, dur, output)

    console.print(table)

    summary = dag.status_summary()
    console.print(
        f"\n[bold]Summary:[/bold] {summary['done']} done, "
        f"{summary['failed']} failed, {summary['skipped']} skipped"
    )

    if summary["failed"] > 0:
        raise SystemExit(1)


@dag_group.command("visualize")
@click.argument("workflow")
def dag_visualize(workflow: str):
    """Show ASCII visualization of a workflow as a DAG."""
    from superpowers.dag_executor import DAGExecutor

    loader = WorkflowLoader()
    try:
        wf = loader.load(workflow)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    dag = DAGExecutor()

    prev_id: str | None = None
    for i, step in enumerate(wf.steps):
        node_id = f"step-{i}"
        deps = [prev_id] if prev_id else []
        dag.add_node(node_id, step.name, action=lambda: None, depends_on=deps)
        prev_id = node_id

    console.print(f"[bold]{wf.name}[/bold] — {wf.description}\n")
    console.print(dag.to_ascii())
