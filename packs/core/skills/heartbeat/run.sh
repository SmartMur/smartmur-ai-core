#!/usr/bin/env bash
set -euo pipefail

# Heartbeat monitor — ping and HTTP checks for key network services

source "$(dirname "$0")/../lib.sh"

status_init "All services are UP." "One or more services are DOWN."

declare -A HOSTS=(
    ["Switch"]="192.168.13.10"
    ["CGM"]="192.168.13.13"
    ["TrueNAS"]="192.168.13.69"
    ["PVE1"]="192.168.100.100"
    ["PVE2"]="192.168.100.200"
    ["Docker Host"]="192.168.30.117"
)

declare -A HTTP_SERVICES=(
    ["PVE1 API"]="https://192.168.100.100:8006"
    ["PVE2 API"]="https://192.168.100.200:8006"
    ["TrueNAS Web"]="https://192.168.13.69:443"
)

# Header
table_header "SERVICE:16" "ADDRESS:20" "TYPE:8" "STATUS:10"

# Ping checks
for name in "Switch" "CGM" "TrueNAS" "PVE1" "PVE2" "Docker Host"; do
    ip="${HOSTS[$name]}"
    if check_ping "$ip"; then
        status="UP"; status_pass
    else
        status="DOWN"; status_fail
    fi
    table_row_status 16 "$name" 20 "$ip" 8 "ICMP" 10 "$status"
done

# HTTP checks
for name in "PVE1 API" "PVE2 API" "TrueNAS Web"; do
    url="${HTTP_SERVICES[$name]}"
    if check_http "$url"; then
        status="UP"; status_pass
    else
        status="DOWN"; status_fail
    fi
    table_row_status 16 "$name" 20 "$url" 8 "HTTPS" 10 "$status"
done

status_summary
