"""Click command for the /status dashboard."""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel

from superpowers.config import get_data_dir

console = Console()


@click.command("status")
def status_dashboard():
    """Show system status across all subsystems."""
    sections: list[str] = []

    # --- Cron ---
    try:
        from superpowers.cron_engine import CronEngine

        engine = CronEngine()
        jobs = engine.list_jobs()
        total = len(jobs)
        enabled = sum(1 for j in jobs if j.enabled)
        sections.append(f"[cyan]Cron:[/cyan] {total} jobs ({enabled} enabled)")
    except Exception:
        sections.append("[cyan]Cron:[/cyan] [dim]unavailable[/dim]")

    # --- Channels ---
    try:
        from superpowers.channels.registry import ChannelRegistry
        from superpowers.config import Settings

        settings = Settings.load()
        registry = ChannelRegistry(settings)
        available = registry.available()
        if available:
            sections.append(f"[cyan]Channels:[/cyan] {', '.join(available)}")
        else:
            sections.append("[cyan]Channels:[/cyan] [dim]none configured[/dim]")
    except Exception:
        sections.append("[cyan]Channels:[/cyan] [dim]unavailable[/dim]")

    # --- Watchers ---
    try:
        from superpowers.watcher.engine import WatcherEngine

        we = WatcherEngine()
        rules = we.list_rules()
        enabled_rules = sum(1 for r in rules if r.enabled)
        sections.append(f"[cyan]Watchers:[/cyan] {len(rules)} rules ({enabled_rules} enabled)")
    except Exception:
        sections.append("[cyan]Watchers:[/cyan] [dim]unavailable[/dim]")

    # --- Skills ---
    try:
        from superpowers.skill_registry import SkillRegistry

        sr = SkillRegistry()
        skills = sr.list()
        sections.append(f"[cyan]Skills:[/cyan] {len(skills)} installed")
    except Exception:
        sections.append("[cyan]Skills:[/cyan] [dim]unavailable[/dim]")

    # --- Vault ---
    try:
        data_dir = get_data_dir()
        vault_file = data_dir / "vault.enc"
        if vault_file.exists():
            sections.append("[cyan]Vault:[/cyan] [green]initialized[/green]")
        else:
            sections.append("[cyan]Vault:[/cyan] [dim]not initialized[/dim]")
    except Exception:
        sections.append("[cyan]Vault:[/cyan] [dim]unavailable[/dim]")

    # --- Memory ---
    try:
        memory_db = get_data_dir() / "memory.db"
        if memory_db.exists():
            sections.append("[cyan]Memory:[/cyan] [green]active[/green]")
        else:
            sections.append("[cyan]Memory:[/cyan] [dim]not initialized[/dim]")
    except Exception:
        sections.append("[cyan]Memory:[/cyan] [dim]unavailable[/dim]")

    # --- Audit ---
    try:
        from superpowers.audit import AuditLog

        audit = AuditLog()
        recent = audit.tail(5)
        if recent:
            audit_lines = []
            for entry in recent:
                ts = entry.get("ts", "?")[:19]
                action = entry.get("action", "?")
                detail = entry.get("detail", "")[:40]
                audit_lines.append(f"  {ts}  {action}  {detail}")
            sections.append("[cyan]Audit (last 5):[/cyan]\n" + "\n".join(audit_lines))
        else:
            sections.append("[cyan]Audit:[/cyan] [dim]no entries[/dim]")
    except Exception:
        sections.append("[cyan]Audit:[/cyan] [dim]unavailable[/dim]")

    panel = Panel(
        "\n".join(sections),
        title="[bold]claude-superpowers status[/bold]",
        border_style="blue",
        padding=(1, 2),
    )
    console.print(panel)
