"""Click subcommands for the policy engine."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.policy_engine import PolicyAction, PolicyEngine

console = Console()


def _get_engine() -> PolicyEngine:
    return PolicyEngine.from_data_dir()


@click.group("policy")
def policy_group():
    """Manage orchestration safety policies."""


@policy_group.command("list")
def policy_list():
    """Show all active policies and their rules."""
    engine = _get_engine()
    policies = engine.get_policies()

    if not policies:
        console.print("[dim]No policies loaded.[/dim]")
        return

    for policy in policies:
        console.print(f"\n[bold cyan]{policy.name}[/bold cyan]", end="")
        if policy.description:
            console.print(f"  [dim]{policy.description}[/dim]")
        else:
            console.print()

        if not policy.rules:
            console.print("  [dim]  (no rules)[/dim]")
            continue

        table = Table(show_header=True, show_lines=False, pad_edge=False, box=None)
        table.add_column("#", style="dim", width=4)
        table.add_column("Action", width=18)
        table.add_column("Pattern", style="cyan")
        table.add_column("Description")

        style_map = {
            PolicyAction.allow: "green",
            PolicyAction.deny: "bold red",
            PolicyAction.require_approval: "yellow",
        }

        for i, rule in enumerate(policy.rules, 1):
            action_style = style_map.get(rule.action, "white")
            pattern = rule.command_pattern or rule.resource_pattern or "(secret detection)"
            table.add_row(
                str(i),
                f"[{action_style}]{rule.action.value}[/{action_style}]",
                pattern[:60],
                rule.description,
            )

        console.print(table)

    console.print(f"\n[dim]Total: {len(policies)} policies[/dim]")


@policy_group.command("check")
@click.argument("command")
def policy_check(command: str):
    """Test a command against all policies."""
    engine = _get_engine()
    decision = engine.check_command(command)

    style_map = {
        PolicyAction.allow: "green",
        PolicyAction.deny: "bold red",
        PolicyAction.require_approval: "yellow",
    }
    style = style_map.get(decision.action, "white")

    console.print(f"Command: [bold]{command}[/bold]")
    console.print(f"Decision: [{style}]{decision.action.value}[/{style}]")
    console.print(f"Reason: {decision.reason}")
    if decision.policy_name:
        console.print(f"Policy: [cyan]{decision.policy_name}[/cyan]")

    if decision.action == PolicyAction.deny:
        raise SystemExit(1)


@policy_group.command("check-file")
@click.argument("path")
def policy_check_file(path: str):
    """Test a file path against file access policies."""
    engine = _get_engine()
    decision = engine.check_file_access(path)

    style_map = {
        PolicyAction.allow: "green",
        PolicyAction.deny: "bold red",
        PolicyAction.require_approval: "yellow",
    }
    style = style_map.get(decision.action, "white")

    console.print(f"Path: [bold]{path}[/bold]")
    console.print(f"Decision: [{style}]{decision.action.value}[/{style}]")
    console.print(f"Reason: {decision.reason}")
    if decision.policy_name:
        console.print(f"Policy: [cyan]{decision.policy_name}[/cyan]")

    if decision.action == PolicyAction.deny:
        raise SystemExit(1)


@policy_group.command("test-output")
@click.argument("text")
def policy_test_output(text: str):
    """Test text for secret leaks."""
    engine = _get_engine()
    has_secrets, redacted = engine.check_output(text)

    if has_secrets:
        console.print("[bold red]Secrets detected![/bold red]")
        console.print(f"Redacted output:\n{redacted}")
        raise SystemExit(1)
    else:
        console.print("[green]No secrets detected.[/green]")
        console.print(f"Output:\n{text}")
