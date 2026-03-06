#!/usr/bin/env bash
# project-sync.sh — Bidirectional sync between Mac and Docker server
# Usage: project-sync.sh [status|sync|push|pull] [--force] [--project NAME]
set -uo pipefail

# ── Config ──────────────────────────────────────────────────────────────
MAC_USER="dre"
MAC_HOST="192.168.20.141"
MAC_PROJECTS="/Users/dre/Projects"

SERVER_USER="ray"
SERVER_HOST="192.168.30.117"
SERVER_PROJECTS="/home/ray/Projects"

# Git repos (synced via GitHub)
GIT_REPOS=(
  BabyS claude-superpowers dotfiles fzf-git.sh homelab
  hommie k3s-cluster nexus-media vmware-audit WorkOps zabbix-zntv
)

# Non-git dirs (synced via rsync, bidirectional)
RSYNC_DIRS=(_bmad home-network-docs)

# Server-only dirs (never synced)
SKIP_DIRS=(docker-stacks)

# ── Colors ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Detect environment ──────────────────────────────────────────────────
detect_env() {
  if [[ "$(uname)" == "Darwin" ]]; then
    LOCAL_ENV="mac"
    LOCAL_PROJECTS="$MAC_PROJECTS"
    REMOTE_USER="$SERVER_USER"
    REMOTE_HOST="$SERVER_HOST"
    REMOTE_PROJECTS="$SERVER_PROJECTS"
  else
    LOCAL_ENV="server"
    LOCAL_PROJECTS="$SERVER_PROJECTS"
    REMOTE_USER="$MAC_USER"
    REMOTE_HOST="$MAC_HOST"
    REMOTE_PROJECTS="$MAC_PROJECTS"
  fi
  LOG_DIR="$HOME/logs"
  mkdir -p "$LOG_DIR"
  LOG_FILE="$LOG_DIR/project-sync.log"
}

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
err()   { echo -e "${RED}✗${NC}  $*"; }
header(){ echo -e "\n${BOLD}${CYAN}── $* ──${NC}"; }

# ── Check remote is reachable ───────────────────────────────────────────
check_remote() {
  if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${REMOTE_USER}@${REMOTE_HOST}" true 2>/dev/null; then
    err "Cannot reach ${REMOTE_USER}@${REMOTE_HOST}"
    exit 1
  fi
  ok "Remote reachable: ${REMOTE_USER}@${REMOTE_HOST}"
}

# ── Git repo status ─────────────────────────────────────────────────────
git_status_local() {
  local dir="$1"
  local path="${LOCAL_PROJECTS}/${dir}"
  if [[ ! -d "${path}/.git" ]]; then
    echo "NOT_GIT"
    return
  fi
  cd "$path"
  local dirty=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
  local branch=$(git branch --show-current 2>/dev/null)

  # Fetch to compare with remote
  git fetch --quiet 2>/dev/null || true
  local remote_hash=$(git rev-parse "origin/${branch}" 2>/dev/null || echo "none")

  local ahead=0 behind=0
  if [[ "$remote_hash" != "none" ]]; then
    ahead=$(git rev-list --count "origin/${branch}..HEAD" 2>/dev/null || echo 0)
    behind=$(git rev-list --count "HEAD..origin/${branch}" 2>/dev/null || echo 0)
  fi

  local local_hash=$(git rev-parse HEAD 2>/dev/null)
  echo "${dirty}|${branch}|${ahead}|${behind}|${local_hash:0:7}"
}

git_status_remote() {
  local dir="$1"
  ssh "${REMOTE_USER}@${REMOTE_HOST}" "
    path='${REMOTE_PROJECTS}/${dir}'
    if [ ! -d \"\${path}/.git\" ]; then echo 'NOT_GIT'; exit; fi
    cd \"\$path\"
    dirty=\$(git status --short 2>/dev/null | wc -l | tr -d ' ')
    branch=\$(git branch --show-current 2>/dev/null)
    hash=\$(git rev-parse HEAD 2>/dev/null)
    echo \"\${dirty}|\${branch}|\${hash}\"
  " 2>/dev/null
}

# ── Show status for all repos ───────────────────────────────────────────
cmd_status() {
  header "Project Sync Status (local=$LOCAL_ENV)"
  check_remote

  printf "\n${BOLD}%-22s %-10s %-8s %-8s %-8s %-10s${NC}\n" \
    "PROJECT" "BRANCH" "LOCAL△" "AHEAD" "BEHIND" "REMOTE△"
  printf "%-22s %-10s %-8s %-8s %-8s %-10s\n" \
    "───────" "──────" "──────" "─────" "──────" "───────"

  for repo in "${GIT_REPOS[@]}"; do
    local_info=$(git_status_local "$repo")
    remote_info=$(git_status_remote "$repo")

    if [[ "$local_info" == "NOT_GIT" ]]; then
      printf "%-22s ${RED}not a git repo locally${NC}\n" "$repo"
      continue
    fi

    IFS='|' read -r l_dirty l_branch l_ahead l_behind l_hash <<< "$local_info"
    IFS='|' read -r r_dirty r_branch r_hash <<< "$remote_info"

    # Color coding
    local_color="${GREEN}"
    [[ "$l_dirty" -gt 0 ]] && local_color="${YELLOW}"
    remote_color="${GREEN}"
    [[ "${r_dirty:-0}" -gt 0 ]] && remote_color="${YELLOW}"
    ahead_color="${NC}"
    [[ "$l_ahead" -gt 0 ]] && ahead_color="${CYAN}"
    behind_color="${NC}"
    [[ "$l_behind" -gt 0 ]] && behind_color="${RED}"

    printf "%-22s %-10s ${local_color}%-8s${NC} ${ahead_color}%-8s${NC} ${behind_color}%-8s${NC} ${remote_color}%-10s${NC}\n" \
      "$repo" "$l_branch" "${l_dirty}Δ" "${l_ahead}↑" "${l_behind}↓" "${r_dirty:-0}Δ"
  done

  header "Non-Git Dirs (rsync)"
  for dir in "${RSYNC_DIRS[@]}"; do
    local_exists=false
    remote_exists=false
    [[ -d "${LOCAL_PROJECTS}/${dir}" ]] && local_exists=true
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "[ -d '${REMOTE_PROJECTS}/${dir}' ]" 2>/dev/null && remote_exists=true

    if ! $local_exists && ! $remote_exists; then
      warn "$dir: missing on both sides"
      continue
    elif ! $local_exists; then
      info "$dir: only on remote → needs pull"
      continue
    elif ! $remote_exists; then
      info "$dir: only on local → needs push"
      continue
    fi

    # Get newest file timestamp (stat works on both macOS and Linux)
    local_mod=$(find "${LOCAL_PROJECTS}/${dir}" -type f -not -name '.DS_Store' -exec stat -c '%Y' {} \; 2>/dev/null | sort -rn | head -1 || \
                find "${LOCAL_PROJECTS}/${dir}" -type f -not -name '.DS_Store' -exec stat -f '%m' {} \; 2>/dev/null | sort -rn | head -1 || echo 0)
    remote_mod=$(ssh "${REMOTE_USER}@${REMOTE_HOST}" "find '${REMOTE_PROJECTS}/${dir}' -type f -not -name '.DS_Store' -exec stat -c '%Y' {} \; 2>/dev/null | sort -rn | head -1 || \
                find '${REMOTE_PROJECTS}/${dir}' -type f -not -name '.DS_Store' -exec stat -f '%m' {} \; 2>/dev/null | sort -rn | head -1 || echo 0" 2>/dev/null)

    [[ -z "$local_mod" ]] && local_mod=0
    [[ -z "$remote_mod" ]] && remote_mod=0

    if [[ "$local_mod" -gt "$remote_mod" ]]; then
      info "$dir: local newer → needs push"
    elif [[ "$remote_mod" -gt "$local_mod" ]]; then
      info "$dir: remote newer → needs pull"
    else
      ok "$dir: in sync"
    fi
  done

  header "Skipped (server-only)"
  for dir in "${SKIP_DIRS[@]}"; do
    info "$dir — server-only, not synced"
  done
}

# ── Sync git repos ──────────────────────────────────────────────────────
sync_git_push() {
  local repo="$1"
  local path="${LOCAL_PROJECTS}/${repo}"
  if [[ ! -d "${path}/.git" ]]; then
    warn "$repo: not a git repo locally — skipping"
    return
  fi

  cd "$path"
  local dirty=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
  local branch=$(git branch --show-current 2>/dev/null)

  if [[ "$dirty" -gt 0 ]]; then
    warn "$repo: $dirty uncommitted files — skipping push (commit first)"
    log "SKIP $repo: $dirty dirty files"
    return
  fi

  # Push local commits to GitHub
  local ahead=$(git rev-list --count "origin/${branch}..HEAD" 2>/dev/null || echo 0)
  if [[ "$ahead" -gt 0 ]]; then
    info "$repo: pushing $ahead commits to origin/${branch}"
    git push origin "$branch" 2>/dev/null && ok "$repo: pushed" || err "$repo: push failed"
    log "PUSH $repo: $ahead commits to $branch"
  fi

  # Pull on remote side
  ssh "${REMOTE_USER}@${REMOTE_HOST}" "
    cd '${REMOTE_PROJECTS}/${repo}' 2>/dev/null || exit 0
    dirty=\$(git status --short 2>/dev/null | wc -l | tr -d ' ')
    if [ \"\$dirty\" -gt 0 ]; then
      echo 'SKIP_REMOTE_DIRTY'
      exit 0
    fi
    git pull --ff-only origin '${branch}' 2>/dev/null && echo 'PULLED' || echo 'PULL_FAILED'
  " 2>/dev/null | while read -r line; do
    case "$line" in
      SKIP_REMOTE_DIRTY) warn "$repo: remote has dirty files — skipping pull" ;;
      PULLED) ok "$repo: remote pulled" ;;
      PULL_FAILED) err "$repo: remote pull failed" ;;
    esac
  done
}

sync_git_pull() {
  local repo="$1"
  local path="${LOCAL_PROJECTS}/${repo}"
  if [[ ! -d "${path}/.git" ]]; then
    warn "$repo: not a git repo locally — skipping"
    return
  fi

  cd "$path"
  local dirty=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
  local branch=$(git branch --show-current 2>/dev/null)

  # Push from remote to GitHub first
  ssh "${REMOTE_USER}@${REMOTE_HOST}" "
    cd '${REMOTE_PROJECTS}/${repo}' 2>/dev/null || exit 0
    dirty=\$(git status --short 2>/dev/null | wc -l | tr -d ' ')
    if [ \"\$dirty\" -gt 0 ]; then
      echo 'SKIP_REMOTE_DIRTY'
      exit 0
    fi
    ahead=\$(git rev-list --count 'origin/${branch}..HEAD' 2>/dev/null || echo 0)
    if [ \"\$ahead\" -gt 0 ]; then
      git push origin '${branch}' 2>/dev/null && echo \"PUSHED \$ahead\" || echo 'PUSH_FAILED'
    fi
  " 2>/dev/null | while read -r line; do
    case "$line" in
      SKIP_REMOTE_DIRTY) warn "$repo: remote has dirty files — skipping remote push" ;;
      PUSHED*) ok "$repo: remote pushed ${line#PUSHED }" ;;
      PUSH_FAILED) err "$repo: remote push failed" ;;
    esac
  done

  # Pull locally
  if [[ "$dirty" -gt 0 ]]; then
    warn "$repo: $dirty local dirty files — skipping pull"
    return
  fi

  git fetch --quiet 2>/dev/null || true
  local behind=$(git rev-list --count "HEAD..origin/${branch}" 2>/dev/null || echo 0)
  if [[ "$behind" -gt 0 ]]; then
    info "$repo: pulling $behind commits"
    git pull --ff-only origin "$branch" 2>/dev/null && ok "$repo: pulled" || err "$repo: pull failed"
    log "PULL $repo: $behind commits from $branch"
  else
    ok "$repo: up to date"
  fi
}

# ── Sync non-git dirs ───────────────────────────────────────────────────
sync_rsync_push() {
  local dir="$1"
  local src="${LOCAL_PROJECTS}/${dir}/"
  local dst="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PROJECTS}/${dir}/"

  info "$dir: rsync local → remote"
  rsync -avz --delete --exclude='.DS_Store' "$src" "$dst" 2>/dev/null && \
    ok "$dir: synced" || err "$dir: rsync failed"
  log "RSYNC_PUSH $dir"
}

sync_rsync_pull() {
  local dir="$1"
  local src="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PROJECTS}/${dir}/"
  local dst="${LOCAL_PROJECTS}/${dir}/"

  info "$dir: rsync remote → local"
  rsync -avz --delete --exclude='.DS_Store' "$src" "$dst" 2>/dev/null && \
    ok "$dir: synced" || err "$dir: rsync failed"
  log "RSYNC_PULL $dir"
}

# ── Main commands ───────────────────────────────────────────────────────
cmd_push() {
  header "Push: $LOCAL_ENV → remote"
  check_remote

  local target="${1:-all}"

  for repo in "${GIT_REPOS[@]}"; do
    [[ "$target" != "all" && "$target" != "$repo" ]] && continue
    sync_git_push "$repo"
  done

  for dir in "${RSYNC_DIRS[@]}"; do
    [[ "$target" != "all" && "$target" != "$dir" ]] && continue
    sync_rsync_push "$dir"
  done

  log "PUSH complete"
}

cmd_pull() {
  header "Pull: remote → $LOCAL_ENV"
  check_remote

  local target="${1:-all}"

  for repo in "${GIT_REPOS[@]}"; do
    [[ "$target" != "all" && "$target" != "$repo" ]] && continue
    sync_git_pull "$repo"
  done

  for dir in "${RSYNC_DIRS[@]}"; do
    [[ "$target" != "all" && "$target" != "$dir" ]] && continue
    sync_rsync_pull "$dir"
  done

  log "PULL complete"
}

cmd_sync() {
  header "Bidirectional Sync"
  check_remote

  local target="${1:-all}"

  info "Phase 1: Fetch all remotes"
  for repo in "${GIT_REPOS[@]}"; do
    [[ "$target" != "all" && "$target" != "$repo" ]] && continue
    local path="${LOCAL_PROJECTS}/${repo}"
    [[ -d "${path}/.git" ]] && (cd "$path" && git fetch --quiet 2>/dev/null)
  done

  info "Phase 2: Push local commits → GitHub → pull on remote"
  for repo in "${GIT_REPOS[@]}"; do
    [[ "$target" != "all" && "$target" != "$repo" ]] && continue
    sync_git_push "$repo"
  done

  info "Phase 3: Pull remote commits → GitHub → pull locally"
  for repo in "${GIT_REPOS[@]}"; do
    [[ "$target" != "all" && "$target" != "$repo" ]] && continue
    sync_git_pull "$repo"
  done

  info "Phase 4: Rsync non-git dirs (newer wins)"
  for dir in "${RSYNC_DIRS[@]}"; do
    [[ "$target" != "all" && "$target" != "$dir" ]] && continue
    [[ ! -d "${LOCAL_PROJECTS}/${dir}" ]] && { warn "$dir: missing locally, skipping"; continue; }

    local_mod=$(find "${LOCAL_PROJECTS}/${dir}" -type f -not -name '.DS_Store' -exec stat -c '%Y' {} \; 2>/dev/null | sort -rn | head -1 || \
                find "${LOCAL_PROJECTS}/${dir}" -type f -not -name '.DS_Store' -exec stat -f '%m' {} \; 2>/dev/null | sort -rn | head -1 || echo 0)
    remote_mod=$(ssh "${REMOTE_USER}@${REMOTE_HOST}" "find '${REMOTE_PROJECTS}/${dir}' -type f -not -name '.DS_Store' -exec stat -c '%Y' {} \; 2>/dev/null | sort -rn | head -1 || \
                find '${REMOTE_PROJECTS}/${dir}' -type f -not -name '.DS_Store' -exec stat -f '%m' {} \; 2>/dev/null | sort -rn | head -1 || echo 0" 2>/dev/null)

    [[ -z "$local_mod" ]] && local_mod=0
    [[ -z "$remote_mod" ]] && remote_mod=0

    if [[ "$local_mod" -gt "$remote_mod" ]]; then
      sync_rsync_push "$dir"
    else
      sync_rsync_pull "$dir"
    fi
  done

  log "SYNC complete"
  header "Done"
}

# ── Entry point ─────────────────────────────────────────────────────────
detect_env

MODE="${1:-status}"
FILTER="${2:-all}"

# Handle --project flag
if [[ "${2:-}" == "--project" ]]; then
  FILTER="${3:-all}"
elif [[ "${1:-}" == "--project" ]]; then
  MODE="status"
  FILTER="${2:-all}"
fi

case "$MODE" in
  status) cmd_status ;;
  push)   cmd_push "$FILTER" ;;
  pull)   cmd_pull "$FILTER" ;;
  sync)   cmd_sync "$FILTER" ;;
  -h|--help|help)
    echo "Usage: project-sync.sh [status|sync|push|pull] [PROJECT_NAME]"
    echo ""
    echo "Commands:"
    echo "  status           Show sync status of all projects (default)"
    echo "  sync             Full bidirectional sync (GitHub + rsync)"
    echo "  push             Push local changes → remote"
    echo "  pull             Pull remote changes → local"
    echo ""
    echo "Options:"
    echo "  PROJECT_NAME     Sync only this project (e.g., 'claude-superpowers')"
    echo ""
    echo "Environment:"
    echo "  Mac:    ${MAC_USER}@${MAC_HOST}:${MAC_PROJECTS}"
    echo "  Server: ${SERVER_USER}@${SERVER_HOST}:${SERVER_PROJECTS}"
    echo ""
    echo "Git repos sync through GitHub (commit→push→pull)."
    echo "Non-git dirs sync via rsync (newer side wins)."
    echo "Dirty repos are never force-synced — commit first."
    ;;
  *) err "Unknown command: $MODE"; exit 1 ;;
esac
