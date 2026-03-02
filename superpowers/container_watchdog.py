"""Container Watchdog — real-time Docker monitoring with Telegram alerts.

Two monitoring mechanisms:
1. Real-time: listens to `docker events` for die/stop events — alerts within seconds
2. Hourly sweep: checks all expected containers are running via `docker ps`

Deduplication prevents alert floods from restart loops.
Grace period ignores containers with restart policies that will auto-recover.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from superpowers.telegram_notify import notify

log = logging.getLogger("container-watchdog")

# ── Configuration ────────────────────────────────────────────────────

# Containers we expect to be running. Keyed by compose project dir.
WATCHED_CONTAINERS: dict[str, list[str]] = {
    "/home/ray/docker/home_media": [
        "gluetun", "qbittorrent", "radarr", "sonarr", "lidarr",
        "prowlarr", "bazarr", "plex", "jellyfin", "overseerr", "jellyseerr",
    ],
    "/home/ray/claude-superpowers": [
        "claude-superpowers-redis-1",
        "claude-superpowers-msg-gateway-1",
        "claude-superpowers-dashboard-1",
    ],
    "/home/ray/docker/npm": ["nginx-proxy-manager"],
    "/home/ray/docker/cloudflared": ["cloudflared-cloudflared-1"],
    "/home/ray/docker/dockhand": ["dockhand"],
}

# Flat set for quick lookup
ALL_WATCHED: set[str] = set()
for _containers in WATCHED_CONTAINERS.values():
    ALL_WATCHED.update(_containers)

# Cooldown: don't re-alert for same container within this many seconds
ALERT_COOLDOWN_SECS = 1800  # 30 minutes

# Grace period: wait this long after a die/stop event before alerting,
# giving the restart policy time to bring the container back
GRACE_PERIOD_SECS = 30

# Hourly sweep interval
SWEEP_INTERVAL_SECS = 3600


# ── State ────────────────────────────────────────────────────────────

@dataclass
class WatchdogState:
    """Tracks alert cooldowns and pending grace-period checks."""
    last_alert: dict[str, float] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def can_alert(self, container: str) -> bool:
        with self.lock:
            last = self.last_alert.get(container, 0)
            return (time.monotonic() - last) >= ALERT_COOLDOWN_SECS

    def record_alert(self, container: str) -> None:
        with self.lock:
            self.last_alert[container] = time.monotonic()

    def clear_alert(self, container: str) -> None:
        """Clear cooldown when container recovers — allows immediate re-alert if it dies again."""
        with self.lock:
            self.last_alert.pop(container, None)


state = WatchdogState()


# ── Helpers ──────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _is_container_running(name: str) -> bool:
    """Check if a container is currently running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", name],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip().lower() == "true"
    except Exception:
        return False


def _has_restart_policy(name: str) -> bool:
    """Check if container has a restart policy (not 'no')."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.HostConfig.RestartPolicy.Name}}", name],
            capture_output=True, text=True, timeout=10,
        )
        policy = result.stdout.strip().lower()
        return policy not in ("", "no")
    except Exception:
        return False


def _get_running_containers() -> set[str]:
    """Get names of all currently running containers."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return set()
        return {line.strip() for line in result.stdout.strip().splitlines() if line.strip()}
    except Exception:
        return set()


def _container_exists(name: str) -> bool:
    """Check if container exists (running or stopped)."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Name}}", name],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


# ── Alert functions ──────────────────────────────────────────────────

def send_down_alert(container: str, reason: str = "stopped") -> None:
    """Send a Telegram alert that a container is down."""
    if not state.can_alert(container):
        log.debug("Skipping alert for %s (cooldown)", container)
        return

    msg = (
        f"*CONTAINER DOWN*\n"
        f"`{container}` is {reason}\n"
        f"_{_ts()}_"
    )
    if notify(msg):
        state.record_alert(container)
        log.warning("Alert sent: %s is %s", container, reason)
    else:
        log.error("Failed to send alert for %s", container)


def send_recovery_alert(container: str) -> None:
    """Send a Telegram notification that a container has recovered."""
    state.clear_alert(container)
    msg = (
        f"*CONTAINER RECOVERED*\n"
        f"`{container}` is back up\n"
        f"_{_ts()}_"
    )
    notify(msg)
    log.info("Recovery alert sent: %s", container)


def send_sweep_alert(down_containers: list[str]) -> None:
    """Send a summary alert for all down containers found during hourly sweep."""
    names = "\n".join(f"  - `{c}`" for c in sorted(down_containers))
    msg = (
        f"*WATCHDOG SWEEP — {len(down_containers)} container(s) down*\n"
        f"{names}\n"
        f"_{_ts()}_"
    )
    notify(msg)
    log.warning("Sweep alert: %d containers down", len(down_containers))


# ── Real-time event listener ────────────────────────────────────────

def _handle_event(container: str, event_type: str) -> None:
    """Handle a docker die/stop event with grace period."""
    if container not in ALL_WATCHED:
        return

    log.info("Event: %s %s — waiting %ds grace period", container, event_type, GRACE_PERIOD_SECS)

    def _check_after_grace():
        time.sleep(GRACE_PERIOD_SECS)
        if _is_container_running(container):
            log.info("%s recovered within grace period", container)
            return
        send_down_alert(container, reason=f"{event_type} (not recovered after {GRACE_PERIOD_SECS}s)")

    t = threading.Thread(target=_check_after_grace, daemon=True)
    t.start()


def event_listener(stop_event: threading.Event) -> None:
    """Listen to docker events for container die/stop. Runs in a thread."""
    log.info("Starting docker event listener")
    while not stop_event.is_set():
        try:
            proc = subprocess.Popen(
                [
                    "docker", "events",
                    "--filter", "event=die",
                    "--filter", "event=stop",
                    "--filter", "event=start",
                    "--filter", "type=container",
                    "--format", "{{.Actor.Attributes.name}} {{.Action}}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for line in iter(proc.stdout.readline, ""):
                if stop_event.is_set():
                    proc.terminate()
                    return
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                container, action = parts[0], parts[1]

                if action == "start" and container in ALL_WATCHED:
                    log.info("Event: %s started", container)
                    send_recovery_alert(container)
                elif action in ("die", "stop"):
                    _handle_event(container, action)

            # If we get here, docker events exited unexpectedly
            if proc.poll() is not None and not stop_event.is_set():
                log.warning("docker events process exited (rc=%s), restarting in 5s", proc.returncode)
                time.sleep(5)

        except Exception as e:
            log.error("Event listener error: %s, restarting in 10s", e)
            time.sleep(10)


# ── Hourly sweep ─────────────────────────────────────────────────────

def hourly_sweep(stop_event: threading.Event) -> None:
    """Periodically check all expected containers are running."""
    log.info("Starting hourly sweep (interval=%ds)", SWEEP_INTERVAL_SECS)
    while not stop_event.is_set():
        stop_event.wait(SWEEP_INTERVAL_SECS)
        if stop_event.is_set():
            return

        log.info("Running sweep...")
        running = _get_running_containers()
        down = []
        for container in sorted(ALL_WATCHED):
            if container not in running:
                down.append(container)
                # Send individual alerts (respects cooldown)
                send_down_alert(container, reason="not running (sweep)")

        if down:
            # Also send a summary if there are multiple
            if len(down) >= 2:
                send_sweep_alert(down)
            log.warning("Sweep found %d down: %s", len(down), ", ".join(down))
        else:
            log.info("Sweep complete: all %d watched containers running", len(ALL_WATCHED))


# ── Status reporting ─────────────────────────────────────────────────

def get_status() -> dict:
    """Get current watchdog status as a dict."""
    running = _get_running_containers()
    down = sorted(c for c in ALL_WATCHED if c not in running)
    up = sorted(c for c in ALL_WATCHED if c in running)
    return {
        "watched": len(ALL_WATCHED),
        "up": len(up),
        "down": len(down),
        "down_containers": down,
        "up_containers": up,
        "timestamp": _ts(),
    }


def print_status() -> None:
    """Print human-readable status to stdout."""
    status = get_status()
    print(f"Container Watchdog Status ({status['timestamp']})")
    print(f"  Watched: {status['watched']}")
    print(f"  Up:      {status['up']}")
    print(f"  Down:    {status['down']}")
    if status["down_containers"]:
        print("\n  DOWN:")
        for c in status["down_containers"]:
            print(f"    - {c}")
    else:
        print("\n  All containers running.")


# ── Main daemon ──────────────────────────────────────────────────────

def run_daemon() -> None:
    """Main entry point — starts event listener + hourly sweep."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log.info("Container watchdog starting — monitoring %d containers", len(ALL_WATCHED))

    # Startup notification
    notify(f"*Container Watchdog started*\nMonitoring {len(ALL_WATCHED)} containers\n_{_ts()}_")

    stop_event = threading.Event()

    # Start event listener thread
    event_thread = threading.Thread(target=event_listener, args=(stop_event,), daemon=True, name="event-listener")
    event_thread.start()

    # Start hourly sweep thread
    sweep_thread = threading.Thread(target=hourly_sweep, args=(stop_event,), daemon=True, name="hourly-sweep")
    sweep_thread.start()

    # Initial sweep — check status right away on startup
    running = _get_running_containers()
    down = [c for c in sorted(ALL_WATCHED) if c not in running]
    if down:
        log.warning("Startup check found %d down: %s", len(down), ", ".join(down))
        for c in down:
            send_down_alert(c, reason="not running (startup check)")
        if len(down) >= 2:
            send_sweep_alert(down)
    else:
        log.info("Startup check: all %d containers running", len(ALL_WATCHED))

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        stop_event.set()
        event_thread.join(timeout=5)
        sweep_thread.join(timeout=5)
        notify(f"*Container Watchdog stopped*\n_{_ts()}_")
        log.info("Watchdog stopped")


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point with subcommands."""
    args = sys.argv[1:]
    cmd = args[0] if args else "run"

    if cmd == "run":
        run_daemon()
    elif cmd == "status":
        print_status()
    elif cmd == "list":
        for project, containers in sorted(WATCHED_CONTAINERS.items()):
            print(f"\n{project}:")
            for c in containers:
                print(f"  - {c}")
    elif cmd == "test-alert":
        name = args[1] if len(args) > 1 else "test-container"
        send_down_alert(name, reason="test alert")
        print(f"Test alert sent for '{name}'")
    else:
        print("Usage: container_watchdog.py [run|status|list|test-alert [name]]")
        sys.exit(1)


if __name__ == "__main__":
    main()
