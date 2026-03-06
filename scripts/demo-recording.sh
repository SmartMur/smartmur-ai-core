#!/usr/bin/env bash
# demo-recording.sh — Simulates a terminal demo session for README recordings.
#
# Usage:
#   ./scripts/demo-recording.sh              # Run demo interactively
#   ./scripts/demo-recording.sh --record     # Auto-record with asciinema or script
#
# Designed for asciinema recordings or plain script(1) captures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAW="$PROJECT_DIR/.venv/bin/claw"
CAST_FILE="$PROJECT_DIR/assets/demo/demo.cast"
TYPESCRIPT_FILE="$PROJECT_DIR/assets/demo/demo.typescript"

# Typing speed simulation (seconds between characters)
CHAR_DELAY=0.03
LINE_DELAY=1.5

# --- Helper functions ---

type_command() {
    local cmd="$1"
    printf "\n\033[1;32m$ \033[0m"
    for (( i=0; i<${#cmd}; i++ )); do
        printf "%s" "${cmd:$i:1}"
        sleep "$CHAR_DELAY"
    done
    printf "\n"
    sleep 0.3
}

show_comment() {
    local comment="$1"
    printf "\033[1;34m# %s\033[0m\n" "$comment"
    sleep 0.5
}

run_command() {
    local comment="$1"
    local cmd="$2"
    show_comment "$comment"
    type_command "$cmd"
    eval "$cmd" 2>&1 || echo "(command returned non-zero — this is fine for demo purposes)"
    sleep "$LINE_DELAY"
}

run_claw() {
    local comment="$1"
    local subcmd="$2"
    run_command "$comment" "$CLAW $subcmd"
}

# --- Recording wrapper ---

record_demo() {
    if command -v asciinema &>/dev/null; then
        echo "Recording with asciinema to $CAST_FILE ..."
        mkdir -p "$(dirname "$CAST_FILE")"
        asciinema rec --command "$0" --title "Claw CLI Demo" --overwrite "$CAST_FILE"
        echo "Recording saved to $CAST_FILE"
        echo "Play it back: asciinema play $CAST_FILE"
        echo "Upload it:    asciinema upload $CAST_FILE"
    elif command -v script &>/dev/null; then
        echo "asciinema not found, falling back to script(1) ..."
        mkdir -p "$(dirname "$TYPESCRIPT_FILE")"
        script -c "$0" "$TYPESCRIPT_FILE"
        echo "Typescript saved to $TYPESCRIPT_FILE"
    else
        echo "Neither asciinema nor script found. Running demo without recording."
        exec "$0"
    fi
    exit 0
}

# --- Main demo ---

run_demo() {
    clear
    printf "\033[1;36m"
    cat <<'BANNER'
   _____ _                       ____
  / ____| |                     |  _ \
 | |    | | __ ___      __      | |_) | __ _ ___  ___
 | |    | |/ _` \ \ /\ / /     |  _ < / _` / __|/ _ \
 | |____| | (_| |\ V  V /      | |_) | (_| \__ \  __/
  \_____|_|\__,_| \_/\_/       |____/ \__,_|___/\___|

  Claude Superpowers — Local-first AI Operations Platform
BANNER
    printf "\033[0m\n"
    sleep 1

    # System status
    run_claw "Check overall system status" "status"

    # Skill registry
    run_claw "List all registered skills" "skill list"

    # Cron jobs
    run_claw "Show scheduled cron jobs" "cron list"

    # Benchmarks
    run_claw "List orchestration benchmarks" "benchmark list"

    # Agent registry
    run_claw "List available agents" "agent list"

    # LLM providers (may not exist)
    if "$CLAW" llm list --help &>/dev/null 2>&1; then
        run_claw "List configured LLM providers" "llm list"
    else
        show_comment "Skipping 'claw llm list' — command not available in this build"
        sleep 0.5
    fi

    # Workflows
    run_claw "Show available workflows" "workflow list"

    # Vault status
    run_claw "Check vault status" "vault status"

    printf "\n\033[1;32mDemo complete.\033[0m\n"
    printf "Run with --record to capture this session.\n\n"
}

# --- Entry point ---

if [[ "${1:-}" == "--record" ]]; then
    record_demo
else
    run_demo
fi
