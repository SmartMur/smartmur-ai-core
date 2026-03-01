#!/usr/bin/env bash
set -euo pipefail

# Docker container monitor — health, status, and resource usage

ISSUES=0

if ! command -v docker &>/dev/null; then
    printf "\033[31m[!] docker command not found.\033[0m\n"
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    printf "\033[31m[!] Docker daemon is not running.\033[0m\n"
    exit 1
fi

# --- Container Status ---
printf "\n"
printf "%-28s %-15s %-20s %-10s\n" "CONTAINER" "STATE" "IMAGE" "STATUS"
printf "%-28s %-15s %-20s %-10s\n" "---------" "-----" "-----" "------"

while IFS=$'\t' read -r name state status image; do
    [ -z "$name" ] && continue

    if [[ "$state" == "running" ]]; then
        # Check for health status
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null || echo "none")
        if [[ "$health" == "unhealthy" ]]; then
            color="\033[31m"
            flag="UNHEALTHY"
            ISSUES=1
        elif [[ "$health" == "healthy" ]]; then
            color="\033[32m"
            flag="HEALTHY"
        else
            color="\033[32m"
            flag="RUNNING"
        fi
    elif [[ "$status" == *"Restarting"* ]]; then
        color="\033[31m"
        flag="RESTARTING"
        ISSUES=1
    else
        color="\033[33m"
        flag="$state"
        ISSUES=1
    fi

    # Truncate image name for display
    short_image=$(echo "$image" | sed 's/^.*\///' | cut -c1-18)
    printf "%-28s %-15s %-20s ${color}%-10s\033[0m\n" "$name" "$state" "$short_image" "$flag"
done < <(docker ps -a --format '{{.Names}}\t{{.State}}\t{{.Status}}\t{{.Image}}' 2>/dev/null)

CONTAINER_COUNT=$(docker ps -q 2>/dev/null | wc -l | tr -d ' ')

if [ "$CONTAINER_COUNT" -eq 0 ]; then
    printf "\033[90m  No containers running.\033[0m\n"
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

printf "\n"

if [ "$ISSUES" -eq 1 ]; then
    printf "\033[31m[!] One or more containers have issues.\033[0m\n"
    exit 1
else
    printf "\033[32m[OK] All %s containers healthy.\033[0m\n" "$CONTAINER_COUNT"
    exit 0
fi
