#!/usr/bin/env bash
set -euo pipefail

# Backup status checker — Time Machine + Docker volumes

source "$(dirname "$0")/../lib.sh"

status_init "All backups are current." "One or more backups are stale or missing."

NOW=$(date +%s)
THRESHOLD=$((24 * 60 * 60))  # 24 hours in seconds

table_header "BACKUP SOURCE:24" "TYPE:12" "LAST BACKUP:20" "STATUS:10"

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
                status="WARNING"; status_fail
            else
                status="OK"; status_pass
            fi
            table_row_status 24 "Time Machine" 12 "TM" 20 "$FORMATTED" 10 "$status"
        else
            table_row_status 24 "Time Machine" 12 "TM" 20 "$LATEST" 10 "UNKNOWN"
        fi
    else
        table_row_status 24 "Time Machine" 12 "TM" 20 "No backup found" 10 "MISSING"
        status_fail
    fi
else
    table_row_status 24 "Time Machine" 12 "TM" 20 "N/A" 10 "SKIPPED"
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
    dim "Docker not available — skipping volume check."
fi

status_summary
