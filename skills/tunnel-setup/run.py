#!/usr/bin/env python3
"""Tunnel Setup skill — validate token, manage cloudflared container, check connectivity."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from superpowers.audit import AuditLog
from superpowers.config import get_data_dir
from superpowers import telegram_notify

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPOSE_DIR = Path("/home/ray/docker/cloudflared")
ENV_FILE = COMPOSE_DIR / ".env"
CONTAINER_NAME = "cloudflared-cloudflared-1"

# Cloudflare tunnel tokens are JWT-like base64 strings, typically 150+ chars.
# We require at least 50 chars of base64-ish content.
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-+/=.]{50,}$")

PLACEHOLDER_VALUES = frozenset({
    "your_tunnel_token_here",
    "your_token_here",
    "changeme",
    "<your-token>",
    "",
})


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

def validate_token(token: str) -> tuple[bool, str]:
    """Validate a Cloudflare tunnel token.

    Returns (is_valid, message).
    """
    if not token:
        return False, "Token is empty"
    if token.lower() in PLACEHOLDER_VALUES:
        return False, f"Token is a placeholder value: '{token}'"
    if len(token) < 50:
        return False, f"Token too short ({len(token)} chars, need 50+)"
    if not TOKEN_PATTERN.match(token):
        return False, "Token contains invalid characters (expected base64-like string)"
    return True, "Token format looks valid"


# ---------------------------------------------------------------------------
# Docker helpers (no shell=True)
# ---------------------------------------------------------------------------

def _run_cmd(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command safely."""
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def _get_container_status() -> dict:
    """Get container status info. Returns dict with keys: exists, running, status, exit_code, restart_count."""
    info: dict = {
        "exists": False,
        "running": False,
        "status": "not_found",
        "exit_code": -1,
        "restart_count": 0,
    }
    try:
        result = _run_cmd([
            "docker", "inspect",
            "--format",
            '{"running":{{.State.Running}},"exit_code":{{.State.ExitCode}},"restart_count":{{.RestartCount}},"status":"{{.State.Status}}"}',
            CONTAINER_NAME,
        ])
        if result.returncode != 0:
            return info

        import json
        data = json.loads(result.stdout.strip())
        info["exists"] = True
        info["running"] = data.get("running", False)
        info["status"] = data.get("status", "unknown")
        info["exit_code"] = data.get("exit_code", -1)
        info["restart_count"] = data.get("restart_count", 0)
    except Exception:
        pass
    return info


def _read_env_token() -> tuple[str, str]:
    """Read current token from .env file.

    Returns (token_value, message).
    """
    if not ENV_FILE.exists():
        return "", f".env not found at {ENV_FILE}"
    try:
        content = ENV_FILE.read_text()
    except OSError as exc:
        return "", f"Cannot read .env: {exc}"

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "CLOUDFLARE_TUNNEL_TOKEN":
            return value, "found"
    return "", "CLOUDFLARE_TUNNEL_TOKEN not found in .env"


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_status() -> int:
    """Show container state, token validation, tunnel health."""
    print("=== Cloudflare Tunnel Status ===\n")

    # Token check
    token, token_msg = _read_env_token()
    if token_msg == "found":
        valid, detail = validate_token(token)
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
        print(f"Token:     {masked}")
        print(f"Valid:     {'yes' if valid else 'NO — ' + detail}")
    else:
        print(f"Token:     NOT SET — {token_msg}")

    print()

    # Container check
    status = _get_container_status()
    if not status["exists"]:
        print(f"Container: {CONTAINER_NAME} — not found")
        print("  Hint: run '/tunnel-setup start' to create it")
    else:
        state_str = "RUNNING" if status["running"] else f"STOPPED (exit {status['exit_code']})"
        print(f"Container: {CONTAINER_NAME} — {state_str}")
        print(f"  Status:       {status['status']}")
        print(f"  Restarts:     {status['restart_count']}")

    # Health verdict
    print()
    if not status["exists"]:
        print("Health: DOWN (container not found)")
        return 1
    if status["running"]:
        print("Health: OK")
        return 0
    if status["restart_count"] >= 5:
        print("Health: CRASH LOOP")
        return 1
    print("Health: DOWN")
    return 1


def cmd_set_token(token: str) -> int:
    """Validate and write tunnel token to .env, then start container."""
    valid, detail = validate_token(token)
    if not valid:
        print(f"ERROR: {detail}", file=sys.stderr)
        return 2

    # Write .env
    try:
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text(f"CLOUDFLARE_TUNNEL_TOKEN={token}\n")
        print(f"Token written to {ENV_FILE}")
    except OSError as exc:
        print(f"ERROR: Cannot write .env: {exc}", file=sys.stderr)
        return 2

    # Audit
    try:
        audit = AuditLog(get_data_dir() / "audit.log")
        audit.log(
            "tunnel.token_set",
            f"Token updated ({len(token)} chars)",
            source="skill:tunnel-setup",
        )
    except Exception:
        pass

    # Telegram notify
    try:
        telegram_notify.notify("[TUNNEL] Token configured, starting container...")
    except Exception:
        pass

    # Start container
    print("Starting cloudflared container...")
    rc = cmd_start()

    if rc == 0:
        try:
            telegram_notify.notify_done("Cloudflare tunnel started with new token")
        except Exception:
            pass
    else:
        try:
            telegram_notify.notify_error("Cloudflare tunnel", "Failed to start after token update")
        except Exception:
            pass

    return rc


def cmd_start() -> int:
    """Start cloudflared container via docker compose."""
    if not COMPOSE_DIR.exists():
        print(f"ERROR: Compose directory not found: {COMPOSE_DIR}", file=sys.stderr)
        return 2

    # Validate token before starting
    token, token_msg = _read_env_token()
    if token_msg == "found":
        valid, detail = validate_token(token)
        if not valid:
            print(f"WARNING: Token issue — {detail}", file=sys.stderr)
            print("Container may crash-loop. Use '/tunnel-setup set-token <token>' to fix.", file=sys.stderr)

    try:
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            capture_output=True, text=True, timeout=60,
            cwd=str(COMPOSE_DIR),
        )
        if result.returncode == 0:
            print("Container started successfully")
            try:
                audit = AuditLog(get_data_dir() / "audit.log")
                audit.log("tunnel.started", "Container started", source="skill:tunnel-setup")
            except Exception:
                pass
            return 0
        else:
            print(f"ERROR: docker compose up failed:\n{result.stderr}", file=sys.stderr)
            return 2
    except subprocess.TimeoutExpired:
        print("ERROR: docker compose up timed out", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("ERROR: docker command not found", file=sys.stderr)
        return 2


def cmd_stop() -> int:
    """Stop cloudflared container."""
    try:
        result = _run_cmd(["docker", "stop", CONTAINER_NAME])
        if result.returncode == 0:
            print(f"Container {CONTAINER_NAME} stopped")
            try:
                audit = AuditLog(get_data_dir() / "audit.log")
                audit.log("tunnel.stopped", "Container stopped", source="skill:tunnel-setup")
            except Exception:
                pass
            try:
                telegram_notify.notify("[TUNNEL] Container stopped")
            except Exception:
                pass
            return 0
        else:
            print(f"ERROR: docker stop failed:\n{result.stderr}", file=sys.stderr)
            return 1
    except subprocess.TimeoutExpired:
        print("ERROR: docker stop timed out", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("ERROR: docker command not found", file=sys.stderr)
        return 2


def cmd_logs() -> int:
    """Show recent container logs."""
    try:
        result = _run_cmd(
            ["docker", "logs", "--tail", "30", CONTAINER_NAME],
            timeout=15,
        )
        output = result.stdout + result.stderr
        if not output.strip():
            print("(no logs available)")
        else:
            print(output)
        return 0 if result.returncode == 0 else 1
    except subprocess.TimeoutExpired:
        print("ERROR: docker logs timed out", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("ERROR: docker command not found", file=sys.stderr)
        return 2


def cmd_help() -> int:
    """Print usage information."""
    print("Usage: tunnel-setup <subcommand> [args]\n")
    print("Subcommands:")
    print("  status             Show container state, token validation, tunnel health")
    print("  set-token <token>  Validate token, write to .env, start container")
    print("  start              Start cloudflared container (docker compose up -d)")
    print("  stop               Stop cloudflared container")
    print("  logs               Show last 30 lines of container logs")
    print("  help               Show this help message")
    print()
    print("Exit codes: 0=success, 1=issue, 2=error")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point — dispatch subcommand."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        return cmd_status()

    subcmd = argv[0].lower()

    if subcmd == "status":
        return cmd_status()
    elif subcmd == "set-token":
        if len(argv) < 2:
            print("ERROR: set-token requires a token argument", file=sys.stderr)
            print("Usage: tunnel-setup set-token <your-cloudflare-tunnel-token>", file=sys.stderr)
            return 2
        return cmd_set_token(argv[1])
    elif subcmd == "start":
        return cmd_start()
    elif subcmd == "stop":
        return cmd_stop()
    elif subcmd == "logs":
        return cmd_logs()
    elif subcmd in ("help", "--help", "-h"):
        return cmd_help()
    else:
        print(f"ERROR: Unknown subcommand '{subcmd}'", file=sys.stderr)
        return cmd_help() or 2


if __name__ == "__main__":
    sys.exit(main())
