#!/usr/bin/env bash
set -euo pipefail

# SSL certificate expiry checker

WARN_DAYS=30
WARNINGS=0

# Default domains if none provided
if [ $# -eq 0 ]; then
    DOMAINS=("google.com" "github.com")
else
    DOMAINS=("$@")
fi

printf "\n"
printf "%-30s %-12s %-24s %s\n" "DOMAIN" "DAYS LEFT" "EXPIRY DATE" "STATUS"
printf "%-30s %-12s %-24s %s\n" "------" "---------" "-----------" "------"

for domain in "${DOMAINS[@]}"; do
    # Get certificate expiry date
    EXPIRY=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null \
        | openssl x509 -noout -enddate 2>/dev/null \
        | sed 's/notAfter=//' || echo "")

    if [ -z "$EXPIRY" ]; then
        printf "%-30s %-12s %-24s \033[31m%-10s\033[0m\n" "$domain" "N/A" "CONNECT FAILED" "ERROR"
        WARNINGS=1
        continue
    fi

    # Calculate days until expiry
    EXPIRY_TS=$(date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY" +%s 2>/dev/null || \
                date -j -f "%b  %d %H:%M:%S %Y %Z" "$EXPIRY" +%s 2>/dev/null || echo "0")
    NOW_TS=$(date +%s)

    if [ "$EXPIRY_TS" -eq 0 ]; then
        printf "%-30s %-12s %-24s \033[33m%-10s\033[0m\n" "$domain" "?" "$EXPIRY" "PARSE ERR"
        continue
    fi

    DAYS_LEFT=$(( (EXPIRY_TS - NOW_TS) / 86400 ))

    if [ "$DAYS_LEFT" -lt 0 ]; then
        color="\033[31m"
        status="EXPIRED"
        WARNINGS=1
    elif [ "$DAYS_LEFT" -le "$WARN_DAYS" ]; then
        color="\033[33m"
        status="WARNING"
        WARNINGS=1
    else
        color="\033[32m"
        status="OK"
    fi

    printf "%-30s %-12s %-24s ${color}%-10s\033[0m\n" "$domain" "${DAYS_LEFT}d" "$EXPIRY" "$status"
done

printf "\n"

if [ "$WARNINGS" -eq 1 ]; then
    printf "\033[33m[!] One or more certificates need attention.\033[0m\n"
    exit 1
else
    printf "\033[32m[OK] All certificates valid for 30+ days.\033[0m\n"
    exit 0
fi
