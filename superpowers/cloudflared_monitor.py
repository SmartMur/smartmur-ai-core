"""Cloudflared tunnel monitor — detect crash loops, diagnose errors, auto-fix."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from superpowers.config import get_data_dir

Status = Literal["healthy", "degraded", "down", "crash_loop", "unknown"]


@dataclass
class ContainerState:
    """Current state of the cloudflared container."""
    running: bool = False
    exit_code: int = 0
    restart_count: int = 0
    status: str = ""
    started_at: str = ""
    error_log: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiagnosticResult:
    """Diagnosis of what's wrong and what to do."""
    status: Status = "unknown"
    issues: list[str] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    needs_user_action: bool = False
    user_action_message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_telegram_summary(self) -> str:
        lines = [f"*Cloudflared Monitor* — Status: {self.status.upper()}"]
        if self.issues:
            lines.append("Issues:")
            for issue in self.issues[:5]:
                lines.append(f"  - {issue}")
        if self.actions_taken:
            lines.append("Actions taken:")
            for action in self.actions_taken[:5]:
                lines.append(f"  - {action}")
        if self.needs_user_action:
            lines.append(f"\n*User action required:* {self.user_action_message}")
        return "\n".join(lines)


# Error patterns to look for in container logs
ERROR_PATTERNS = {
    "invalid_token": re.compile(r"(?:invalid|unauthorized|bad).*token", re.IGNORECASE),
    "placeholder_token": re.compile(r"your_tunnel_token_here", re.IGNORECASE),
    "network_error": re.compile(r"(?:DNS|network|connection refused|timeout|dial tcp)", re.IGNORECASE),
    "cert_error": re.compile(r"(?:certificate|TLS|SSL).*(?:error|failed|invalid)", re.IGNORECASE),
    "version_mismatch": re.compile(r"(?:version|upgrade|deprecated|incompatible)", re.IGNORECASE),
}


class CloudflaredMonitor:
    """Monitor and auto-fix cloudflared tunnel container."""

    DEFAULT_CONTAINER = "cloudflared-cloudflared-1"
    DEFAULT_COMPOSE_DIR = Path("/home/ray/docker/cloudflared")
    CRASH_LOOP_THRESHOLD = 5  # restarts in monitoring window

    def __init__(
        self,
        container_name: str = DEFAULT_CONTAINER,
        compose_dir: Path | str = DEFAULT_COMPOSE_DIR,
    ):
        self.container_name = container_name
        self.compose_dir = Path(compose_dir)

    def _run_cmd(self, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a command safely (no shell=True)."""
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
        )

    def get_container_state(self) -> ContainerState:
        """Inspect container and return its state."""
        state = ContainerState()

        try:
            result = self._run_cmd([
                "docker", "inspect",
                "--format", '{"running":{{.State.Running}},"exit_code":{{.State.ExitCode}},"restart_count":{{.RestartCount}},"status":"{{.State.Status}}","started_at":"{{.State.StartedAt}}"}',
                self.container_name,
            ])
            if result.returncode != 0:
                state.status = "not_found"
                return state

            data = json.loads(result.stdout.strip())
            state.running = data.get("running", False)
            state.exit_code = data.get("exit_code", 0)
            state.restart_count = data.get("restart_count", 0)
            state.status = data.get("status", "unknown")
            state.started_at = data.get("started_at", "")

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            state.status = "inspect_failed"
            return state

        # Get recent logs
        try:
            log_result = self._run_cmd([
                "docker", "logs", "--tail", "50", self.container_name,
            ])
            state.error_log = (log_result.stdout + log_result.stderr)[-2000:]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return state

    def check_env_token(self) -> tuple[bool, str]:
        """Check if .env has a real tunnel token (not placeholder).

        Returns (is_valid, message).
        """
        env_file = self.compose_dir / ".env"
        if not env_file.exists():
            return False, f".env file not found at {env_file}"

        try:
            content = env_file.read_text()
        except OSError as exc:
            return False, f"Cannot read .env: {exc}"

        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key.upper() in ("TUNNEL_TOKEN", "CLOUDFLARE_TUNNEL_TOKEN", "CF_TUNNEL_TOKEN"):
                if not value or value == "your_tunnel_token_here" or value.startswith("your_"):
                    return False, f"Token is a placeholder: '{value}'"
                if len(value) < 20:
                    return False, f"Token looks too short ({len(value)} chars)"
                return True, "Token looks valid"

        return False, "No tunnel token variable found in .env"

    def diagnose(self, state: ContainerState) -> DiagnosticResult:
        """Analyze container state and produce diagnosis."""
        result = DiagnosticResult()

        # Check if container exists
        if state.status == "not_found":
            result.status = "down"
            result.issues.append("Container not found — may need docker compose up")
            return result

        if state.status == "inspect_failed":
            result.status = "unknown"
            result.issues.append("Could not inspect container — docker may not be running")
            return result

        # Check token first
        token_valid, token_msg = self.check_env_token()
        if not token_valid:
            result.status = "down"
            result.issues.append(f"Invalid token: {token_msg}")
            result.needs_user_action = True
            result.user_action_message = (
                "Cloudflared needs a real tunnel token. "
                "Go to https://one.dash.cloudflare.com/, create/retrieve a tunnel token, "
                f"and paste it into {self.compose_dir / '.env'}"
            )

        # Check crash loop
        if state.restart_count >= self.CRASH_LOOP_THRESHOLD:
            result.status = "crash_loop"
            result.issues.append(
                f"Crash loop detected: {state.restart_count} restarts, exit code {state.exit_code}"
            )

        # Check error patterns in logs
        if state.error_log:
            for pattern_name, pattern in ERROR_PATTERNS.items():
                if pattern.search(state.error_log):
                    result.issues.append(f"Log pattern match: {pattern_name}")

        # Set status if not already set
        if result.status == "unknown":
            if state.running:
                result.status = "healthy" if not result.issues else "degraded"
            else:
                result.status = "down"

        return result

    def apply_fixes(self, state: ContainerState, diagnosis: DiagnosticResult) -> DiagnosticResult:
        """Apply automatic fixes based on diagnosis. Modifies diagnosis in place."""

        # Don't auto-fix if user action is needed (e.g., bad token)
        if diagnosis.needs_user_action:
            # If crash looping with bad token, stop the container to save CPU
            if diagnosis.status == "crash_loop":
                try:
                    self._run_cmd(["docker", "stop", self.container_name])
                    diagnosis.actions_taken.append(
                        "Stopped crash-looping container (bad token — waiting for user fix)"
                    )
                except Exception:
                    pass
            return diagnosis

        # Crash loop — stop container and alert
        if diagnosis.status == "crash_loop":
            try:
                self._run_cmd(["docker", "stop", self.container_name])
                diagnosis.actions_taken.append("Stopped crash-looping container")
            except Exception:
                diagnosis.actions_taken.append("Failed to stop crash-looping container")
            return diagnosis

        # Network errors — restart once
        has_network_error = any("network_error" in issue for issue in diagnosis.issues)
        if has_network_error and not state.running:
            try:
                self._run_cmd(
                    ["docker", "compose", "restart"],
                    timeout=60,
                )
                diagnosis.actions_taken.append("Restarted container (network error recovery)")
            except Exception:
                diagnosis.actions_taken.append("Failed to restart container")
            return diagnosis

        # Container down but no specific issue — try restart
        if diagnosis.status == "down" and not diagnosis.needs_user_action:
            try:
                self._run_cmd(
                    ["docker", "compose", "up", "-d"],
                    timeout=60,
                )
                diagnosis.actions_taken.append("Started container with docker compose up -d")
            except Exception:
                diagnosis.actions_taken.append("Failed to start container")

        return diagnosis

    def save_status(self, state: ContainerState, diagnosis: DiagnosticResult) -> Path:
        """Save current status to data dir."""
        monitor_dir = get_data_dir() / "cloudflared-monitor"
        monitor_dir.mkdir(parents=True, exist_ok=True)

        status_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "container": state.to_dict(),
            "diagnosis": diagnosis.to_dict(),
        }

        # Save latest status
        status_file = monitor_dir / "status.json"
        status_file.write_text(json.dumps(status_data, indent=2))

        # Append to incident log if there are issues
        if diagnosis.issues or diagnosis.actions_taken:
            incident_file = monitor_dir / "incident-log.jsonl"
            with incident_file.open("a") as f:
                f.write(json.dumps(status_data) + "\n")

        return status_file

    def run_check(self) -> tuple[ContainerState, DiagnosticResult]:
        """Full check cycle: inspect → diagnose → fix → save."""
        state = self.get_container_state()
        diagnosis = self.diagnose(state)
        diagnosis = self.apply_fixes(state, diagnosis)
        self.save_status(state, diagnosis)
        return state, diagnosis
