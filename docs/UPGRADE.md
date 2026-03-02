# Upgrade Guide

Version migration, breaking changes, config adjustments, and rollback guidance.

---

## General Upgrade Steps

### 1. Back Up First

```bash
# Back up critical state
cp ~/.claude-superpowers/vault.enc ~/vault-pre-upgrade.enc
cp ~/.claude-superpowers/age-identity.txt ~/age-identity-pre-upgrade.txt
cp ~/.claude-superpowers/memory.db ~/memory-pre-upgrade.db
cp ~/.claude-superpowers/cron/jobs.json ~/jobs-pre-upgrade.json
cp /home/ray/claude-superpowers/.env ~/env-pre-upgrade
```

### 2. Pull New Code

```bash
cd /home/ray/claude-superpowers
git fetch origin
git log --oneline HEAD..origin/main   # Review incoming changes
git pull --ff-only
```

### 3. Check for New Dependencies

```bash
# Compare pyproject.toml changes
git diff HEAD~1 pyproject.toml

# Reinstall
source .venv/bin/activate
pip install -e ".[dev]"
```

### 4. Check for New Environment Variables

```bash
# Compare .env.example changes
git diff HEAD~1 .env.example

# Add any new variables to your .env
```

### 5. Rebuild Docker Services

```bash
docker compose up -d --build
```

### 6. Restart Standalone Services

```bash
# Cron daemon
claw daemon uninstall && claw daemon install

# File watcher (if running as systemd service)
systemctl --user restart claude-superpowers-watcher

# Telegram bot (if running as systemd service)
systemctl --user restart claude-superpowers-telegram
```

### 7. Verify

```bash
claw --version
claw status
claw vault list
claw skill list
curl http://localhost:8200/health
```

---

## Breaking Changes Log

### v0.1.0 (Initial Release)

This is the initial release. All components are new.

**Configuration requirements established:**

| Item | Requirement |
|------|-------------|
| `DASHBOARD_PASS` | Must be set explicitly. No insecure default. |
| `ALLOWED_CHAT_IDS` | Must be set for Telegram bot. Empty = all messages rejected. |
| `age` binary | Must be installed on the system for vault operations. |
| Python 3.12+ | Minimum supported version. |

**Data directory:** `~/.claude-superpowers/` is created automatically by `Settings.ensure_dirs()`.

**Vault format:** age-encrypted JSON blob. Format is stable and forward-compatible.

**Memory database:** SQLite with WAL mode. Schema: single `memories` table with UNIQUE constraint on `(category, key, project)`.

**Cron job store:** `jobs.json` (human-readable manifest) + `jobstore.sqlite` (APScheduler state). Both must be consistent. If edited manually, restart the daemon.

---

## Config Diff Guidance

When upgrading, compare your `.env` against `.env.example` for new or changed variables.

```bash
# Show all variables in .env.example
grep -v '^#' .env.example | grep '=' | cut -d= -f1 | sort

# Show all variables in your .env
grep -v '^#' .env | grep '=' | cut -d= -f1 | sort

# Find variables in .env.example not in .env
diff <(grep -v '^#' .env.example | grep '=' | cut -d= -f1 | sort) \
     <(grep -v '^#' .env | grep '=' | cut -d= -f1 | sort)
```

### Environment Variables Added Over Time

| Variable | Added In | Default | Notes |
|----------|----------|---------|-------|
| `ANTHROPIC_API_KEY` | Phase 1 | `""` | For Claude-type cron jobs |
| `SLACK_BOT_TOKEN` | Phase 3 | `""` | Slack messaging |
| `TELEGRAM_BOT_TOKEN` | Phase 3 | `""` | Telegram messaging + bot |
| `TELEGRAM_DEFAULT_CHAT_ID` | Phase 3 | `""` | Default notification target |
| `DISCORD_BOT_TOKEN` | Phase 3 | `""` | Discord messaging |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `SMTP_PORT`, `SMTP_FROM` | Phase 3 | varies | Email messaging |
| `DASHBOARD_USER`, `DASHBOARD_PASS` | Phase 8 | `""` | Dashboard auth (required) |
| `REDIS_URL` | Phase 3 | `redis://localhost:6379/0` | Session/pubsub |
| `VAULT_IDENTITY_FILE` | Phase 1 | `~/.claude-superpowers/vault.key` | Vault key path |
| `ALLOWED_CHAT_IDS` | Phase 9 | `""` | Telegram bot allowlist |
| `TELEGRAM_SESSION_TTL` | Phase 9 | `3600` | Bot session TTL |
| `TELEGRAM_MAX_HISTORY` | Phase 9 | `20` | Bot message limit |
| `TELEGRAM_MAX_PER_CHAT` | Phase 9 | `2` | Bot concurrency per chat |
| `TELEGRAM_MAX_GLOBAL` | Phase 9 | `5` | Bot global concurrency |
| `TELEGRAM_QUEUE_OVERFLOW` | Phase 9 | `10` | Bot queue limit |
| `HOME_ASSISTANT_URL` | Phase 4 | `""` | HA base URL |
| `HOME_ASSISTANT_TOKEN` | Phase 4 | `""` | HA access token |
| `SUPERPOWERS_DATA_DIR` | Phase 1 | `~/.claude-superpowers` | Data directory override |

---

## Schema Changes

### Memory Database

The memory database (`~/.claude-superpowers/memory.db`) uses a single table:

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    project TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    access_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    UNIQUE(category, key, project)
);
```

If a future version adds columns, the upgrade path is:

1. Back up the database: `cp memory.db memory-backup.db`
2. Run the upgrade (the code will handle schema migration)
3. Verify: `claw memory stats`

### Cron Job Store

The `jobs.json` format is a flat dictionary keyed by job ID. New fields may be added to job entries; existing fields are preserved. The APScheduler SQLite store (`jobstore.sqlite`) is managed internally and should not be edited.

### Vault Format

The vault is a JSON object encrypted with age. The JSON schema is `{"key": "value", ...}`. New keys are simply added; no format migration is needed.

---

## Rollback Plan

If an upgrade causes problems:

### Quick Rollback

```bash
cd /home/ray/claude-superpowers

# 1. Check the previous version
git log --oneline -5

# 2. Revert to previous commit
git checkout <commit-hash>

# 3. Reinstall
pip install -e ".[dev]"

# 4. Rebuild containers
docker compose up -d --build

# 5. Restart services
claw daemon uninstall && claw daemon install

# 6. Restore config if needed
cp ~/env-pre-upgrade .env
```

### Data Rollback

If the upgrade modified data files:

```bash
# Restore vault
cp ~/vault-pre-upgrade.enc ~/.claude-superpowers/vault.enc
cp ~/age-identity-pre-upgrade.txt ~/.claude-superpowers/age-identity.txt
chmod 600 ~/.claude-superpowers/age-identity.txt ~/.claude-superpowers/vault.enc

# Restore memory
cp ~/memory-pre-upgrade.db ~/.claude-superpowers/memory.db

# Restore cron jobs
cp ~/jobs-pre-upgrade.json ~/.claude-superpowers/cron/jobs.json
claw daemon uninstall && claw daemon install
```

### Full Rollback Checklist

1. Stop all services: `docker compose down`, `claw daemon uninstall`
2. Check out the previous working version
3. Restore `.env` if it was modified
4. Restore data files if they were modified
5. Reinstall Python dependencies: `pip install -e ".[dev]"`
6. Rebuild Docker images: `docker compose up -d --build`
7. Reinstall daemon: `claw daemon install`
8. Run verification: `claw status`, health check endpoints, `claw vault list`

---

## Testing Before Upgrade

Before upgrading in production, run the test suite:

```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -q \
  --ignore=tests/test_telegram_concurrency.py \
  --ignore=tests/test_vault.py
```

Known test notes:
- `test_telegram_concurrency.py` hangs; always ignore
- `test_vault.py` requires `age-keygen` binary; ignore if not installed
- Set `PYTHONPATH=.` so `msg_gateway` and `dashboard` packages resolve
