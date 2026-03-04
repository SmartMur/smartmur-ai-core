#!/usr/bin/env bash
set -euo pipefail

# Docker container monitor — health, status, and resource usage

source "$(dirname "$0")/../lib.sh"

check_command docker "docker command not found."

if ! docker info &>/dev/null 2>&1; then
    error "[!] Docker daemon is not running."
    exit 1
fi

status_init "All containers healthy." "One or more containers have issues."

# --- Container Status ---
table_header "CONTAINER:28" "STATE:15" "IMAGE:20" "STATUS:10"

while IFS=$'\t' read -r name state status image; do
    [ -z "$name" ] && continue

    if [[ "$state" == "running" ]]; then
        # Check for health status
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null || echo "none")
        if [[ "$health" == "unhealthy" ]]; then
            flag="UNHEALTHY"; status_fail
        elif [[ "$health" == "healthy" ]]; then
            flag="HEALTHY"; status_pass
        else
            flag="RUNNING"; status_pass
        fi
    elif [[ "$status" == *"Restarting"* ]]; then
        flag="RESTARTING"; status_fail
    else
        flag="$state"; status_fail
    fi

    # Truncate image name for display
    short_image=$(echo "$image" | sed 's/^.*\///' | cut -c1-18)
    table_row_status 28 "$name" 15 "$state" 20 "$short_image" 10 "$flag"
done < <(docker ps -a --format '{{.Names}}\t{{.State}}\t{{.Status}}\t{{.Image}}' 2>/dev/null)

CONTAINER_COUNT=$(docker ps -q 2>/dev/null | wc -l | tr -d ' ')

if [ "$CONTAINER_COUNT" -eq 0 ]; then
    dim "  No containers running."
else
    # --- Resource Usage ---
    printf "\n"
    printf "%-28s %-10s %-16s %-16s %-10s\n" "CONTAINER" "CPU %" "MEM USAGE" "MEM LIMIT" "MEM %"
    printf "%-28s %-10s %-16s %-16s %-10s\n" "---------" "-----" "---------" "---------" "-----"

    while IFS=$'\t' read -r name cpu mem_usage mem_limit mem_pct; do
        [ -z "$name" ] && continue
        printf "%-28s %-10s %-16s %-16s %-10s\n" "$name" "$cpu" "$mem_usage" "$mem_limit" "$mem_pct"
    done < <(docker stats --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}' 2>/dev/null | sed 's| / |\t|')
fi

# Override summary to include count
printf "\n"
if status_has_failures; then
    error "[!] One or more containers have issues."
    exit 1
else
    success "[OK] All ${CONTAINER_COUNT} containers healthy."
    exit 0
fi
