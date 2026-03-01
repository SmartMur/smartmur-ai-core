#!/usr/bin/env bash
set -euo pipefail

# Backup status checker — Time Machine + Docker volumes

WARNINGS=0
NOW=$(date +%s)
THRESHOLD=$((24 * 60 * 60))  # 24 hours in seconds

printf "\n"
printf "%-24s %-12s %-20s %s\n" "BACKUP SOURCE" "TYPE" "LAST BACKUP" "STATUS"
printf "%-24s %-12s %-20s %s\n" "-------------" "----" "-----------" "------"

# --- Time Machine ---
if command -v tmutil &>/dev/null; then
    LATEST=$(tmutil latestbackup 2>/dev/null || echo "")
    if [ -n "$LATEST" ]; then
        # Extract timestamp from backup path (format: YYYY-MM-DD-HHMMSS)
        BACKUP_DATE=$(basename "$LATEST" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}' || echo "")
        if [ -n "$BACKUP_DATE" ]; then
            FORMATTED=$(echo "$BACKUP_DATE" | sed 's/\([0-9]\{4\}\)-\([0-9]\{2\}\)-\([0-9]\{2\}\)-\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3 \4:\5:\6/')
            BACKUP_TS=$(date -j -f "%Y-%m-%d %H:%M:%S" "$FORMATTED" +%s 2>/dev/null || echo "0")
            AGE=$(( NOW - BACKUP_TS ))
            if [ "$AGE" -gt "$THRESHOLD" ]; then
                status="WARNING"
                color="\033[33m"
                WARNINGS=1
            else
                status="OK"
                color="\033[32m"
            fi
            printf "%-24s %-12s %-20s ${color}%-10s\033[0m\n" "Time Machine" "TM" "$FORMATTED" "$status"
        else
            printf "%-24s %-12s %-20s \033[33m%-10s\033[0m\n" "Time Machine" "TM" "$LATEST" "UNKNOWN"
        fi
    else
        printf "%-24s %-12s %-20s \033[31m%-10s\033[0m\n" "Time Machine" "TM" "No backup found" "MISSING"
        WARNINGS=1
    fi
else
    printf "%-24s %-12s %-20s \033[90m%-10s\033[0m\n" "Time Machine" "TM" "N/A" "SKIPPED"
fi

# --- Docker Volumes ---
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    printf "\n"
    printf "%-32s %-12s %s\n" "DOCKER VOLUME" "DRIVER" "SIZE"
    printf "%-32s %-12s %s\n" "-------------" "------" "----"

    while IFS=$'\t' read -r vname driver mount; do
        [ -z "$vname" ] && continue
        size="unknown"
        if [ -n "$mount" ] && [ -d "$mount" ]; then
            size=$(du -sh "$mount" 2>/dev/null | cut -f1 || echo "unknown")
        fi
        printf "%-32s %-12s %s\n" "$vname" "$driver" "$size"
    done < <(docker volume ls --format '{{.Name}}\t{{.Driver}}\t{{.Mountpoint}}' 2>/dev/null)
else
    printf "\n\033[90mDocker not available — skipping volume check.\033[0m\n"
fi

printf "\n"

if [ "$WARNINGS" -eq 1 ]; then
    printf "\033[33m[!] One or more backups are stale or missing.\033[0m\n"
    exit 1
else
    printf "\033[32m[OK] All backups are current.\033[0m\n"
    exit 0
fi
