#!/usr/bin/env bash
set -euo pipefail

# Heartbeat monitor — ping and HTTP checks for key network services

FAILED=0

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
printf "\n"
printf "%-16s %-20s %-8s %-10s\n" "SERVICE" "ADDRESS" "TYPE" "STATUS"
printf "%-16s %-20s %-8s %-10s\n" "-------" "-------" "----" "------"

# Ping checks
for name in "Switch" "CGM" "TrueNAS" "PVE1" "PVE2" "Docker Host"; do
    ip="${HOSTS[$name]}"
    if ping -c 1 -W 2 "$ip" &>/dev/null; then
        status="UP"
        color="\033[32m"
    else
        status="DOWN"
        color="\033[31m"
        FAILED=1
    fi
    printf "%-16s %-20s %-8s ${color}%-10s\033[0m\n" "$name" "$ip" "ICMP" "$status"
done

# HTTP checks
for name in "PVE1 API" "PVE2 API" "TrueNAS Web"; do
    url="${HTTP_SERVICES[$name]}"
    if curl -sk --connect-timeout 5 --max-time 5 -o /dev/null -w '' "$url" 2>/dev/null; then
        status="UP"
        color="\033[32m"
    else
        status="DOWN"
        color="\033[31m"
        FAILED=1
    fi
    printf "%-16s %-20s %-8s ${color}%-10s\033[0m\n" "$name" "$url" "HTTPS" "$status"
done

printf "\n"

if [ "$FAILED" -eq 1 ]; then
    printf "\033[31m[!] One or more services are DOWN.\033[0m\n"
    exit 1
else
    printf "\033[32m[OK] All services are UP.\033[0m\n"
    exit 0
fi
