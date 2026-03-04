#!/usr/bin/env bash
# skills/lib.sh — Shared library for skill shell scripts
# Source this from any skill: source "$(dirname "$0")/../lib.sh"
#
# Provides:
#   - Color output:    info, warn, error, success, dim
#   - Table helpers:   table_header, table_row, table_sep
#   - Status tracking: status_init, status_fail, status_summary
#   - Check helpers:   check_ping, check_http, check_command
#   - Environment:     resolve_dirs, load_env
#   - Timing:          timer_start, timer_elapsed

set -euo pipefail

# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------

# SKILL_DIR  — directory of the calling script
# PROJECT_DIR — root of the claude-superpowers repo
resolve_dirs() {
    SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}")" && pwd)"
    PROJECT_DIR="$(cd "$SKILL_DIR/../.." && pwd)"
}

# Load .env from PROJECT_DIR (call resolve_dirs first)
load_env() {
    resolve_dirs
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        set -a
        # shellcheck disable=SC1091
        source "$PROJECT_DIR/.env" 2>/dev/null || true
        set +a
    fi
}

# ---------------------------------------------------------------------------
# Color helpers  (auto-disable when stdout is not a terminal)
# ---------------------------------------------------------------------------

if [[ -t 1 ]] || [[ "${FORCE_COLOR:-0}" == "1" ]]; then
    _C_RED='\033[31m'
    _C_GREEN='\033[32m'
    _C_YELLOW='\033[33m'
    _C_DIM='\033[90m'
    _C_RESET='\033[0m'
else
    _C_RED=''
    _C_GREEN=''
    _C_YELLOW=''
    _C_DIM=''
    _C_RESET=''
fi

# Colored output to stderr (for messages) — newline appended
info()    { printf "${_C_RESET}%s${_C_RESET}\n" "$*"; }
warn()    { printf "${_C_YELLOW}%s${_C_RESET}\n" "$*"; }
error()   { printf "${_C_RED}%s${_C_RESET}\n" "$*"; }
success() { printf "${_C_GREEN}%s${_C_RESET}\n" "$*"; }
dim()     { printf "${_C_DIM}%s${_C_RESET}\n" "$*"; }

# Return raw color codes for inline use in printf
color_for_status() {
    case "$1" in
        UP|OK|HEALTHY|RUNNING|ok)   echo -ne "$_C_GREEN" ;;
        DOWN|EXPIRED|UNHEALTHY|ERROR|MISSING|RESTARTING|down|error)
                                     echo -ne "$_C_RED" ;;
        WARNING|STALE|UNKNOWN|SKIPPED)
                                     echo -ne "$_C_YELLOW" ;;
        *)                           echo -ne "$_C_DIM" ;;
    esac
}

color_reset() { echo -ne "$_C_RESET"; }

# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

# Print a formatted table header row.
# Usage: table_header "COL1:16" "COL2:20" "COL3:8" "COL4:10"
#   — each arg is "LABEL:WIDTH"
table_header() {
    local fmt="" sep_fmt="" labels=() seps=()
    for col in "$@"; do
        local label="${col%%:*}"
        local width="${col##*:}"
        fmt+="%-${width}s "
        labels+=("$label")
        seps+=("$(printf '%0.s-' $(seq 1 "${#label}"))")
    done
    printf "\n"
    # shellcheck disable=SC2059
    printf "${fmt}\n" "${labels[@]}"
    # shellcheck disable=SC2059
    printf "${fmt}\n" "${seps[@]}"
}

# Print a table row with optional color on the last column.
# Usage: table_row "val1:16" "val2:20" "val3:8" "val4:10:STATUS"
#   — last arg can have a third ":STATUS" field to auto-color that cell
table_row() {
    local args=("$@")
    local count=${#args[@]}
    local out=""

    for i in "${!args[@]}"; do
        local parts="${args[$i]}"
        # Split on ':'
        IFS=':' read -r val width status <<< "$parts"
        status="${status:-}"

        if [[ -n "$status" ]]; then
            # Colored cell
            out+="$(color_for_status "$status")$(printf "%-${width}s" "$val")$(color_reset) "
        else
            out+="$(printf "%-${width}s" "$val") "
        fi
    done

    echo -e "$out"
}

# Simpler: print a row where just the last column is colored by status.
# Usage: table_row_colored WIDTH1 VAL1 WIDTH2 VAL2 ... LAST_WIDTH LAST_VAL STATUS
# This is an alternative API closer to what the original scripts used.
# Example: table_row_status 16 "PVE1" 20 "192.168.100.100" 8 "ICMP" 10 "UP"
#   — the last value is auto-colored based on its content
table_row_status() {
    local args=("$@")
    local count=${#args[@]}
    # Last arg is the status value, second-to-last is its width
    local status="${args[$((count-1))]}"
    local out=""

    local i=0
    while [[ $i -lt $((count - 2)) ]]; do
        local width="${args[$i]}"
        local val="${args[$((i+1))]}"
        out+="$(printf "%-${width}s" "$val") "
        i=$((i + 2))
    done

    # Last column with color
    local last_width="${args[$((count-2))]}"
    out+="$(color_for_status "$status")$(printf "%-${last_width}s" "$status")$(color_reset)"
    echo -e "$out"
}

# ---------------------------------------------------------------------------
# Status / failure tracking
# ---------------------------------------------------------------------------

_LIB_FAIL_COUNT=0
_LIB_PASS_COUNT=0
_LIB_STATUS_LABEL_OK="All checks passed."
_LIB_STATUS_LABEL_FAIL="One or more checks failed."

# Initialize status tracking with custom labels
# Usage: status_init "All services are UP." "One or more services are DOWN."
status_init() {
    _LIB_FAIL_COUNT=0
    _LIB_PASS_COUNT=0
    _LIB_STATUS_LABEL_OK="${1:-All checks passed.}"
    _LIB_STATUS_LABEL_FAIL="${2:-One or more checks failed.}"
}

status_pass() { _LIB_PASS_COUNT=$((_LIB_PASS_COUNT + 1)); }
status_fail() { _LIB_FAIL_COUNT=$((_LIB_FAIL_COUNT + 1)); }
status_has_failures() { [[ $_LIB_FAIL_COUNT -gt 0 ]]; }
status_counts() { echo "${_LIB_PASS_COUNT} passed, ${_LIB_FAIL_COUNT} failed"; }

# Print summary and exit with appropriate code.
# Usage: status_summary
status_summary() {
    printf "\n"
    if status_has_failures; then
        error "[!] ${_LIB_STATUS_LABEL_FAIL}"
        exit 1
    else
        success "[OK] ${_LIB_STATUS_LABEL_OK}"
        exit 0
    fi
}

# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------

# Ping a host. Returns 0 on success, 1 on failure.
# Usage: check_ping 192.168.1.1 [timeout_seconds]
check_ping() {
    local host="$1"
    local timeout="${2:-2}"
    ping -c 1 -W "$timeout" "$host" &>/dev/null
}

# HTTP(S) connectivity check. Returns 0 on 2xx/3xx, 1 otherwise.
# Usage: check_http "https://example.com:8006" [timeout_seconds]
check_http() {
    local url="$1"
    local timeout="${2:-5}"
    local code
    code=$(curl -sk --connect-timeout "$timeout" --max-time "$timeout" \
        -o /dev/null -w "%{http_code}" "$url" 2>/dev/null) || code="000"
    [[ "$code" =~ ^[23] ]]
}

# Check that a command exists.
# Usage: check_command docker "docker command not found"
check_command() {
    local cmd="$1"
    local msg="${2:-$cmd command not found.}"
    if ! command -v "$cmd" &>/dev/null; then
        error "[!] $msg"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

_LIB_TIMER_START=""

timer_start() { _LIB_TIMER_START=$(date +%s); }

# Print elapsed time since timer_start. Returns "Xs" string.
timer_elapsed() {
    local now
    now=$(date +%s)
    local elapsed=$(( now - _LIB_TIMER_START ))
    if [[ $elapsed -ge 60 ]]; then
        echo "$((elapsed / 60))m $((elapsed % 60))s"
    else
        echo "${elapsed}s"
    fi
}

# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

# Run a command safely, capturing output. Prints output on success, "ERROR" on failure.
safe_run() {
    local output
    output=$("$@" 2>&1) && echo "$output" || echo "ERROR"
}

# Timestamp in UTC
timestamp_utc() { date -u '+%Y-%m-%d %H:%M UTC'; }
