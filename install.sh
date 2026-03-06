#!/usr/bin/env bash
# ------------------------------------------------------------------
# install.sh — One-line installer for Claude Superpowers (claw CLI)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/SmartMur/smartmur-ai-core/main/install.sh | bash
#   # or locally:
#   bash install.sh [--dry-run] [--help]
# ------------------------------------------------------------------

REPO_URL="https://github.com/SmartMur/smartmur-ai-core.git"
INSTALL_DIR="${CLAW_INSTALL_DIR:-$HOME/claude-superpowers}"
LOCAL_BIN="$HOME/.local/bin"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=12

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

# ── Globals ───────────────────────────────────────────────────────
DRY_RUN=0
ERRORS=0

# ── Helpers ───────────────────────────────────────────────────────
info()  { printf "%s[*]%s %s\n" "$BLUE"  "$RESET" "$*"; }
ok()    { printf "%s[+]%s %s\n" "$GREEN" "$RESET" "$*"; }
warn()  { printf "%s[!]%s %s\n" "$YELLOW" "$RESET" "$*"; }
fail()  { printf "%s[-]%s %s\n" "$RED"   "$RESET" "$*"; ERRORS=$((ERRORS + 1)); }
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
Claude Superpowers (claw) Installer

Usage: install.sh [OPTIONS]

Options:
  --help        Show this help message and exit
  --dry-run     Show what would happen without making changes

Environment variables:
  CLAW_INSTALL_DIR   Override install directory (default: ~/claude-superpowers)

Prerequisites:
  - Python 3.12 or later
  - Docker and Docker Compose v2
  - git

What it does:
  1. Checks prerequisites (Python, Docker, git)
  2. Clones or updates the repository
  3. Creates a Python virtualenv and installs dependencies
  4. Copies .env.example to .env (if .env is missing)
  5. Pulls Docker service images
  6. Adds 'claw' CLI to your PATH
  7. Runs a quick health check
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
printf "\n%s" "${BOLD}"
cat <<'BANNER'
   _____ _                 _
  / ____| |               | |
 | |    | | __ ___      __| |
 | |    | |/ _` \ \ /\ / /| |
 | |____| | (_| |\ V  V / |_|
  \_____|_|\__,_| \_/\_/  (_)
BANNER
printf "%s\n" "$RESET"
info "Claude Superpowers installer"
if [ "$DRY_RUN" -eq 1 ]; then
    warn "DRY RUN MODE — no changes will be made"
fi
printf "\n"

# ── Step 1: Detect OS & Architecture ─────────────────────────────
step "Detecting system"

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux)  OS_LABEL="Linux" ;;
    Darwin) OS_LABEL="macOS" ;;
    *)      fatal "Unsupported operating system: $OS" ;;
esac

case "$ARCH" in
    x86_64)  ARCH_LABEL="x86_64 (amd64)" ;;
    aarch64|arm64) ARCH_LABEL="ARM64" ;;
    *)       ARCH_LABEL="$ARCH" ;;
esac

ok "OS: $OS_LABEL | Architecture: $ARCH_LABEL"

# ── Step 2: Check prerequisites ──────────────────────────────────
step "Checking prerequisites"

check_command() {
    local cmd="$1"
    local label="${2:-$1}"
    local hint="${3:-}"
    if command -v "$cmd" >/dev/null 2>&1; then
        ok "$label found: $(command -v "$cmd")"
        return 0
    else
        fail "$label not found"
        if [ -n "$hint" ]; then
            info "  Install: $hint"
        fi
        return 1
    fi
}

# Python — need 3.12+
PYTHON_CMD=""
python_ok=0
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        py_version=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
        if [ -n "$py_version" ]; then
            py_major="${py_version%%.*}"
            py_minor="${py_version#*.}"
            if [ "$py_major" -ge "$MIN_PYTHON_MAJOR" ] && [ "$py_minor" -ge "$MIN_PYTHON_MINOR" ]; then
                PYTHON_CMD="$candidate"
                python_ok=1
                ok "Python $py_version found: $(command -v "$candidate")"
                break
            fi
        fi
    fi
done

if [ "$python_ok" -eq 0 ]; then
    fail "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ not found"
    if [ "$OS" = "Darwin" ]; then
        info "  Install: brew install python@3.12"
    else
        info "  Install: sudo apt install python3.12 python3.12-venv"
    fi
fi

# Docker
docker_ok=0
if check_command docker "Docker" "https://docs.docker.com/get-docker/"; then
    docker_ok=1
fi

# Docker Compose v2
compose_ok=0
if docker compose version >/dev/null 2>&1; then
    compose_version=$(docker compose version --short 2>/dev/null || echo "unknown")
    ok "Docker Compose v2 found (${compose_version})"
    compose_ok=1
elif command -v docker-compose >/dev/null 2>&1; then
    warn "docker-compose (v1) found — Docker Compose v2 recommended"
    compose_ok=1
else
    fail "Docker Compose not found"
    info "  Install: https://docs.docker.com/compose/install/"
fi

# Git
git_ok=0
if check_command git "git" "sudo apt install git  OR  brew install git"; then
    git_ok=1
fi

if [ "$python_ok" -eq 0 ] || [ "$git_ok" -eq 0 ]; then
    fatal "Missing required prerequisites (see above). Install them and re-run."
fi

if [ "$docker_ok" -eq 0 ] || [ "$compose_ok" -eq 0 ]; then
    warn "Docker/Compose not found — CLI will install but Docker services will be unavailable."
fi

# ── Step 3: Clone or update repository ────────────────────────────
step "Setting up repository"

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Repository already exists at $INSTALL_DIR — pulling latest"
    if [ "$DRY_RUN" -eq 0 ]; then
        cd "$INSTALL_DIR" || fatal "Cannot cd to $INSTALL_DIR"
        git pull --ff-only 2>&1 || warn "git pull failed — continuing with existing code"
    else
        info "[dry-run] cd $INSTALL_DIR && git pull --ff-only"
    fi
else
    info "Cloning repository to $INSTALL_DIR"
    run_cmd git clone "$REPO_URL" "$INSTALL_DIR"
    if [ $? -ne 0 ] && [ "$DRY_RUN" -eq 0 ]; then
        fatal "git clone failed"
    fi
fi

if [ "$DRY_RUN" -eq 0 ]; then
    cd "$INSTALL_DIR" || fatal "Cannot cd to $INSTALL_DIR"
fi

ok "Repository ready at $INSTALL_DIR"

# ── Step 4: Create Python virtualenv ──────────────────────────────
step "Setting up Python virtualenv"

VENV_DIR="$INSTALL_DIR/.venv"

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ]; then
    info "Virtualenv already exists at $VENV_DIR"
else
    info "Creating virtualenv..."
    if [ "$DRY_RUN" -eq 0 ]; then
        # Try with pip first, fall back to --without-pip + bootstrap
        if ! "$PYTHON_CMD" -m venv "$VENV_DIR" 2>/dev/null; then
            info "Standard venv creation failed — trying --without-pip and bootstrapping"
            "$PYTHON_CMD" -m venv --without-pip "$VENV_DIR" || fatal "Cannot create virtualenv"

            info "Bootstrapping pip via get-pip.py..."
            GET_PIP_URL="https://bootstrap.pypa.io/get-pip.py"
            GET_PIP_PATH="$INSTALL_DIR/.get-pip.py"

            if command -v curl >/dev/null 2>&1; then
                curl -fsSL "$GET_PIP_URL" -o "$GET_PIP_PATH" || fatal "Failed to download get-pip.py"
            elif command -v wget >/dev/null 2>&1; then
                wget -q "$GET_PIP_URL" -O "$GET_PIP_PATH" || fatal "Failed to download get-pip.py"
            else
                fatal "Neither curl nor wget available — cannot bootstrap pip"
            fi

            "$VENV_DIR/bin/python" "$GET_PIP_PATH" --quiet || fatal "pip bootstrap failed"
            rm -f "$GET_PIP_PATH"
        fi
    else
        info "[dry-run] $PYTHON_CMD -m venv $VENV_DIR"
    fi
fi

ok "Virtualenv ready"

# ── Step 5: Install package ───────────────────────────────────────
step "Installing claude-superpowers (editable)"

if [ "$DRY_RUN" -eq 0 ]; then
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools 2>&1 || warn "pip/setuptools upgrade failed"
    "$VENV_DIR/bin/pip" install --quiet -e "$INSTALL_DIR" 2>&1
    if [ $? -ne 0 ]; then
        fatal "pip install -e . failed"
    fi
else
    info "[dry-run] $VENV_DIR/bin/pip install -e $INSTALL_DIR"
fi

ok "Package installed"

# ── Step 6: Copy .env.example ─────────────────────────────────────
step "Configuring environment"

ENV_FILE="$INSTALL_DIR/.env"
ENV_EXAMPLE="$INSTALL_DIR/.env.example"

if [ -f "$ENV_FILE" ]; then
    info ".env already exists — skipping (will not overwrite)"
else
    if [ -f "$ENV_EXAMPLE" ]; then
        run_cmd cp "$ENV_EXAMPLE" "$ENV_FILE"
        ok "Copied .env.example to .env"
        warn "Edit $ENV_FILE to set your API keys and passwords"
    else
        warn ".env.example not found — skipping .env creation"
    fi
fi

# Create data directory
DATA_DIR="$HOME/.claude-superpowers"
if [ ! -d "$DATA_DIR" ]; then
    run_cmd mkdir -p "$DATA_DIR"
    ok "Created data directory: $DATA_DIR"
else
    info "Data directory exists: $DATA_DIR"
fi

# ── Step 7: Pull Docker images ────────────────────────────────────
step "Pulling Docker service images"

if [ "$docker_ok" -eq 1 ] && [ "$compose_ok" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 0 ]; then
        cd "$INSTALL_DIR" || fatal "Cannot cd to $INSTALL_DIR"
        docker compose pull 2>&1 || warn "docker compose pull had warnings (some images may need building)"
    else
        info "[dry-run] docker compose pull"
    fi
    ok "Docker images ready"
else
    warn "Skipping Docker pull — Docker/Compose not available"
fi

# ── Step 8: Add claw to PATH ─────────────────────────────────────
step "Adding claw to PATH"

CLAW_BIN="$VENV_DIR/bin/claw"

if [ ! -f "$CLAW_BIN" ] && [ "$DRY_RUN" -eq 0 ]; then
    warn "claw binary not found at $CLAW_BIN — install may have failed"
else
    # Create symlink in ~/.local/bin
    run_cmd mkdir -p "$LOCAL_BIN"

    if [ "$DRY_RUN" -eq 0 ]; then
        ln -sf "$CLAW_BIN" "$LOCAL_BIN/claw" 2>/dev/null
        if [ $? -eq 0 ]; then
            ok "Symlinked claw to $LOCAL_BIN/claw"
        else
            warn "Could not create symlink in $LOCAL_BIN"
        fi
    else
        info "[dry-run] ln -sf $CLAW_BIN $LOCAL_BIN/claw"
    fi

    # Check if LOCAL_BIN is on PATH
    case ":$PATH:" in
        *":$LOCAL_BIN:"*) ;;
        *)
            warn "$LOCAL_BIN is not in your PATH"
            info "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
            printf "    %sexport PATH=\"%s:\$PATH\"%s\n" "$BOLD" "$LOCAL_BIN" "$RESET"
            ;;
    esac
fi

# ── Step 9: Health check ─────────────────────────────────────────
step "Running health check"

if [ "$DRY_RUN" -eq 0 ]; then
    if [ -f "$CLAW_BIN" ]; then
        claw_version=$("$CLAW_BIN" --version 2>&1 || true)
        if [ -n "$claw_version" ]; then
            ok "claw CLI responds: $claw_version"
        else
            # --version might not exist, try --help
            "$CLAW_BIN" --help >/dev/null 2>&1
            if [ $? -eq 0 ]; then
                ok "claw CLI is functional"
            else
                warn "claw CLI installed but health check returned non-zero"
            fi
        fi
    else
        warn "claw binary not found — skipping health check"
    fi
else
    info "[dry-run] $CLAW_BIN --version"
fi

# ── Done ──────────────────────────────────────────────────────────
printf "\n"
if [ "$ERRORS" -gt 0 ]; then
    warn "Installation completed with $ERRORS warning(s) — review messages above"
else
    ok "Installation complete!"
fi

printf "\n%s%sNext steps:%s\n" "$BOLD" "$GREEN" "$RESET"
printf "  1. cd %s\n" "$INSTALL_DIR"
printf "  2. Edit .env with your API keys and passwords\n"
if [ "$docker_ok" -eq 1 ]; then
    printf "  3. docker compose up -d    # start services\n"
    printf "  4. claw status             # verify everything\n"
else
    printf "  3. Install Docker, then: docker compose up -d\n"
    printf "  4. claw status             # verify everything\n"
fi
printf "\n  Dashboard: http://localhost:8200\n"
printf "  Docs:      %s\n\n" "$REPO_URL"
