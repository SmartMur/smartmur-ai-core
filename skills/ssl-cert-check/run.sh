#!/usr/bin/env bash
set -euo pipefail

# SSL certificate expiry checker

source "$(dirname "$0")/../lib.sh"

WARN_DAYS=30

status_init "All certificates valid for 30+ days." "One or more certificates need attention."

# Default domains if none provided
if [ $# -eq 0 ]; then
    DOMAINS=("google.com" "github.com")
else
    DOMAINS=("$@")
fi

table_header "DOMAIN:30" "DAYS LEFT:12" "EXPIRY DATE:24" "STATUS:10"

for domain in "${DOMAINS[@]}"; do
    # Get certificate expiry date
    EXPIRY=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null \
        | openssl x509 -noout -enddate 2>/dev/null \
        | sed 's/notAfter=//' || echo "")

    if [ -z "$EXPIRY" ]; then
        table_row_status 30 "$domain" 12 "N/A" 24 "CONNECT FAILED" 10 "ERROR"
        status_fail
        continue
    fi

    # Calculate days until expiry
    EXPIRY_TS=$(date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY" +%s 2>/dev/null || \
                date -j -f "%b  %d %H:%M:%S %Y %Z" "$EXPIRY" +%s 2>/dev/null || echo "0")
    NOW_TS=$(date +%s)

    if [ "$EXPIRY_TS" -eq 0 ]; then
        table_row_status 30 "$domain" 12 "?" 24 "$EXPIRY" 10 "UNKNOWN"
        continue
    fi

    DAYS_LEFT=$(( (EXPIRY_TS - NOW_TS) / 86400 ))

    if [ "$DAYS_LEFT" -lt 0 ]; then
        status="EXPIRED"; status_fail
    elif [ "$DAYS_LEFT" -le "$WARN_DAYS" ]; then
        status="WARNING"; status_fail
    else
        status="OK"; status_pass
    fi

    table_row_status 30 "$domain" 12 "${DAYS_LEFT}d" 24 "$EXPIRY" 10 "$status"
done

status_summary
