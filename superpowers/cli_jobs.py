"""Click subcommands for the job orchestration engine."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _runner(repo_dir: str | None = None):
    from superpowers.job_runner import JobRunner

    return JobRunner(repo_dir=repo_dir)


@click.group("jobs")
def jobs_group():
    """Git-branch job orchestration."""


@jobs_group.command("list")
@click.option("--repo", default=None, help="Repository path (default: cwd)")
def jobs_list(repo: str | None):
    """List all job branches."""
    runner = _runner(repo)
    branches = runner.list_job_branches()

    if not branches:
        console.print("[dim]No job branches found.[/dim]")
        return

    table = Table(title="Job Branches")
    table.add_column("ID", style="cyan")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("SHA", style="dim")

    for b in branches:
        status_style = {
            "completed": "green",
            "merged": "bold green",
            "failed": "red",
            "running": "yellow",
        }.get(b["status"], "dim")
        table.add_row(
            b["job_id"],
            b["branch"],
            f"[{status_style}]{b['status']}[/{status_style}]",
            b["sha"],
        )

    console.print(table)


@jobs_group.command("run")
@click.argument("name")
@click.option("--command", "-c", required=True, help="Shell command to execute")
@click.option("--repo", default=None, help="Repository path (default: cwd)")
@click.option("--pr", is_flag=True, help="Create a PR after execution")
@click.option("--auto-merge", is_flag=True, help="Auto-merge if files are in allowed paths")
def jobs_run(name: str, command: str, repo: str | None, pr: bool, auto_merge: bool):
    """Run a command on a dedicated job branch."""
    runner = _runner(repo)
    result = runner.run(name=name, command=command)

    if result.status.value == "completed":
        console.print(f"[green]Job completed:[/green] {result.job_id}")
        if result.changed_files:
            console.print(f"  Changed files: {len(result.changed_files)}")
            for f in result.changed_files:
                console.print(f"    - {f}")
        if result.commit_sha:
            console.print(f"  Commit: {result.commit_sha[:8]}")
    else:
        console.print(f"[red]Job failed:[/red] {result.job_id}")
        if result.error:
            console.print(f"  Error: {result.error[:200]}")

    if pr and result.status.value == "completed":
        result = runner.create_pr(result)
        console.print(f"  PR: {result.pr_url}")

    if auto_merge and result.status.value == "completed":
        if runner.can_auto_merge(result):
            result = runner.auto_merge(result)
            console.print("  [bold green]Auto-merged![/bold green]")
        else:
            console.print("  [yellow]Auto-merge blocked: files outside allowed paths[/yellow]")
