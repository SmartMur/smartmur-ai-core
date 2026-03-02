#!/usr/bin/env python3
"""Deploy skill — pull latest code, rebuild containers, run health checks.

Exit codes:
    0 — success
    1 — health check failed
    2 — error (git, docker, pip, or test failure)
"""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Project root is two levels up from this script
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Venv paths
VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PIP = VENV_DIR / "bin" / "pip"
VENV_PYTEST = VENV_DIR / "bin" / "pytest"


def _run_cmd(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command without shell=True. Returns CompletedProcess."""
    return subprocess.run(
        args,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _notify_start() -> None:
    try:
        from superpowers.telegram_notify import notify_start
        notify_start("Deploying claude-superpowers")
    except Exception:
        pass


def _notify_done(message: str) -> None:
    try:
        from superpowers.telegram_notify import notify_done
        notify_done(message)
    except Exception:
        pass


def _notify_error(message: str, details: str = "") -> None:
    try:
        from superpowers.telegram_notify import notify_error
        notify_error(message, details=details)
    except Exception:
        pass


def _audit_log(action: str, detail: str, metadata: dict | None = None) -> None:
    try:
        from superpowers.audit import AuditLog
        audit = AuditLog()
        audit.log(action, detail, source="deploy-skill", metadata=metadata)
    except Exception:
        pass


def step_git_pull() -> tuple[bool, str]:
    """Pull latest code with fast-forward only."""
    print("==> Pulling latest code...")
    result = _run_cmd(["git", "pull", "--ff-only"], cwd=PROJECT_ROOT)
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"    FAILED: {msg}")
        return False, msg
    output = result.stdout.strip()
    print(f"    {output}")
    return True, output


def step_pip_install() -> tuple[bool, str]:
    """Install/update dependencies in the venv."""
    print("==> Installing Python dependencies...")
    pip_path = str(VENV_PIP)
    if not VENV_PIP.exists():
        pip_path = "pip"
    result = _run_cmd([pip_path, "install", "-e", ".[dev]"], cwd=PROJECT_ROOT)
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        # Truncate long pip output
        short = msg[:500] if len(msg) > 500 else msg
        print(f"    FAILED: {short}")
        return False, short
    print("    Dependencies installed.")
    return True, "ok"


def step_docker_build() -> tuple[bool, str]:
    """Build Docker containers without cache."""
    print("==> Building Docker containers...")
    compose_file = PROJECT_ROOT / "docker-compose.prod.yaml"
    if not compose_file.exists():
        compose_file = PROJECT_ROOT / "docker-compose.yaml"
    result = _run_cmd(
        ["docker", "compose", "-f", str(compose_file), "build", "--no-cache"],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        short = msg[:500] if len(msg) > 500 else msg
        print(f"    FAILED: {short}")
        return False, short
    print("    Docker build complete.")
    return True, "ok"


def step_docker_up() -> tuple[bool, str]:
    """Start Docker containers in detached mode."""
    print("==> Starting Docker services...")
    compose_file = PROJECT_ROOT / "docker-compose.prod.yaml"
    if not compose_file.exists():
        compose_file = PROJECT_ROOT / "docker-compose.yaml"
    result = _run_cmd(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        short = msg[:500] if len(msg) > 500 else msg
        print(f"    FAILED: {short}")
        return False, short
    print("    Services started.")
    return True, "ok"


def step_health_check(url: str = "http://localhost:8200/health", retries: int = 3) -> tuple[bool, str]:
    """Check dashboard health endpoint."""
    print(f"==> Health check: {url}")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode()
                if resp.status == 200:
                    print(f"    OK (attempt {attempt})")
                    return True, body
        except Exception as exc:
            print(f"    Attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                import time
                time.sleep(2)
    return False, "health check failed after retries"


def step_quick_tests() -> tuple[bool, str]:
    """Run quick test suite — stop on first failure."""
    print("==> Running quick test suite...")
    pytest_path = str(VENV_PYTEST)
    if not VENV_PYTEST.exists():
        pytest_path = "pytest"
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run(
        [
            pytest_path, "tests/",
            "--ignore=tests/test_telegram_concurrency.py",
            "-k", "not test_vault",
            "-x", "--tb=short", "-q",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        # Include last 10 lines for context
        lines = output.splitlines()
        summary = "\n".join(lines[-10:]) if len(lines) > 10 else output
        print(f"    FAILED:\n    {summary}")
        return False, summary
    print(f"    {output.splitlines()[-1] if output else 'Tests passed.'}")
    return True, output


def deploy() -> int:
    """Run the full deployment pipeline. Returns exit code."""
    _notify_start()
    _audit_log("deploy.start", "deployment initiated")

    # Step 1: Git pull
    ok, detail = step_git_pull()
    if not ok:
        _notify_error("Git pull failed", details=detail)
        _audit_log("deploy.fail", "git pull failed", metadata={"error": detail})
        return 2

    # Step 2: Pip install
    ok, detail = step_pip_install()
    if not ok:
        _notify_error("Pip install failed", details=detail)
        _audit_log("deploy.fail", "pip install failed", metadata={"error": detail})
        return 2

    # Step 3: Docker build
    ok, detail = step_docker_build()
    if not ok:
        _notify_error("Docker build failed", details=detail)
        _audit_log("deploy.fail", "docker build failed", metadata={"error": detail})
        return 2

    # Step 4: Docker up
    ok, detail = step_docker_up()
    if not ok:
        _notify_error("Docker up failed", details=detail)
        _audit_log("deploy.fail", "docker up failed", metadata={"error": detail})
        return 2

    # Step 5: Health check
    ok, detail = step_health_check()
    if not ok:
        _notify_error("Health check failed", details=detail)
        _audit_log("deploy.fail", "health check failed", metadata={"error": detail})
        return 1

    # Step 6: Quick tests
    ok, detail = step_quick_tests()
    if not ok:
        _notify_error("Quick tests failed", details=detail)
        _audit_log("deploy.fail", "quick tests failed", metadata={"error": detail})
        return 2

    _notify_done("claude-superpowers deployed successfully")
    _audit_log("deploy.success", "deployment completed successfully")
    print("\n==> Deployment complete.")
    return 0


if __name__ == "__main__":
    sys.exit(deploy())
