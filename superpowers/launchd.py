"""macOS launchd plist management for claude-superpowers services."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PREFIX = "com.dreday"
LOG_DIR = Path.home() / ".claude-superpowers" / "logs"
PROJECT_DIR = Path("/Users/dre/Projects/claude-superpowers")
VENV_PYTHON = str(PROJECT_DIR / ".venv" / "bin" / "python")


def _plist_path(service_name: str) -> Path:
    return LAUNCH_AGENTS_DIR / f"{PLIST_PREFIX}.{service_name}.plist"


def generate_plist(
    service_name: str,
    command: list[str],
    interval: int | None = None,
    keep_alive: bool = True,
    working_directory: str | None = None,
    stdout_path: str | None = None,
    stderr_path: str | None = None,
) -> str:
    """Generate a launchd plist XML string."""
    label = f"{PLIST_PREFIX}.{service_name}"
    plist: dict = {
        "Label": label,
        "ProgramArguments": command,
        "KeepAlive": keep_alive,
    }
    if interval is not None:
        plist["StartInterval"] = interval
        # When using StartInterval, KeepAlive restarts crashes — both can coexist
    if working_directory:
        plist["WorkingDirectory"] = working_directory
    if stdout_path:
        plist["StandardOutPath"] = stdout_path
    if stderr_path:
        plist["StandardErrorPath"] = stderr_path

    return plistlib.dumps(plist, fmt=plistlib.FMT_XML).decode()


def install_plist(service_name: str, plist_content: str) -> Path:
    """Write plist to ~/Library/LaunchAgents/ and return the path."""
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _plist_path(service_name)
    path.write_text(plist_content)
    return path


def uninstall_plist(service_name: str) -> None:
    """Unload service and remove plist file."""
    try:
        unload_service(service_name)
    except Exception:
        pass
    path = _plist_path(service_name)
    if path.exists():
        path.unlink()


def load_service(service_name: str) -> None:
    """Load the service via launchctl."""
    path = _plist_path(service_name)
    if not path.exists():
        raise FileNotFoundError(f"Plist not found: {path}")
    subprocess.run(["launchctl", "load", str(path)], check=True)


def unload_service(service_name: str) -> None:
    """Unload the service via launchctl."""
    path = _plist_path(service_name)
    if not path.exists():
        raise FileNotFoundError(f"Plist not found: {path}")
    subprocess.run(["launchctl", "unload", str(path)], check=True)


def service_status(service_name: str) -> dict:
    """Check if a service is running via launchctl list."""
    label = f"{PLIST_PREFIX}.{service_name}"
    result = subprocess.run(
        ["launchctl", "list", label],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"running": False, "label": label, "pid": None, "exit_code": None}

    info: dict = {"running": False, "label": label, "pid": None, "exit_code": None}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith('"PID"'):
            # launchctl list output: "PID" = 12345;
            parts = line.split("=")
            if len(parts) == 2:
                pid_str = parts[1].strip().rstrip(";").strip()
                try:
                    info["pid"] = int(pid_str)
                    info["running"] = True
                except ValueError:
                    pass
        elif line.startswith('"LastExitStatus"'):
            parts = line.split("=")
            if len(parts) == 2:
                code_str = parts[1].strip().rstrip(";").strip()
                try:
                    info["exit_code"] = int(code_str)
                except ValueError:
                    pass

    # Fallback: also check the simpler launchctl list | grep approach
    if not info["running"]:
        result2 = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
        )
        for line in result2.stdout.splitlines():
            if label in line:
                parts = line.split()
                if len(parts) >= 3 and parts[0] != "-":
                    try:
                        info["pid"] = int(parts[0])
                        info["running"] = True
                    except ValueError:
                        pass
                if len(parts) >= 3:
                    try:
                        info["exit_code"] = int(parts[1])
                    except ValueError:
                        pass
                break

    return info


def install_cron_daemon() -> Path:
    """Install and load the cron daemon launchd service."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = str(LOG_DIR / "cron-daemon.log")

    plist_content = generate_plist(
        service_name="claude-superpowers-cron",
        command=[VENV_PYTHON, "-m", "superpowers.cron_runner"],
        keep_alive=True,
        working_directory=str(PROJECT_DIR),
        stdout_path=log_path,
        stderr_path=log_path,
    )
    path = install_plist("claude-superpowers-cron", plist_content)
    load_service("claude-superpowers-cron")
    return path
