"""Network scanner — ping sweep + port scan using only stdlib.

No nmap dependency required. Uses subprocess ping and socket connect
for host discovery and port checking.

Configuration via environment variables:
    NETWORK_SCAN_HOSTS  — comma-separated list of host:label pairs
                          e.g. "192.168.30.117:Docker Host,192.168.13.69:TrueNAS"
    NETWORK_SCAN_SUBNETS — comma-separated CIDR subnets to sweep
                          e.g. "192.168.30.0/24,192.168.13.0/24"
    NETWORK_SCAN_PORTS  — comma-separated ports to check (default: 22,80,443,8080,8443)
    NETWORK_SCAN_CRITICAL — comma-separated IPs that MUST be up (exit code 1 if any down)
    NETWORK_SCAN_TIMEOUT — ping/connect timeout in seconds (default: 2)
    NETWORK_SCAN_WORKERS — max parallel workers (default: 20)
"""

from __future__ import annotations

import ipaddress
import os
import platform
import socket
import subprocess
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

# ── Defaults ──────────────────────────────────────────────────────────

DEFAULT_PORTS = [22, 80, 443, 8080, 8443]

DEFAULT_HOSTS: list[tuple[str, str]] = [
    ("192.168.30.117", "Docker Host"),
    ("192.168.13.69", "TrueNAS"),
    ("192.168.100.100", "PVE1"),
    ("192.168.100.200", "PVE2"),
    ("192.168.13.10", "Switch"),
    ("192.168.13.13", "CGM"),
]

DEFAULT_TIMEOUT = 2
DEFAULT_WORKERS = 20


# ── Data classes ──────────────────────────────────────────────────────


@dataclass
class PortResult:
    """Result of a single port check."""

    port: int
    open: bool
    response_time_ms: float | None = None  # None if closed/timeout


@dataclass
class HostResult:
    """Result of scanning a single host."""

    ip: str
    label: str
    alive: bool
    ping_time_ms: float | None = None  # None if unreachable
    ports: list[PortResult] = field(default_factory=list)
    error: str = ""


@dataclass
class ScanReport:
    """Full scan report."""

    hosts: list[HostResult] = field(default_factory=list)
    total_hosts: int = 0
    hosts_up: int = 0
    hosts_down: int = 0
    critical_down: list[str] = field(default_factory=list)
    scan_time_seconds: float = 0.0

    @property
    def all_critical_up(self) -> bool:
        return len(self.critical_down) == 0


# ── Configuration loader ─────────────────────────────────────────────


def load_config() -> dict:
    """Load scanner configuration from environment variables.

    Returns a dict with keys: hosts, subnets, ports, critical, timeout, workers.
    """
    config: dict = {}

    # Hosts — "ip:label,ip:label" or use defaults
    hosts_env = os.environ.get("NETWORK_SCAN_HOSTS", "")
    if hosts_env.strip():
        hosts = []
        for entry in hosts_env.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if ":" in entry:
                ip, label = entry.split(":", 1)
                hosts.append((ip.strip(), label.strip()))
            else:
                hosts.append((entry, entry))
        config["hosts"] = hosts
    else:
        config["hosts"] = list(DEFAULT_HOSTS)

    # Subnets for sweep
    subnets_env = os.environ.get("NETWORK_SCAN_SUBNETS", "")
    if subnets_env.strip():
        config["subnets"] = [s.strip() for s in subnets_env.split(",") if s.strip()]
    else:
        config["subnets"] = []

    # Ports
    ports_env = os.environ.get("NETWORK_SCAN_PORTS", "")
    if ports_env.strip():
        config["ports"] = [int(p.strip()) for p in ports_env.split(",") if p.strip()]
    else:
        config["ports"] = list(DEFAULT_PORTS)

    # Critical hosts
    critical_env = os.environ.get("NETWORK_SCAN_CRITICAL", "")
    if critical_env.strip():
        config["critical"] = [h.strip() for h in critical_env.split(",") if h.strip()]
    else:
        # Default: all configured hosts are critical
        config["critical"] = [h[0] for h in config["hosts"]]

    # Timeout
    config["timeout"] = int(os.environ.get("NETWORK_SCAN_TIMEOUT", str(DEFAULT_TIMEOUT)))

    # Workers
    config["workers"] = int(os.environ.get("NETWORK_SCAN_WORKERS", str(DEFAULT_WORKERS)))

    return config


# ── Low-level probes ─────────────────────────────────────────────────


def ping_host(ip: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, float | None]:
    """Ping a host. Returns (alive, latency_ms).

    Uses subprocess to call the system ping command.
    Works on Linux and macOS.
    """
    system = platform.system().lower()
    if system == "windows":
        count_flag = "-n"
        timeout_flag = "-w"
        timeout_val = str(timeout * 1000)  # Windows uses milliseconds
    else:
        count_flag = "-c"
        timeout_flag = "-W"
        timeout_val = str(timeout)

    cmd = ["ping", count_flag, "1", timeout_flag, timeout_val, ip]

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2,  # subprocess timeout slightly longer
        )
        elapsed = (time.monotonic() - start) * 1000  # ms

        if result.returncode == 0:
            # Try to parse actual ping time from output
            parsed_time = _parse_ping_time(result.stdout)
            return True, parsed_time if parsed_time is not None else round(elapsed, 2)
        return False, None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False, None


def _parse_ping_time(output: str) -> float | None:
    """Extract RTT from ping output.

    Handles both Linux and macOS formats:
        Linux: "time=1.23 ms"
        macOS: "time=1.234 ms"
    """
    for line in output.splitlines():
        if "time=" in line:
            try:
                # Extract the number after "time="
                part = line.split("time=")[1]
                ms_str = part.split()[0].rstrip("ms")
                return round(float(ms_str), 2)
            except (IndexError, ValueError):
                continue
    return None


def check_port(ip: str, port: int, timeout: int = DEFAULT_TIMEOUT) -> PortResult:
    """Check if a TCP port is open on a host."""
    start = time.monotonic()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        elapsed = round((time.monotonic() - start) * 1000, 2)
        sock.close()
        if result == 0:
            return PortResult(port=port, open=True, response_time_ms=elapsed)
        return PortResult(port=port, open=False)
    except (TimeoutError, OSError):
        return PortResult(port=port, open=False)


# ── Subnet expansion ─────────────────────────────────────────────────


def expand_subnet(cidr: str) -> list[str]:
    """Expand a CIDR subnet into a list of host IP strings.

    Excludes the network and broadcast addresses.
    """
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        return [str(ip) for ip in network.hosts()]
    except ValueError:
        return []


# ── Scanner ──────────────────────────────────────────────────────────


def scan_host(
    ip: str,
    label: str = "",
    ports: Sequence[int] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> HostResult:
    """Scan a single host: ping + port check.

    Returns a HostResult with ping status and port scan results.
    """
    if ports is None:
        ports = DEFAULT_PORTS
    if not label:
        label = ip

    alive, ping_ms = ping_host(ip, timeout=timeout)

    result = HostResult(
        ip=ip,
        label=label,
        alive=alive,
        ping_time_ms=ping_ms,
    )

    # Only scan ports if host is alive (or if we want to check anyway)
    if alive:
        for port in ports:
            result.ports.append(check_port(ip, port, timeout=timeout))

    return result


def run_scan(
    hosts: list[tuple[str, str]] | None = None,
    subnets: list[str] | None = None,
    ports: list[int] | None = None,
    critical: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    workers: int = DEFAULT_WORKERS,
) -> ScanReport:
    """Run a full network scan.

    Args:
        hosts: List of (ip, label) tuples. Uses defaults if None.
        subnets: CIDR subnets to sweep. Discovered hosts get auto-labels.
        ports: TCP ports to check on live hosts.
        critical: IPs that must be up for exit code 0.
        timeout: Ping/connect timeout in seconds.
        workers: Max parallel scan threads.

    Returns:
        ScanReport with all results.
    """
    if hosts is None:
        hosts = list(DEFAULT_HOSTS)
    if subnets is None:
        subnets = []
    if ports is None:
        ports = list(DEFAULT_PORTS)
    if critical is None:
        critical = [h[0] for h in hosts]

    start_time = time.monotonic()

    # Build target list: explicit hosts + subnet expansion
    # Track known IPs so we don't duplicate
    targets: dict[str, str] = {}  # ip -> label
    for ip, label in hosts:
        targets[ip] = label

    for cidr in subnets:
        for ip in expand_subnet(cidr):
            if ip not in targets:
                targets[ip] = f"discovered-{ip}"

    # Parallel scan
    results: list[HostResult] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(targets) or 1)) as executor:
        futures = {
            executor.submit(scan_host, ip, label, ports, timeout): ip
            for ip, label in targets.items()
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except (OSError, subprocess.SubprocessError, ValueError, TimeoutError) as exc:
                ip = futures[future]
                results.append(
                    HostResult(
                        ip=ip,
                        label=targets.get(ip, ip),
                        alive=False,
                        error=str(exc),
                    )
                )

    # Sort by IP for deterministic output
    results.sort(key=lambda r: tuple(int(p) for p in r.ip.split(".") if p.isdigit()))

    elapsed = time.monotonic() - start_time

    # Build report
    critical_set = set(critical)
    report = ScanReport(
        hosts=results,
        total_hosts=len(results),
        hosts_up=sum(1 for r in results if r.alive),
        hosts_down=sum(1 for r in results if not r.alive),
        critical_down=[r.ip for r in results if not r.alive and r.ip in critical_set],
        scan_time_seconds=round(elapsed, 2),
    )

    return report


# ── Output formatting ────────────────────────────────────────────────

PORT_NAMES = {
    22: "SSH",
    80: "HTTP",
    443: "HTTPS",
    8080: "HTTP-Alt",
    8443: "HTTPS-Alt",
    3000: "Grafana",
    8006: "Proxmox",
    8123: "HomeAssist",
    9090: "Prometheus",
    6379: "Redis",
    5432: "Postgres",
    3306: "MySQL",
    8200: "Dashboard",
}


def format_table(report: ScanReport) -> str:
    """Format scan results as a human-readable table.

    Follows the heartbeat skill's table style.
    """
    lines: list[str] = []
    lines.append("")
    lines.append("=== Network Scan Results ===")
    lines.append("")

    # Host status table
    lines.append(f"{'HOST':<20} {'IP':<18} {'STATUS':<8} {'PING':<10} {'OPEN PORTS'}")
    lines.append(f"{'----':<20} {'--':<18} {'------':<8} {'----':<10} {'----------'}")

    for host in report.hosts:
        status = "UP" if host.alive else "DOWN"
        ping_str = f"{host.ping_time_ms:.1f}ms" if host.ping_time_ms is not None else "---"
        open_ports = [p for p in host.ports if p.open]
        if open_ports:
            port_str = ", ".join(f"{p.port}/{PORT_NAMES.get(p.port, '?')}" for p in open_ports)
        else:
            port_str = "none" if host.alive else "---"

        lines.append(f"{host.label:<20} {host.ip:<18} {status:<8} {ping_str:<10} {port_str}")

    lines.append("")

    # Summary
    lines.append(f"Total: {report.total_hosts} hosts scanned in {report.scan_time_seconds:.1f}s")
    lines.append(f"  Up: {report.hosts_up}  Down: {report.hosts_down}")

    if report.critical_down:
        lines.append("")
        lines.append(f"[!] CRITICAL hosts DOWN: {', '.join(report.critical_down)}")
    else:
        lines.append("")
        lines.append("[OK] All critical hosts are UP.")

    lines.append("")
    return "\n".join(lines)


def format_port_detail(report: ScanReport) -> str:
    """Format detailed port scan results for hosts that are up."""
    lines: list[str] = []
    lines.append("")
    lines.append("=== Port Scan Detail ===")
    lines.append("")

    for host in report.hosts:
        if not host.alive:
            continue
        if not host.ports:
            continue

        lines.append(f"{host.label} ({host.ip}):")
        for p in host.ports:
            status = "OPEN" if p.open else "CLOSED"
            name = PORT_NAMES.get(p.port, "?")
            time_str = f" ({p.response_time_ms:.1f}ms)" if p.response_time_ms is not None else ""
            lines.append(f"  {p.port:>5}/{name:<12} {status}{time_str}")
        lines.append("")

    return "\n".join(lines)
