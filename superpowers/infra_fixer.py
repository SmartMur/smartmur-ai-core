"""Infra Fixer — general-purpose Docker infrastructure health monitor and auto-fixer."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from superpowers.config import get_data_dir


HealthStatus = Literal["healthy", "degraded", "down", "crash_loop", "unknown"]
Severity = Literal["critical", "warning", "info"]


@dataclass
class ContainerInfo:
    """State of a single Docker container."""
    name: str = ""
    project: str = ""
    image: str = ""
    status: str = ""  # running, exited, restarting, etc.
    running: bool = False
    exit_code: int = 0
    restart_count: int = 0
    health: str = ""  # healthy, unhealthy, none
    started_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InfraIssue:
    """A detected infrastructure problem."""
    severity: Severity
    container: str
    project: str
    issue: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InfraReport:
    """Full infrastructure health report."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    containers_total: int = 0
    containers_running: int = 0
    containers_stopped: int = 0
    containers_unhealthy: int = 0
    projects_total: int = 0
    issues: list[InfraIssue] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    containers: list[ContainerInfo] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def status(self) -> HealthStatus:
        criticals = sum(1 for i in self.issues if i.severity == "critical")
        warnings = sum(1 for i in self.issues if i.severity == "warning")
        if criticals > 0:
            return "down"
        if warnings > 0:
            return "degraded"
        return "healthy"

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "status": self.status,
            "containers_total": self.containers_total,
            "containers_running": self.containers_running,
            "containers_stopped": self.containers_stopped,
            "containers_unhealthy": self.containers_unhealthy,
            "projects_total": self.projects_total,
            "issues": [i.to_dict() for i in self.issues],
            "actions_taken": self.actions_taken,
            "containers": [c.to_dict() for c in self.containers],
            "duration_seconds": self.duration_seconds,
            "summary": {
                "critical": self.critical_count,
                "warning": self.warning_count,
                "info": sum(1 for i in self.issues if i.severity == "info"),
            },
        }

    def to_telegram_summary(self) -> str:
        emoji_map = {"healthy": "OK", "degraded": "WARN", "down": "DOWN"}
        lines = [f"*Infra Fixer* — {emoji_map.get(self.status, '?')} {self.status.upper()}"]
        lines.append(
            f"Containers: {self.containers_running}/{self.containers_total} running"
            f" | {self.containers_unhealthy} unhealthy"
        )
        if self.issues:
            lines.append(f"Issues: {self.critical_count} critical, {self.warning_count} warning")
            for issue in self.issues[:5]:
                lines.append(f"  [{issue.severity.upper()}] {issue.container}: {issue.issue}")
            if len(self.issues) > 5:
                lines.append(f"  ...and {len(self.issues) - 5} more")
        if self.actions_taken:
            lines.append("Actions:")
            for action in self.actions_taken[:3]:
                lines.append(f"  - {action}")
        lines.append(f"_Duration: {self.duration_seconds:.1f}s_")
        return "\n".join(lines)


# Known compose projects with their expected running containers
# Containers listed here as "expected" should normally be running
# Containers not listed are considered optional (e.g., arr stack that user stopped intentionally)
KNOWN_PROJECTS = {
    "claude-superpowers": {
        "compose_dir": "/home/ray/claude-superpowers",
        "expected_running": [
            "claude-superpowers-redis-1",
            "claude-superpowers-msg-gateway-1",
            "claude-superpowers-dashboard-1",
        ],
    },
    "zabbix": {
        "compose_dir": "/home/ray/zabbix",
        "expected_running": [
            "zabbix-postgres-1",
            "zabbix-zabbix-server-1",
            "zabbix-zabbix-web-1",
        ],
    },
    "netaudit": {
        "compose_dir": "/home/ray/docker/NetAudit",
        "expected_running": [
            "netaudit-api-1",
            "netaudit-timescaledb-1",
            "netaudit-redis-1",
        ],
    },
    "joplin": {
        "compose_dir": "/home/ray/docker/joplin",
        "expected_running": ["joplin-app-1", "joplin-db-1"],
    },
    "npm": {
        "compose_dir": "/home/ray/docker/npm",
        "expected_running": ["nginx-proxy-manager"],
    },
    "cloudflared": {
        "compose_dir": "/home/ray/docker/cloudflared",
        "expected_running": ["cloudflared-cloudflared-1"],
    },
    "dockhand": {
        "compose_dir": "/home/ray/docker/dockhand",
        "expected_running": ["dockhand"],
    },
    "zntv": {
        "compose_dir": "/home/ray/zntv",
        "expected_running": ["zntv-zntv-1"],
    },
    "home_media": {
        "compose_dir": "/home/ray/docker/home_media",
        # Only core services expected; arr stack is optional
        "expected_running": ["gluetun", "qbittorrent", "jellyfin"],
    },
}

CRASH_LOOP_THRESHOLD = 5  # restart count above this = crash loop
PLACEHOLDER_PATTERNS = [
    re.compile(r"your_\w+_here", re.IGNORECASE),
    re.compile(r"changeme|CHANGEME"),
    re.compile(r"<your[_-].*>"),
]


class InfraFixer:
    """Monitor all Docker infrastructure and auto-fix common issues."""

    def __init__(self, projects: dict | None = None):
        self.projects = projects or KNOWN_PROJECTS

    def _run_cmd(
        self, args: list[str], *, timeout: int = 30
    ) -> subprocess.CompletedProcess:
        """Run a command safely (no shell=True)."""
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)

    def get_all_containers(self) -> list[ContainerInfo]:
        """Get info on all Docker containers (running and stopped)."""
        containers: list[ContainerInfo] = []
        try:
            # Use docker ps -a with a parseable format
            result = self._run_cmd([
                "docker", "ps", "-a",
                "--format",
                '{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Label "com.docker.compose.project"}}',
            ])
            if result.returncode != 0:
                return containers

            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                name, status_str, image, project = (
                    parts[0],
                    parts[1],
                    parts[2],
                    parts[3],
                )

                running = status_str.lower().startswith("up")
                health = ""
                if "(healthy)" in status_str.lower():
                    health = "healthy"
                elif "(unhealthy)" in status_str.lower():
                    health = "unhealthy"

                containers.append(ContainerInfo(
                    name=name,
                    project=project,
                    image=image,
                    status=status_str,
                    running=running,
                    health=health,
                ))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Get restart counts for non-running or unhealthy containers via inspect
        for c in containers:
            if not c.running or c.health == "unhealthy":
                try:
                    result = self._run_cmd([
                        "docker", "inspect",
                        "--format", "{{.RestartCount}} {{.State.ExitCode}}",
                        c.name,
                    ])
                    if result.returncode == 0:
                        parts = result.stdout.strip().split()
                        if len(parts) >= 2:
                            c.restart_count = int(parts[0])
                            c.exit_code = int(parts[1])
                except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                    pass

        return containers

    def check_container_health(
        self, containers: list[ContainerInfo]
    ) -> list[InfraIssue]:
        """Check all containers for common issues."""
        issues: list[InfraIssue] = []

        for c in containers:
            # Crash loop detection
            if c.restart_count >= CRASH_LOOP_THRESHOLD:
                issues.append(InfraIssue(
                    severity="critical",
                    container=c.name,
                    project=c.project,
                    issue=f"Crash loop: {c.restart_count} restarts, exit code {c.exit_code}",
                    suggestion=f"Check logs with `docker logs {c.name}`, fix config, then restart",
                ))

            # Unhealthy container
            elif c.health == "unhealthy":
                issues.append(InfraIssue(
                    severity="warning",
                    container=c.name,
                    project=c.project,
                    issue="Container healthcheck failing",
                    suggestion=f"Check `docker inspect {c.name}` for healthcheck details",
                ))

            # Restarting status (not yet at threshold)
            elif "restarting" in c.status.lower():
                issues.append(InfraIssue(
                    severity="warning",
                    container=c.name,
                    project=c.project,
                    issue=f"Container is restarting (exit code {c.exit_code})",
                    suggestion="Monitor — may recover or escalate to crash loop",
                ))

        return issues

    def check_expected_running(
        self, containers: list[ContainerInfo]
    ) -> list[InfraIssue]:
        """Check if expected containers from known projects are running."""
        issues: list[InfraIssue] = []
        running_names = {c.name for c in containers if c.running}

        for project_name, project_info in self.projects.items():
            for expected in project_info.get("expected_running", []):
                if expected not in running_names:
                    # Check if it exists but stopped
                    stopped = [
                        c for c in containers
                        if c.name == expected and not c.running
                    ]
                    if stopped:
                        issues.append(InfraIssue(
                            severity="warning",
                            container=expected,
                            project=project_name,
                            issue=f"Expected container is stopped (exit code {stopped[0].exit_code})",
                            suggestion=(
                                f"Restart with: cd {project_info['compose_dir']}"
                                " && docker compose up -d"
                            ),
                        ))
                    else:
                        issues.append(InfraIssue(
                            severity="warning",
                            container=expected,
                            project=project_name,
                            issue="Expected container not found",
                            suggestion=(
                                f"Deploy with: cd {project_info['compose_dir']}"
                                " && docker compose up -d"
                            ),
                        ))

        return issues

    def check_env_files(self) -> list[InfraIssue]:
        """Check .env files in known projects for placeholder values."""
        issues: list[InfraIssue] = []

        for project_name, project_info in self.projects.items():
            env_file = Path(project_info["compose_dir"]) / ".env"
            if not env_file.exists():
                continue

            try:
                content = env_file.read_text()
            except OSError:
                continue

            for _i, line in enumerate(content.splitlines(), 1):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                for pat in PLACEHOLDER_PATTERNS:
                    if pat.search(value):
                        issues.append(InfraIssue(
                            severity="critical",
                            container="",
                            project=project_name,
                            issue=f"Placeholder value in .env: {key.strip()}='{value}'",
                            suggestion=f"Edit {env_file} and set a real value for {key.strip()}",
                        ))
                        break

        return issues

    def check_disk_usage(self) -> list[InfraIssue]:
        """Check Docker disk usage for warning signs."""
        issues: list[InfraIssue] = []
        try:
            result = self._run_cmd([
                "docker", "system", "df",
                "--format", "{{.Type}}\t{{.Size}}\t{{.Reclaimable}}",
            ])
            if result.returncode != 0:
                return issues
            # Just report as info — no auto-fix for disk
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    resource_type, size, reclaimable = parts[0], parts[1], parts[2]
                    # Flag if reclaimable is large (contains "GB")
                    if "GB" in reclaimable:
                        issues.append(InfraIssue(
                            severity="info",
                            container="",
                            project="docker",
                            issue=f"{resource_type}: {size} total, {reclaimable} reclaimable",
                            suggestion="Run `docker system prune` to reclaim space",
                        ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return issues

    def apply_fixes(
        self, containers: list[ContainerInfo], issues: list[InfraIssue]
    ) -> list[str]:
        """Apply automatic fixes for safe, well-understood issues."""
        actions: list[str] = []

        # Group issues by type
        crash_loops = [i for i in issues if "crash loop" in i.issue.lower()]
        stopped_expected = [
            i for i in issues if "expected container is stopped" in i.issue.lower()
        ]

        # Stop crash-looping containers to save CPU
        for issue in crash_loops:
            if not issue.container:
                continue
            try:
                self._run_cmd(["docker", "stop", issue.container])
                actions.append(f"Stopped crash-looping container: {issue.container}")
            except Exception:
                actions.append(f"Failed to stop: {issue.container}")

        # Restart expected containers that are stopped (but NOT crash-looping)
        crash_loop_names = {i.container for i in crash_loops}
        for issue in stopped_expected:
            if issue.container in crash_loop_names:
                continue  # Don't restart something we just stopped
            project_info = self.projects.get(issue.project, {})
            compose_dir = project_info.get("compose_dir", "")
            if compose_dir:
                try:
                    self._run_cmd(
                        ["docker", "compose", "-f",
                         str(Path(compose_dir) / "docker-compose.yml"),
                         "up", "-d", "--no-recreate"],
                        timeout=60,
                    )
                    actions.append(
                        f"Restarted stopped container: {issue.container}"
                        f" (project: {issue.project})"
                    )
                except Exception:
                    actions.append(f"Failed to restart: {issue.container}")

        return actions

    def save_report(self, report: InfraReport) -> Path:
        """Save report to data dir."""
        fixer_dir = get_data_dir() / "infra-fixer"
        fixer_dir.mkdir(parents=True, exist_ok=True)

        data = report.to_dict()

        # Latest
        latest = fixer_dir / "latest.json"
        latest.write_text(json.dumps(data, indent=2))

        # Timestamped
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        history = fixer_dir / f"report-{ts}.json"
        history.write_text(json.dumps(data, indent=2))

        # Append issues to incident log
        if report.issues or report.actions_taken:
            incident_file = fixer_dir / "incident-log.jsonl"
            with incident_file.open("a") as f:
                f.write(json.dumps({
                    "timestamp": report.timestamp,
                    "status": report.status,
                    "issues": [i.to_dict() for i in report.issues],
                    "actions": report.actions_taken,
                }) + "\n")

        return latest

    def run_check(self, *, auto_fix: bool = True) -> InfraReport:
        """Full infrastructure check cycle."""
        import time
        start = time.monotonic()

        # Gather all containers
        containers = self.get_all_containers()

        # Run all checks
        issues: list[InfraIssue] = []
        issues.extend(self.check_container_health(containers))
        issues.extend(self.check_expected_running(containers))
        issues.extend(self.check_env_files())
        issues.extend(self.check_disk_usage())

        # Auto-fix
        actions: list[str] = []
        if auto_fix:
            actions = self.apply_fixes(containers, issues)

        # Build report
        projects = {c.project for c in containers if c.project}
        report = InfraReport(
            containers_total=len(containers),
            containers_running=sum(1 for c in containers if c.running),
            containers_stopped=sum(1 for c in containers if not c.running),
            containers_unhealthy=sum(
                1 for c in containers if c.health == "unhealthy"
            ),
            projects_total=len(projects),
            issues=issues,
            actions_taken=actions,
            containers=containers,
            duration_seconds=round(time.monotonic() - start, 2),
        )

        return report
