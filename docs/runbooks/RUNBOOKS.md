# Runbooks

Operational procedures for deploying, rolling back, triaging incidents, and restoring from backups.

---

## Deploy Procedure

### Via Docker Compose

```bash
cd /home/ray/claude-superpowers

# 1. Pull latest code
git pull --ff-only

# 2. Check for config changes
diff .env .env.example   # Look for new variables

# 3. Build and deploy
docker compose up -d --build

# 4. Verify health
docker compose ps
curl http://localhost:8200/health
curl http://localhost:8100/health

# 5. Check logs for errors
docker compose logs --tail 50 dashboard
docker compose logs --tail 50 msg-gateway
```

### Via Deploy Skill

```bash
# Automated pipeline: git pull -> pip install -> docker build -> up -> health check -> test
python3 skills/deploy/run.py

# Exit codes:
#   0 = success
#   1 = health check failed
#   2 = error (git, docker, pip, or test failure)
```

### Via GitHub Actions

1. Push a version tag: `git tag v1.1.0 && git push origin v1.1.0`
2. The release workflow runs tests, builds Docker images to `ghcr.io`, and creates a GitHub release
3. The deploy workflow SSHes to the server, runs `git pull`, rebuilds, and verifies

Required secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

### Post-Deploy Verification

```bash
# Dashboard API responds
curl -u "admin:${DASHBOARD_PASS}" http://localhost:8200/api/status

# Message gateway responds
curl http://localhost:8100/health

# Cron daemon is running
claw daemon status

# Skills are discoverable
claw skill list

# Vault is accessible
claw vault list

# Run the test suite
PYTHONPATH=. pytest tests/ -q \
  --ignore=tests/test_telegram_concurrency.py \
  --ignore=tests/test_vault.py
```

---

## Rollback Procedure

### Docker Compose Rollback

```bash
cd /home/ray/claude-superpowers

# 1. Check what changed
git log --oneline -5

# 2. Roll back to previous commit
git checkout <previous-commit-hash>

# 3. Rebuild and restart
docker compose up -d --build

# 4. Verify
curl http://localhost:8200/health
claw daemon status
```

### Git-Based Rollback

```bash
# Revert the last commit (creates a new commit)
git revert HEAD
docker compose up -d --build

# Or reset to a specific tag
git checkout v1.0.0
docker compose up -d --build
```

### Rollback Checklist

1. Verify the target version works with the current `.env` configuration
2. Check if any database migrations need to be reversed (memory.db schema changes)
3. Restart the cron daemon: `claw daemon uninstall && claw daemon install`
4. Restart the file watcher if running: `systemctl --user restart claude-superpowers-watcher`
5. Test core functionality: vault access, skill execution, dashboard login

---

## Incident Triage

### Step 1: Identify the Problem

```bash
# Check service status
docker compose ps
claw daemon status
claw status

# Check recent audit log for errors
claw audit tail
claw audit search "error"
claw audit search "failed"

# Check Docker logs
docker compose logs --tail 100 dashboard
docker compose logs --tail 100 msg-gateway
```

### Step 2: Classify Severity

| Severity | Criteria | Response |
|----------|----------|----------|
| P0 - Critical | Dashboard down, vault inaccessible, cron daemon crashed | Fix immediately, notify via alternate channel |
| P1 - High | Messaging not sending, SSH health check failures | Fix within 1 hour |
| P2 - Medium | Single skill failing, browser profile corruption | Fix within 24 hours |
| P3 - Low | Log noise, cosmetic dashboard issues | Track in to-do list |

### Step 3: Common Failure Modes

**Dashboard not responding (port 8200)**

```bash
# Check container status
docker compose ps dashboard

# Check if port is in use
ss -tlnp | grep 8200

# Restart
docker compose restart dashboard

# If build error, check logs
docker compose logs dashboard
```

**Cron daemon not running**

```bash
claw daemon status

# Check systemd
systemctl --user status claude-superpowers-cron
journalctl --user -u claude-superpowers-cron --since "1 hour ago"

# Reinstall
claw daemon uninstall
claw daemon install
```

**Vault errors (age not found)**

```bash
# Verify age is installed
which age
which age-keygen

# Install if missing
sudo apt install -y age

# Reinitialize (safe to run if identity exists)
claw vault init

# Check permissions
ls -la ~/.claude-superpowers/age-identity.txt  # Should be -rw-------
ls -la ~/.claude-superpowers/vault.enc          # Should be -rw-------
```

**Redis connection refused**

```bash
# Check Redis container
docker compose ps redis
docker compose logs redis

# Restart Redis
docker compose restart redis

# Test connectivity
redis-cli -u redis://localhost:6379/0 ping
```

**Telegram bot not responding**

```bash
# Check if ALLOWED_CHAT_IDS is set
grep ALLOWED_CHAT_IDS .env

# Check if bot token is valid
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"

# Check bot logs
journalctl --user -u claude-superpowers-telegram --since "1 hour ago"
```

**Skill execution failure**

```bash
# Validate the skill
claw skill validate skills/<name>

# Check dependencies
which <dependency-binary>

# Run manually with verbose output
claw skill run <name>

# Check audit log
claw audit search "<skill-name>"
```

**SSH connection failures**

```bash
# Test SSH directly
ssh -v <user>@<host>

# Check host configuration
cat ~/.claude-superpowers/hosts.yaml

# Run health check
claw ssh health --json

# Check vault for password (if password auth)
claw vault get ssh:<alias>:password --reveal
```

### Step 4: Escalation

If the issue cannot be resolved:

1. Capture diagnostic output: `claw status`, `docker compose ps`, `claw audit tail`
2. Save the audit log: `cp ~/.claude-superpowers/audit.log ~/audit-$(date +%F).log`
3. Note the last known working state (git hash, deploy time)
4. Roll back to the last known working version (see Rollback Procedure)

---

## Backup and Restore

### What to Back Up

| File/Directory | Content | Priority |
|---------------|---------|----------|
| `~/.claude-superpowers/vault.enc` | Encrypted credentials | Critical |
| `~/.claude-superpowers/age-identity.txt` | Vault decryption key | Critical |
| `~/.claude-superpowers/memory.db` | Persistent memory store | High |
| `~/.claude-superpowers/cron/jobs.json` | Cron job definitions | High |
| `~/.claude-superpowers/hosts.yaml` | SSH host config | High |
| `~/.claude-superpowers/profiles.yaml` | Notification profiles | Medium |
| `~/.claude-superpowers/watchers.yaml` | File watcher rules | Medium |
| `~/.claude-superpowers/rotation_policies.yaml` | Credential rotation policies | Medium |
| `.env` | Environment configuration | High |
| `~/.claude-superpowers/audit.log` | Audit trail | Low (append-only, can be large) |
| `~/.claude-superpowers/cron/output/` | Job execution logs | Low |
| `~/.claude-superpowers/browser/profiles/` | Browser session data | Low |

### Backup Script

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="$HOME/backups/claude-superpowers/$(date +%F)"
DATA_DIR="$HOME/.claude-superpowers"
PROJECT_DIR="/home/ray/claude-superpowers"

mkdir -p "$BACKUP_DIR"

# Critical files
cp "$DATA_DIR/vault.enc" "$BACKUP_DIR/"
cp "$DATA_DIR/age-identity.txt" "$BACKUP_DIR/"
chmod 600 "$BACKUP_DIR/age-identity.txt" "$BACKUP_DIR/vault.enc"

# Configuration
cp "$DATA_DIR/memory.db" "$BACKUP_DIR/" 2>/dev/null || true
cp "$DATA_DIR/cron/jobs.json" "$BACKUP_DIR/" 2>/dev/null || true
cp "$DATA_DIR/hosts.yaml" "$BACKUP_DIR/" 2>/dev/null || true
cp "$DATA_DIR/profiles.yaml" "$BACKUP_DIR/" 2>/dev/null || true
cp "$DATA_DIR/watchers.yaml" "$BACKUP_DIR/" 2>/dev/null || true
cp "$DATA_DIR/rotation_policies.yaml" "$BACKUP_DIR/" 2>/dev/null || true
cp "$PROJECT_DIR/.env" "$BACKUP_DIR/dot-env" 2>/dev/null || true

echo "Backup saved to $BACKUP_DIR"
ls -la "$BACKUP_DIR"
```

### Restore Procedure

```bash
BACKUP_DIR="$HOME/backups/claude-superpowers/2026-03-01"  # Adjust date
DATA_DIR="$HOME/.claude-superpowers"

# Stop services first
docker compose -f /home/ray/claude-superpowers/docker-compose.yaml down
claw daemon uninstall 2>/dev/null || true

# Restore critical files
cp "$BACKUP_DIR/vault.enc" "$DATA_DIR/"
cp "$BACKUP_DIR/age-identity.txt" "$DATA_DIR/"
chmod 600 "$DATA_DIR/age-identity.txt" "$DATA_DIR/vault.enc"

# Restore configuration
cp "$BACKUP_DIR/memory.db" "$DATA_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/jobs.json" "$DATA_DIR/cron/" 2>/dev/null || true
cp "$BACKUP_DIR/hosts.yaml" "$DATA_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/profiles.yaml" "$DATA_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/watchers.yaml" "$DATA_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/rotation_policies.yaml" "$DATA_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/dot-env" "/home/ray/claude-superpowers/.env" 2>/dev/null || true

# Restart services
cd /home/ray/claude-superpowers
docker compose up -d
claw daemon install

# Verify
claw vault list
claw cron list
claw memory stats
claw status
```

### Memory Database Backup

The SQLite memory database supports online backup:

```bash
# Copy while running (WAL mode makes this safe)
cp ~/.claude-superpowers/memory.db ~/memory-backup-$(date +%F).db

# Or use sqlite3 backup command
sqlite3 ~/.claude-superpowers/memory.db ".backup ~/memory-backup-$(date +%F).db"
```

### Automated Backup via Cron

```bash
claw cron add daily-backup \
  --type shell \
  --command "/home/ray/claude-superpowers/scripts/backup.sh" \
  --schedule "daily at 02:00" \
  --output "info"
```

---

## Log Rotation

### Audit Log

The audit log grows indefinitely. Rotate it periodically:

```bash
# Compress and rotate
cd ~/.claude-superpowers
mv audit.log "audit-$(date +%F).log"
gzip "audit-$(date +%F).log"
# The next audit write will create a fresh audit.log
```

### Cron Output Logs

```bash
# Prune logs older than 30 days
claw cron logs --prune 30d

# Manual cleanup
find ~/.claude-superpowers/cron/output/ -name "*.log" -mtime +30 -delete
```

### Daemon Logs

```bash
# The cron daemon log
ls -lh ~/.claude-superpowers/logs/cron-daemon.log

# Truncate if too large
> ~/.claude-superpowers/logs/cron-daemon.log
```
