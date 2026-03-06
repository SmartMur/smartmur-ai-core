"""Click subcommands for LLM provider management."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("llm")
def llm_group():
    """Manage LLM providers (list, test, set-default)."""


@llm_group.command("list")
def llm_list():
    """Show registered providers and their availability status."""
    from superpowers.llm_provider import ProviderRegistry

    reg = ProviderRegistry()
    providers = reg.list_providers()

    if not providers:
        console.print("[dim]No providers configured.[/dim]")
        return

    table = Table(title="LLM Providers", show_lines=False)
    table.add_column("Provider", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Position", justify="right")

    for idx, (name, available) in enumerate(providers, 1):
        status = "[green]available[/green]" if available else "[red]unavailable[/red]"
        table.add_row(name, status, str(idx))

    console.print(table)

    chain = reg.chain
    console.print(f"\nFallback chain: [bold]{' -> '.join(chain)}[/bold]")


@llm_group.command("test")
@click.argument("provider", required=False, default=None)
@click.option("--prompt", "-p", default="Say hello in one sentence.", help="Test prompt to send.")
def llm_test(provider: str | None, prompt: str):
    """Send a test prompt to a provider and show the response."""
    from superpowers.llm_provider import ProviderRegistry

    reg = ProviderRegistry()

    try:
        p = reg.get(provider)
    except (KeyError, RuntimeError) as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    console.print(f"[dim]Provider:[/dim] {p.name}")
    console.print(f"[dim]Available:[/dim] {p.available()}")
    console.print(f"[dim]Prompt:[/dim] {prompt}")
    console.print()

    try:
        response = p.invoke(prompt)
        console.print(f"[green]Response:[/green]\n{response}")
    except (RuntimeError, FileNotFoundError, TimeoutError) as exc:
        console.print(f"[bold red]Failed:[/bold red] {exc}")
        raise SystemExit(1)


@llm_group.command("set-default")
@click.argument("provider")
def llm_set_default(provider: str):
    """Set the default LLM provider (runtime only).

    To persist, set LLM_PROVIDERS in your .env file.
    """
    import os

    from superpowers.llm_provider import ProviderRegistry, normalise_provider_name

    canonical = normalise_provider_name(provider)
    reg = ProviderRegistry()

    try:
        reg.set_default(canonical)
    except KeyError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        available = [name for name, _ in reg.list_providers()]
        console.print(f"[dim]Available providers: {', '.join(available)}[/dim]")
        raise SystemExit(1)

    # Also update the env var so child processes see it
    current = os.environ.get("LLM_PROVIDERS", "claude")
    names = [n.strip() for n in current.split(",") if n.strip()]
    if canonical in names:
        names.remove(canonical)
    names.insert(0, canonical)
    os.environ["LLM_PROVIDERS"] = ",".join(names)

    console.print(f"[green]Default provider set to:[/green] {canonical}")
    console.print(f"[dim]Updated LLM_PROVIDERS={os.environ['LLM_PROVIDERS']}[/dim]")
