from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def ssh_run(target: str, command: str) -> str:
        """Execute a command on an SSH host or host group.

        Args:
            target: Host alias or group name (e.g. "proxmox", "all", "webservers").
            command: Shell command to execute remotely.
        """
        try:
            from superpowers.config import Settings
            from superpowers.ssh_fabric.executor import SSHExecutor
            from superpowers.ssh_fabric.hosts import HostRegistry
            from superpowers.ssh_fabric.pool import ConnectionPool

            Settings.load()  # ensure env is loaded
            hosts = HostRegistry()
            with ConnectionPool(hosts) as pool:
                executor = SSHExecutor(pool, hosts)
                results = executor.run(target, command)

            lines = []
            for r in results:
                header = f"[{r.host}] exit={r.exit_code}"
                if r.error:
                    header += f" error={r.error}"
                lines.append(header)
                if r.stdout.strip():
                    lines.append(r.stdout.rstrip())
                if r.stderr.strip():
                    lines.append(f"STDERR: {r.stderr.rstrip()}")
                lines.append("")
            return "\n".join(lines).rstrip() or "No output."
        except (ImportError, OSError, RuntimeError, KeyError, ValueError) as exc:
            return f"Error running SSH command: {exc}"

    @mcp.tool()
    def ssh_list_hosts() -> str:
        """List all configured SSH hosts with connection details."""
        try:
            from superpowers.ssh_fabric.hosts import HostRegistry

            hosts = HostRegistry()
            host_list = hosts.list_hosts()
            if not host_list:
                return "No hosts configured. Create ~/.claude-superpowers/hosts.yaml."

            lines = []
            for h in host_list:
                groups_str = ", ".join(g for g in h.groups if g != "all")
                line = f"  {h.alias}: {h.username}@{h.hostname}:{h.port} auth={h.auth.value}"
                if groups_str:
                    line += f" groups=[{groups_str}]"
                if h.tags:
                    tags = ", ".join(f"{k}={v}" for k, v in h.tags.items())
                    line += f" tags=[{tags}]"
                lines.append(line)
            return f"SSH hosts ({len(host_list)}):\n" + "\n".join(lines)
        except (ImportError, OSError, ValueError) as exc:
            return f"Error listing hosts: {exc}"

    @mcp.tool()
    def ssh_list_groups() -> str:
        """List SSH host groups and their members."""
        try:
            from superpowers.ssh_fabric.hosts import HostRegistry

            hosts = HostRegistry()
            groups = hosts.groups()
            if not groups:
                return "No host groups found."

            lines = []
            for group, members in sorted(groups.items()):
                lines.append(f"  {group}: {', '.join(members)}")
            return f"Host groups ({len(groups)}):\n" + "\n".join(lines)
        except (ImportError, OSError, ValueError) as exc:
            return f"Error listing groups: {exc}"

    @mcp.tool()
    def ssh_health_check() -> str:
        """Ping and SSH-probe all configured hosts. Returns a status table."""
        try:
            from superpowers.config import Settings
            from superpowers.ssh_fabric.executor import SSHExecutor
            from superpowers.ssh_fabric.health import HealthChecker
            from superpowers.ssh_fabric.hosts import HostRegistry
            from superpowers.ssh_fabric.pool import ConnectionPool

            Settings.load()
            hosts = HostRegistry()
            with ConnectionPool(hosts) as pool:
                executor = SSHExecutor(pool, hosts)
                checker = HealthChecker(hosts, executor)
                report = checker.check_all()

            if not report.hosts:
                return "No hosts configured."

            lines = [
                f"{'HOST':<16} {'PING':<6} {'SSH':<6} {'LATENCY':<10} {'LOAD AVG'}",
                "-" * 60,
            ]
            for h in report.hosts:
                ping = "OK" if h.ping_ok else "FAIL"
                ssh = "OK" if h.ssh_ok else "FAIL"
                latency = f"{h.latency_ms:.0f}ms"
                load = h.load_avg or (h.error if h.error else "-")
                lines.append(f"{h.alias:<16} {ping:<6} {ssh:<6} {latency:<10} {load}")

            status = "ALL OK" if report.all_ok else "DEGRADED"
            lines.append(f"\nOverall: {status}")
            return "\n".join(lines)
        except (ImportError, OSError, RuntimeError, KeyError, ValueError) as exc:
            return f"Error running health check: {exc}"

    @mcp.tool()
    def ha_get_state(entity_id: str) -> str:
        """Get the current state of a Home Assistant entity.

        Args:
            entity_id: Entity ID (e.g. "light.office", "climate.living_room", "sensor.temperature").
        """
        try:
            from superpowers.config import Settings
            from superpowers.ssh_fabric.homeassistant import HomeAssistantClient

            settings = Settings.load()
            ha = HomeAssistantClient(settings.home_assistant_url, settings.home_assistant_token)
            state = ha.get_state(entity_id)
            if not state:
                return f"Entity '{entity_id}' not found."

            s = state.get("state", "unknown")
            attrs = state.get("attributes", {})
            friendly = attrs.get("friendly_name", entity_id)
            last_changed = state.get("last_changed", "")

            lines = [f"{friendly} ({entity_id}): {s}"]
            if last_changed:
                lines.append(f"  Last changed: {last_changed}")
            for k, v in attrs.items():
                if k != "friendly_name":
                    lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        except (ImportError, OSError, RuntimeError, ValueError, KeyError) as exc:
            return f"Error getting HA state: {exc}"

    @mcp.tool()
    def ha_call_service(domain: str, service: str, entity_id: str) -> str:
        """Call a Home Assistant service on an entity.

        Args:
            domain: Service domain (e.g. "light", "climate", "switch", "homeassistant").
            service: Service name (e.g. "turn_on", "turn_off", "set_temperature").
            entity_id: Target entity ID (e.g. "light.office").
        """
        try:
            from superpowers.config import Settings
            from superpowers.ssh_fabric.homeassistant import HomeAssistantClient

            settings = Settings.load()
            ha = HomeAssistantClient(settings.home_assistant_url, settings.home_assistant_token)
            ha.call_service(domain, service, entity_id)
            return f"Called {domain}.{service} on {entity_id} successfully."
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            return f"Error calling HA service: {exc}"

    @mcp.tool()
    def ha_list_entities(filter_prefix: str = "") -> str:
        """List Home Assistant entities, optionally filtered by prefix.

        Args:
            filter_prefix: Optional prefix filter (e.g. "light.", "sensor.", "climate."). Empty string returns all.
        """
        try:
            from superpowers.config import Settings
            from superpowers.ssh_fabric.homeassistant import HomeAssistantClient

            settings = Settings.load()
            ha = HomeAssistantClient(settings.home_assistant_url, settings.home_assistant_token)
            states = ha.get_states()

            if filter_prefix:
                states = [s for s in states if s.get("entity_id", "").startswith(filter_prefix)]

            if not states:
                msg = "No entities found"
                if filter_prefix:
                    msg += f" matching '{filter_prefix}'"
                return msg + "."

            lines = [f"{'ENTITY':<40} {'STATE':<15} {'NAME'}"]
            lines.append("-" * 70)
            for s in sorted(states, key=lambda x: x.get("entity_id", "")):
                eid = s.get("entity_id", "")
                state = s.get("state", "unknown")
                name = s.get("attributes", {}).get("friendly_name", "")
                lines.append(f"{eid:<40} {state:<15} {name}")
            lines.append(f"\nTotal: {len(states)} entities")
            return "\n".join(lines)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            return f"Error listing HA entities: {exc}"
