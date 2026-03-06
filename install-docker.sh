#!/usr/bin/env bash
# ------------------------------------------------------------------
# install-docker.sh — Docker-only quickstart for Claude Superpowers
#
# Pulls images, starts services, prints access URLs.
# Does NOT install the Python CLI — use install.sh for the full setup.
#
# Usage:
#   bash install-docker.sh [--help] [--dry-run]
# ------------------------------------------------------------------

# ── Colors ────────────────────────────────────────────────────────
if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4)
    BOLD=$(tput bold)
    RESET=$(tput sgr0)
else
    RED="" GREEN="" YELLOW="" BLUE="" BOLD="" RESET=""
fi

DRY_RUN=0

info()  { printf "%s[*]%s %s\n" "$BLUE"  "$RESET" "$*"; }
ok()    { printf "%s[+]%s %s\n" "$GREEN" "$RESET" "$*"; }
warn()  { printf "%s[!]%s %s\n" "$YELLOW" "$RESET" "$*"; }
fatal() { printf "%s[FATAL]%s %s\n" "$RED" "$RESET" "$*"; exit 1; }
step()  { printf "\n%s==> %s%s\n" "${BOLD}${GREEN}" "$*" "$RESET"; }

run_cmd() {
    if [ "$DRY_RUN" -eq 1 ]; then
        info "[dry-run] $*"
        return 0
    fi
    "$@"
}

show_help() {
    cat <<'HELP'
Claude Superpowers — Docker Quickstart

Usage: install-docker.sh [OPTIONS]

Options:
  --help        Show this help message and exit
  --dry-run     Show what would happen without making changes

What it does:
  1. Checks Docker and Docker Compose are installed
  2. Copies .env.example to .env if needed
  3. Pulls Docker images
  4. Starts all services (docker compose up -d)
  5. Prints access URLs

Services started:
  - Redis           (localhost:6379)
  - Message Gateway (localhost:8100)
  - Dashboard       (localhost:8200)
  - Browser Engine  (localhost:8300)
  - Telegram Bot
HELP
    exit 0
}

# ── Argument parsing ──────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --help|-h)    show_help ;;
        --dry-run|-n) DRY_RUN=1 ;;
        *)            warn "Unknown argument: $arg" ;;
    esac
done

# ── Banner ────────────────────────────────────────────────────────
printf "\n%s" "$BOLD"
cat <<'BANNER'
  Claude Superpowers — Docker Quickstart
BANNER
printf "%s\n" "$RESET"

if [ "$DRY_RUN" -eq 1 ]; then
    warn "DRY RUN MODE — no changes will be made"
fi

# ── Find project directory ────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

if [ -f "$SCRIPT_DIR/docker-compose.yaml" ] || [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
elif [ -f "./docker-compose.yaml" ] || [ -f "./docker-compose.yml" ]; then
    PROJECT_DIR="$(pwd)"
else
    fatal "Cannot find docker-compose.yaml — run this script from the project root or the directory containing it."
fi

info "Project directory: $PROJECT_DIR"

# ── Step 1: Check Docker ─────────────────────────────────────────
step "Checking prerequisites"

if ! command -v docker >/dev/null 2>&1; then
    fatal "Docker is not installed. Install it from https://docs.docker.com/get-docker/"
fi
ok "Docker found: $(command -v docker)"

if docker compose version >/dev/null 2>&1; then
    compose_version=$(docker compose version --short 2>/dev/null || echo "unknown")
    ok "Docker Compose v2 found (${compose_version})"
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    warn "docker-compose (v1) found — v2 recommended"
    COMPOSE_CMD="docker-compose"
else
    fatal "Docker Compose not found. Install it from https://docs.docker.com/compose/install/"
fi

# Check Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    fatal "Docker daemon is not running. Start it and try again."
fi
ok "Docker daemon is running"

# ── Step 2: Environment file ─────────────────────────────────────
step "Checking environment"

cd "$PROJECT_DIR" || fatal "Cannot cd to $PROJECT_DIR"

if [ -f ".env" ]; then
    info ".env exists — using existing configuration"
else
    if [ -f ".env.example" ]; then
        run_cmd cp .env.example .env
        ok "Copied .env.example to .env"
        warn "Edit .env to set your API keys and passwords before services start"
    else
        fatal ".env.example not found — cannot configure services"
    fi
fi

# Create data directory if needed
DATA_DIR="$HOME/.claude-superpowers"
if [ ! -d "$DATA_DIR" ]; then
    run_cmd mkdir -p "$DATA_DIR"
    run_cmd mkdir -p "$DATA_DIR/browser/profiles"
    ok "Created data directory: $DATA_DIR"
fi

# ── Step 3: Pull images ──────────────────────────────────────────
step "Pulling Docker images"

run_cmd $COMPOSE_CMD pull 2>&1 || warn "Some images may need building locally"
ok "Image pull complete"

# ── Step 4: Build and start services ─────────────────────────────
step "Starting services"

run_cmd $COMPOSE_CMD up -d --build 2>&1
if [ $? -ne 0 ] && [ "$DRY_RUN" -eq 0 ]; then
    fatal "docker compose up failed — check logs with: docker compose logs"
fi
ok "Services started"

# ── Step 5: Verify ───────────────────────────────────────────────
step "Verifying services"

if [ "$DRY_RUN" -eq 0 ]; then
    info "Waiting 5 seconds for services to initialize..."
    sleep 5

    # Check each service
    running=$($COMPOSE_CMD ps --format '{{.Name}} {{.Status}}' 2>/dev/null || $COMPOSE_CMD ps 2>/dev/null)
    if [ -n "$running" ]; then
        printf "%s\n" "$running"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────
printf "\n"
ok "Docker services are running!"
printf "\n%s%sAccess URLs:%s\n" "$BOLD" "$GREEN" "$RESET"
printf "  Dashboard:       http://localhost:8200\n"
printf "  Message Gateway: http://localhost:8100\n"
printf "  Browser Engine:  http://localhost:8300\n"
printf "  Redis:           localhost:6379\n"
printf "\n%s%sUseful commands:%s\n" "$BOLD" "$BLUE" "$RESET"
printf "  docker compose logs -f         # follow logs\n"
printf "  docker compose ps              # service status\n"
printf "  docker compose down            # stop services\n"
printf "  docker compose up -d --build   # rebuild and restart\n"
printf "\n"
