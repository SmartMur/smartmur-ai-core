#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
WATCHDOG="$PROJECT_DIR/superpowers/container_watchdog.py"
SERVICE="container-watchdog.service"

# Source .env for Telegram credentials if available
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

usage() {
    echo "Container Watchdog — real-time Docker monitoring with Telegram alerts"
    echo ""
    echo "Usage: run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  status      Show watched containers and their current state"
    echo "  start       Start the watchdog systemd service"
    echo "  stop        Stop the watchdog systemd service"
    echo "  restart     Restart the watchdog systemd service"
    echo "  logs        Show watchdog service logs"
    echo "  list        List all watched containers"
    echo "  test-alert  Send a test Telegram alert"
    echo "  run         Run watchdog in foreground (for debugging)"
}

cmd="${1:-status}"

case "$cmd" in
    status)
        echo "=== Watchdog Service ==="
        systemctl --user status "$SERVICE" --no-pager 2>/dev/null || echo "Service not running"
        echo ""
        echo "=== Container Status ==="
        cd "$PROJECT_DIR" && python3 -m superpowers.container_watchdog status
        ;;
    start)
        systemctl --user start "$SERVICE"
        echo "Watchdog started"
        systemctl --user status "$SERVICE" --no-pager
        ;;
    stop)
        systemctl --user stop "$SERVICE"
        echo "Watchdog stopped"
        ;;
    restart)
        systemctl --user restart "$SERVICE"
        echo "Watchdog restarted"
        systemctl --user status "$SERVICE" --no-pager
        ;;
    logs)
        journalctl --user -u "$SERVICE" --no-pager -n "${2:-50}"
        ;;
    list)
        cd "$PROJECT_DIR" && python3 -m superpowers.container_watchdog list
        ;;
    test-alert)
        cd "$PROJECT_DIR" && python3 -m superpowers.container_watchdog test-alert "${2:-test-container}"
        ;;
    run)
        cd "$PROJECT_DIR" && exec python3 -m superpowers.container_watchdog run
        ;;
    *)
        usage
        exit 1
        ;;
esac
