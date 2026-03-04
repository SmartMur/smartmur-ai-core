"""Click subcommands for the agent registry."""

from __future__ import annotations

import subprocess

import click
from rich.console import Console
from rich.table import Table

from superpowers.agent_registry import AgentRegistry, get_agent_body
from superpowers.llm_provider import get_default_provider

console = Console()


def _registry() -> AgentRegistry:
    return AgentRegistry()


@click.group("agent")
def agent_group():
    """Discover and run subagents."""


@agent_group.command("list")
def agent_list():
    """Show all registered agents."""
    registry = _registry()
    agents = registry.discover()

    if not agents:
        console.print("[dim]No agents found.[/dim]")
        console.print("  Add agent definitions to [cyan]subagents/<name>/agent.md[/cyan]")
        return

    table = Table(title="Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Tags")
    table.add_column("Skills")

    for a in agents:
        table.add_row(
            a.name,
            a.description[:60],
            ", ".join(a.tags) if a.tags else "-",
            ", ".join(a.skills) if a.skills else "-",
        )

    console.print(table)


@agent_group.command("info")
@click.argument("name")
def agent_info(name: str):
    """Show detailed agent information."""
    registry = _registry()
    registry.discover()
    try:
        agent = registry.get(name)
    except KeyError:
        console.print(f"[red]Agent not found:[/red] {name}")
        raise SystemExit(1)

    table = Table(title=f"Agent: {agent.name}", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Name", agent.name)
    table.add_row("Description", agent.description)
    table.add_row("Tags", ", ".join(agent.tags) if agent.tags else "-")
    table.add_row("Skills", ", ".join(agent.skills) if agent.skills else "-")
    table.add_row("Triggers", ", ".join(agent.triggers) if agent.triggers else "-")
    table.add_row("Path", str(agent.path))

    console.print(table)


@agent_group.command("run")
@click.argument("name")
@click.option("--task", "-t", default=None, help="Task description to pass to the agent.")
def agent_run(name: str, task: str | None):
    """Run an agent by name, optionally with a task description."""
    registry = _registry()
    registry.discover()
    try:
        agent = registry.get(name)
    except KeyError:
        console.print(f"[red]Agent not found:[/red] {name}")
        raise SystemExit(1)

    # Build the system prompt from agent.md body
    body = get_agent_body(agent.path)
    if not body:
        console.print(f"[yellow]Warning:[/yellow] Agent '{name}' has no system prompt body.")

    prompt = body
    if task:
        prompt = f"{body}\n\n---\n\nTask: {task}"

    console.print(f"[bold]Running agent:[/bold] {agent.name}")
    if task:
        console.print(f"[dim]Task:[/dim] {task}")

    provider = get_default_provider(role="chat")
    if not provider.available():
        console.print(
            "[red]Error:[/red] No LLM provider available. "
            "Install/configure Claude CLI or set OPENAI_API_KEY for ChatGPT fallback."
        )
        raise SystemExit(1)

    try:
        result = provider.invoke(prompt).strip()
        if result:
            console.print(result)
        else:
            console.print("[yellow]Agent returned no output.[/yellow]")
    except TimeoutError:
        console.print("[red]Error:[/red] Agent timed out after 300 seconds.")
        raise SystemExit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]Error:[/red] Agent timed out.")
        raise SystemExit(1)
    except FileNotFoundError:
        console.print("[red]Error:[/red] LLM provider binary not found.")
        raise SystemExit(1)
    except RuntimeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)


@agent_group.command("recommend")
@click.argument("task")
def agent_recommend(task: str):
    """Show ranked agent recommendations for a task."""
    registry = _registry()
    registry.discover()
    recommendations = registry.recommend(task)

    if not recommendations:
        console.print("[dim]No matching agents found for this task.[/dim]")
        return

    table = Table(title="Agent Recommendations")
    table.add_column("Rank", style="dim", justify="right")
    table.add_column("Agent", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Description")
    table.add_column("Tags")

    for i, (agent, score) in enumerate(recommendations, 1):
        table.add_row(
            str(i),
            agent.name,
            str(score),
            agent.description[:50],
            ", ".join(agent.tags)[:40],
        )

    console.print(table)
