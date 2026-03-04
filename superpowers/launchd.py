"""Service management for claude-superpowers daemons.

On Linux this module manages user-level systemd units.
On macOS it manages launchd plists.
"""

from __future__ import annotations

import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
PLIST_PREFIX = "com.claude-superpowers"
from superpowers.config import get_data_dir  # noqa: E402

LOG_DIR = get_data_dir() / "logs"
PROJECT_DIR = Path(__file__).resolve().parent.parent
VENV_PYTHON = sys.executable


def service_backend() -> str:
    if sys.platform == "darwin":
        return "launchd"
    if sys.platform.startswith("linux"):
        return "systemd"
    return "unsupported"


def service_label(service_name: str) -> str:
    if service_backend() == "launchd":
        launchd_name = service_name
        if launchd_name.startswith("claude-superpowers-"):
            launchd_name = launchd_name.removeprefix("claude-superpowers-")
        return f"{PLIST_PREFIX}.{launchd_name}"
    return f"{service_name}.service"


def _plist_path(service_name: str) -> Path:
    return LAUNCH_AGENTS_DIR / f"{service_label(service_name)}.plist"


def _unit_path(service_name: str) -> Path:
    return SYSTEMD_USER_DIR / service_label(service_name)


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
    label = service_label(service_name)
    plist: dict = {
        "Label": label,
        "ProgramArguments": command,
        "KeepAlive": keep_alive,
    }
    if interval is not None:
        plist["StartInterval"] = interval
    if working_directory:
        plist["WorkingDirectory"] = working_directory
    if stdout_path:
        plist["StandardOutPath"] = stdout_path
    if stderr_path:
        plist["StandardErrorPath"] = stderr_path

    return plistlib.dumps(plist, fmt=plistlib.FMT_XML).decode()


def generate_systemd_unit(
    service_name: str,
    command: list[str],
    keep_alive: bool = True,
    working_directory: str | None = None,
) -> str:
    """Generate a systemd user service unit."""
    restart = "always" if keep_alive else "no"
    quoted_cmd = " ".join(shlex.quote(part) for part in command)

    lines = [
        "[Unit]",
        f"Description={service_name}",
        "",
        "[Service]",
        "Type=simple",
        f"ExecStart={quoted_cmd}",
        f"Restart={restart}",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ]
    if working_directory:
        lines.insert(7, f"WorkingDirectory={working_directory}")
    return "\n".join(lines)


def install_plist(service_name: str, service_content: str) -> Path:
    """Write service file and return its path."""
    backend = service_backend()
    if backend == "launchd":
        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        path = _plist_path(service_name)
    elif backend == "systemd":
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
        path = _unit_path(service_name)
    else:
        raise RuntimeError(f"Unsupported platform for daemon management: {sys.platform}")

    path.write_text(service_content)
    return path


def uninstall_plist(service_name: str) -> None:
    """Stop and remove service file."""
    try:
        unload_service(service_name)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, RuntimeError):
        pass

    backend = service_backend()
    path = _plist_path(service_name) if backend == "launchd" else _unit_path(service_name)
    if path.exists():
        path.unlink()

    if backend == "systemd":
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)


def load_service(service_name: str) -> None:
    """Start and enable a service on the current platform."""
    backend = service_backend()
    if backend == "launchd":
        path = _plist_path(service_name)
        if not path.exists():
            raise FileNotFoundError(f"Plist not found: {path}")
        subprocess.run(["launchctl", "load", str(path)], check=True)
        return

    if backend == "systemd":
        path = _unit_path(service_name)
        if not path.exists():
            raise FileNotFoundError(f"Unit file not found: {path}")
        unit = service_label(service_name)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", unit], check=True)
        return

    raise RuntimeError(f"Unsupported platform for daemon management: {sys.platform}")


def unload_service(service_name: str) -> None:
    """Stop and disable a service on the current platform."""
    backend = service_backend()
    if backend == "launchd":
        path = _plist_path(service_name)
        if not path.exists():
            raise FileNotFoundError(f"Plist not found: {path}")
        subprocess.run(["launchctl", "unload", str(path)], check=True)
        return

    if backend == "systemd":
        unit = service_label(service_name)
        subprocess.run(["systemctl", "--user", "disable", "--now", unit], check=False)
        return

    raise RuntimeError(f"Unsupported platform for daemon management: {sys.platform}")


def _launchd_status(service_name: str) -> dict:
    label = service_label(service_name)
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
    return info


def _systemd_status(service_name: str) -> dict:
    label = service_label(service_name)
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            label,
            "--property=ActiveState,SubState,MainPID,ExecMainStatus",
            "--no-page",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"running": False, "label": label, "pid": None, "exit_code": None}

    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip()

    pid = None
    pid_raw = parsed.get("MainPID", "")
    if pid_raw.isdigit() and int(pid_raw) > 0:
        pid = int(pid_raw)

    exit_code = None
    exit_raw = parsed.get("ExecMainStatus", "")
    if exit_raw.isdigit():
        exit_code = int(exit_raw)

    active = parsed.get("ActiveState") == "active"
    return {"running": active, "label": label, "pid": pid, "exit_code": exit_code}


def service_status(service_name: str) -> dict:
    """Return running state, PID and exit code for a service."""
    backend = service_backend()
    if backend == "launchd":
        return _launchd_status(service_name)
    if backend == "systemd":
        return _systemd_status(service_name)
    return {
        "running": False,
        "label": service_label(service_name),
        "pid": None,
        "exit_code": None,
    }


def install_cron_daemon() -> Path:
    """Install and start the cron daemon service."""
    service_name = "claude-superpowers-cron"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    command = [VENV_PYTHON, "-m", "superpowers.cron_runner"]
    backend = service_backend()
    if backend == "launchd":
        log_path = str(LOG_DIR / "cron-daemon.log")
        content = generate_plist(
            service_name=service_name,
            command=command,
            keep_alive=True,
            working_directory=str(PROJECT_DIR),
            stdout_path=log_path,
            stderr_path=log_path,
        )
    elif backend == "systemd":
        content = generate_systemd_unit(
            service_name=service_name,
            command=command,
            keep_alive=True,
            working_directory=str(PROJECT_DIR),
        )
    else:
        raise RuntimeError(f"Unsupported platform for daemon management: {sys.platform}")

    path = install_plist(service_name, content)
    load_service(service_name)
    return path
