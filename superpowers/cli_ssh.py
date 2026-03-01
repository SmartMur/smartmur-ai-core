"""Click subcommands for SSH fabric — remote execution, health checks, Home Assistant."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.config import Settings
from superpowers.ssh_fabric.base import SSHError
from superpowers.ssh_fabric.hosts import HostRegistry
from superpowers.ssh_fabric.pool import ConnectionPool
from superpowers.ssh_fabric.executor import SSHExecutor
from superpowers.ssh_fabric.health import HealthChecker
from superpowers.ssh_fabric.homeassistant import HomeAssistantClient

console = Console()


def _build_stack() -> tuple[HostRegistry, ConnectionPool, SSHExecutor]:
    settings = Settings.load()
    settings.ensure_dirs()
    hosts = HostRegistry()

    vault = None
    try:
        from superpowers.vault import Vault

        vault = Vault(settings.vault_identity_file)
    except Exception:
        pass

    pool = ConnectionPool(hosts, vault=vault)
    executor = SSHExecutor(pool, hosts)
    return hosts, pool, executor


def _ha_client() -> HomeAssistantClient:
    settings = Settings.load()
    if not settings.home_assistant_url or not settings.home_assistant_token:
        raise SSHError(
            "HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN must be set in .env"
        )
    return HomeAssistantClient(settings.home_assistant_url, settings.home_assistant_token)


@click.group("ssh")
def ssh_group():
    """Execute commands on remote hosts, health checks, Home Assistant."""


@ssh_group.command("hosts")
def ssh_hosts():
    """List configured SSH hosts."""
    hosts = HostRegistry()
    host_list = hosts.list_hosts()

    if not host_list:
        console.print("[dim]No hosts configured.[/dim]")
        console.print(f"  Add hosts to: ~/.claude-superpowers/hosts.yaml")
        return

    table = Table(title="SSH Hosts")
    table.add_column("Alias", style="cyan")
    table.add_column("Hostname")
    table.add_column("Username")
    table.add_column("Auth")
    table.add_column("Groups")

    for h in host_list:
        table.add_row(
            h.alias,
            f"{h.hostname}:{h.port}" if h.port != 22 else h.hostname,
            h.username,
            h.auth.value,
            ", ".join(h.groups),
        )

    console.print(table)


@ssh_group.command("run")
@click.argument("target")
@click.argument("command")
@click.option("--timeout", "-t", default=30, help="Command timeout in seconds.")
def ssh_run(target: str, command: str, timeout: int):
    """Run a command on one or more hosts.

    TARGET is a host alias or group name.

    Examples:
      claw ssh run proxmox1 "qm list"
      claw ssh run docker "docker ps"
      claw ssh run all "uptime"
    """
    hosts, pool, executor = _build_stack()

    try:
        hosts.resolve(target)
    except SSHError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    with pool:
        results = executor.run(target, command, timeout=timeout)

    table = Table(title=f"Results: {command}")
    table.add_column("Host", style="cyan")
    table.add_column("Exit", justify="right")
    table.add_column("Output")

    any_failed = False
    for r in results:
        if r.ok:
            status = f"[green]{r.exit_code}[/green]"
        else:
            status = f"[red]{r.exit_code}[/red]"
            any_failed = True

        output = r.stdout.strip() if r.ok else (r.error or r.stderr.strip())
        table.add_row(r.host, status, output)

    console.print(table)

    if any_failed:
        raise SystemExit(1)


@ssh_group.command("test")
@click.argument("target")
def ssh_test(target: str):
    """Test SSH connectivity to one or more hosts.

    TARGET is a host alias or group name.

    Examples:
      claw ssh test proxmox1
      claw ssh test all
    """
    hosts, pool, executor = _build_stack()

    try:
        hosts.resolve(target)
    except SSHError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    with pool:
        results = executor.run(target, "echo ok", timeout=10)

    any_failed = False
    for r in results:
        if r.ok and r.stdout.strip() == "ok":
            console.print(f"  [green]PASS[/green] {r.host}")
        else:
            error = r.error or r.stderr.strip() or "no response"
            console.print(f"  [red]FAIL[/red] {r.host} — {error}")
            any_failed = True

    if any_failed:
        console.print("[bold red]Some hosts failed connectivity test[/bold red]")
        raise SystemExit(1)
    else:
        console.print("[bold green]All hosts passed[/bold green]")


@ssh_group.command("health")
@click.option("--json-path", default=None, help="Override JSON output path.")
def ssh_health(json_path: str | None):
    """Run health checks on all hosts — ping + SSH + uptime.

    Writes results to ~/.claude-superpowers/ssh/health.json
    """
    from pathlib import Path

    hosts, pool, executor = _build_stack()
    output_path = Path(json_path) if json_path else None
    checker = HealthChecker(hosts, executor, output_path=output_path)

    with pool:
        report = checker.check_all()

    table = Table(title="Host Health")
    table.add_column("Host", style="cyan")
    table.add_column("Ping")
    table.add_column("SSH")
    table.add_column("Latency (ms)", justify="right")
    table.add_column("Load Avg")
    table.add_column("Error")

    for h in report.hosts:
        ping = "[green]OK[/green]" if h.ping_ok else "[red]FAIL[/red]"
        ssh = "[green]OK[/green]" if h.ssh_ok else "[red]FAIL[/red]"
        table.add_row(
            h.alias,
            ping,
            ssh,
            f"{h.latency_ms:.1f}",
            h.load_avg or "-",
            h.error or "",
        )

    console.print(table)

    checker.write_json(report)
    console.print(f"[dim]Written to {checker._output_path}[/dim]")

    if not report.all_ok:
        raise SystemExit(1)


# --- Home Assistant subgroup ---


@ssh_group.group("ha")
def ha_group():
    """Home Assistant controls."""


@ha_group.command("state")
@click.argument("entity_id")
def ha_state(entity_id: str):
    """Get the state of a Home Assistant entity.

    Example: claw ssh ha state light.office
    """
    try:
        client = _ha_client()
        state = client.get_state(entity_id)
    except SSHError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    if not state:
        console.print(f"[bold red]Error:[/bold red] Entity not found: {entity_id}")
        raise SystemExit(1)

    console.print(f"[cyan]{entity_id}[/cyan]: [bold]{state.get('state', 'unknown')}[/bold]")

    attrs = state.get("attributes", {})
    if attrs:
        table = Table(title="Attributes")
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        for k, v in attrs.items():
            table.add_row(str(k), str(v))
        console.print(table)


@ha_group.command("call")
@click.argument("domain")
@click.argument("service")
@click.argument("entity_id")
def ha_call(domain: str, service: str, entity_id: str):
    """Call a Home Assistant service.

    Examples:
      claw ssh ha call light turn_on light.office
      claw ssh ha call climate set_temperature climate.living_room
    """
    try:
        client = _ha_client()
        result = client.call_service(domain, service, entity_id)
    except SSHError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    console.print(f"[bold green]OK[/bold green] {domain}.{service} -> {entity_id}")


@ha_group.command("list")
@click.option("--filter", "-f", "filter_str", default=None, help="Filter entities by prefix (e.g. 'light', 'switch').")
def ha_list(filter_str: str | None):
    """List Home Assistant entities.

    Examples:
      claw ssh ha list
      claw ssh ha list --filter light
    """
    try:
        client = _ha_client()
        states = client.get_states()
    except SSHError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)

    if filter_str:
        states = [s for s in states if s.get("entity_id", "").startswith(filter_str)]

    if not states:
        console.print("[dim]No entities found.[/dim]")
        return

    table = Table(title="Home Assistant Entities")
    table.add_column("Entity ID", style="cyan")
    table.add_column("State")
    table.add_column("Name")

    for s in sorted(states, key=lambda x: x.get("entity_id", "")):
        entity_id = s.get("entity_id", "")
        state_val = s.get("state", "unknown")
        name = s.get("attributes", {}).get("friendly_name", "")
        table.add_row(entity_id, state_val, name)

    console.print(table)
    console.print(f"[dim]{len(states)} entities[/dim]")
