# Configuration Reference

Complete reference for all environment variables, configuration files, and schemas used by claude-superpowers.

---

## Environment Variables (.env)

The `.env` file in the project root is loaded by `superpowers/config.py` at startup. Variables already set in the shell environment take precedence over `.env` values.

### LLM

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ANTHROPIC_API_KEY` | string | `""` | Anthropic API key for Claude-type cron jobs and intake pipeline |
| `OPENAI_API_KEY` | string | `""` | OpenAI API key for ChatGPT/OpenAI provider and fallback |
| `OPENAI_MODEL` | string | `gpt-4o` | Default model used by the OpenAI provider |
| `LLM_FALLBACK` | boolean | `true` | If `true`, Claude primary calls auto-fallback to OpenAI when `OPENAI_API_KEY` is set |

### Messaging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SLACK_BOT_TOKEN` | string | `""` | Slack bot token (`xoxb-...`) for sending messages |
| `TELEGRAM_BOT_TOKEN` | string | `""` | Telegram Bot API token from @BotFather |
| `TELEGRAM_DEFAULT_CHAT_ID` | string | `""` | Default Telegram chat ID for outbound notifications |
| `DISCORD_BOT_TOKEN` | string | `""` | Discord bot token for sending messages |
| `SMTP_HOST` | string | `""` | SMTP server hostname (e.g., `smtp.gmail.com`) |
| `SMTP_USER` | string | `""` | SMTP login username |
| `SMTP_PASS` | string | `""` | SMTP login password or app-specific password |
| `SMTP_PORT` | integer | `587` | SMTP port (587 for STARTTLS, 465 for SSL) |
| `SMTP_FROM` | string | `""` | From address for outbound emails |

### Dashboard

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DASHBOARD_USER` | string | `""` | HTTP Basic auth username. Code default is empty string; `.env.example` uses `admin` as a template value. **Must be set** to a non-trivial value |
| `DASHBOARD_PASS` | string | `""` | HTTP Basic auth password. **Must be set** -- no insecure default |
| `DASHBOARD_SECRET` | string | `""` | JWT signing key for session tokens. Auto-generated at startup if left empty |

### Infrastructure

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_URL` | string | `redis://localhost:6379/0` | Redis connection URL for session storage and pubsub |
| `BROWSER_ENGINE_URL` | string | `http://browser-engine:8300` | URL for the Playwright browser engine service. Set automatically in Docker Compose; override for local dev |

### Vault

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VAULT_IDENTITY_FILE` | string | `~/.claude-superpowers/vault.key` | Path to the age identity (private key) file |

### SSH Fabric

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SSH_CONNECT_TIMEOUT` | integer | `10` | SSH connection timeout in seconds |
| `SSH_COMMAND_TIMEOUT` | integer | `30` | SSH command execution timeout in seconds |
| `SSH_AUTO_ADD_HOST_KEYS` | boolean | `false` | If `true`, unknown SSH host keys are auto-accepted. Leave `false` for strict host key verification |

### Telegram Bot

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ALLOWED_CHAT_IDS` | string | `""` | Comma-separated list of allowed Telegram chat IDs. If empty, **all messages are rejected** |
| `TELEGRAM_SESSION_TTL` | integer | `3600` | Conversation history TTL in seconds |
| `TELEGRAM_MAX_HISTORY` | integer | `20` | Maximum messages retained per chat session |
| `TELEGRAM_MAX_PER_CHAT` | integer | `2` | Maximum concurrent jobs per chat |
| `TELEGRAM_MAX_GLOBAL` | integer | `5` | Maximum concurrent jobs across all chats |
| `TELEGRAM_QUEUE_OVERFLOW` | integer | `10` | Maximum queued jobs before rejecting new requests |
| `TELEGRAM_MODE` | string | `polling` | Transport mode: `webhook` or `polling` |
| `TELEGRAM_WEBHOOK_URL` | string | `""` | Public HTTPS URL for webhook endpoint (e.g., `https://bot.example.com/webhook/telegram`). Required when `TELEGRAM_MODE=webhook` |
| `TELEGRAM_ADMIN_CHAT_ID` | string | `""` | Admin chat ID for receiving access request notifications |

### Home Automation

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HOME_ASSISTANT_URL` | string | `""` | Home Assistant base URL (e.g., `http://192.168.30.50:8123`) |
| `HOME_ASSISTANT_TOKEN` | string | `""` | Home Assistant long-lived access token |

### Model Routing (Phase F)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CHAT_MODEL` | string | `claude` | Model/provider for interactive chat. Supports `claude`, `openai`, `chatgpt` (alias), or custom provider names |
| `JOB_MODEL` | string | `claude` | Model/provider for background cron and workflow jobs. Supports `claude`, `openai`, `chatgpt` (alias), or custom provider names |

### Security (Phase G)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENVIRONMENT` | string | `development` | Runtime environment: `development` or `production`. Setting `production` auto-enables `FORCE_HTTPS` |
| `FORCE_HTTPS` | boolean | `false` | Enforce HTTPS for all connections. Automatically `true` when `ENVIRONMENT=production` |
| `WEBHOOK_REQUIRE_SIGNATURE` | boolean | `true` | Fail-closed webhook signature validation. Set to `false` to disable (not recommended) |
| `RATE_LIMIT_PER_IP` | integer | `60` | Maximum requests per minute per IP address |
| `RATE_LIMIT_PER_USER` | integer | `120` | Maximum requests per minute per authenticated user |
| `SLACK_SIGNING_SECRET` | string | `""` | Slack HMAC signing secret for inbound webhook validation. Required for Slack webhooks |
| `DISCORD_PUBLIC_KEY` | string | `""` | Discord application public key (hex) for Ed25519 webhook verification. Required for Discord webhooks |

### Data Directory

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SUPERPOWERS_DATA_DIR` | string | `~/.claude-superpowers` | Override the base data directory |
| `CLAUDE_SUPERPOWERS_DATA_DIR` | string | `~/.claude-superpowers` | Legacy alias for `SUPERPOWERS_DATA_DIR` |

---

## Configuration Files

### `~/.claude-superpowers/hosts.yaml` -- SSH Hosts

Defines hosts for the SSH fabric. Used by `claw ssh` commands.

```yaml
hosts:
  - alias: proxmox              # Short name (required)
    hostname: 192.168.30.10     # IP or DNS name (required)
    port: 22                    # SSH port (default: 22)
    username: root              # Login user (default: root)
    auth: key                   # Auth method: key | password | agent (default: key)
    key_file: ~/.ssh/id_ed25519 # Private key path (for auth: key)
    groups:                     # Host groups (default: [all])
      - servers
      - hypervisors
    tags:                       # Arbitrary metadata (default: {})
      role: hypervisor
```

**Field reference:**

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `alias` | yes | -- | string | Short name used in CLI commands |
| `hostname` | yes | -- | string | IP address or DNS hostname |
| `port` | no | `22` | integer | SSH port |
| `username` | no | `root` | string | SSH login username |
| `auth` | no | `key` | enum | `key`, `password`, or `agent` |
| `key_file` | no | `""` | string | Path to SSH private key |
| `groups` | no | `["all"]` | list[string] | Group membership; `all` is auto-appended |
| `tags` | no | `{}` | dict | Key-value metadata |

Vault keys used by SSH:

| Vault Key | Purpose |
|-----------|---------|
| `ssh:<alias>:password` | Password for `password` auth |
| `ssh:<alias>:passphrase` | Key passphrase for `key` auth |

### `~/.claude-superpowers/profiles.yaml` -- Notification Profiles

Maps profile names to one or more channel+target pairs. Used by `claw msg notify`.

```yaml
critical:
  - channel: slack
    target: "#alerts"
  - channel: telegram
    target: "123456789"

info:
  - channel: slack
    target: "#general"

daily-digest:
  - channel: email
    target: admin@example.com
  - channel: slack
    target: "#daily"
```

**Entry fields:**

| Field | Type | Description |
|-------|------|-------------|
| `channel` | enum | `slack`, `telegram`, `discord`, `email` |
| `target` | string | Channel-specific target: Slack channel, Telegram chat ID, Discord channel ID, email address |

### `~/.claude-superpowers/watchers.yaml` -- File Watcher Rules

Defines file monitoring rules for the watcher daemon. Used by `claw watcher`.

```yaml
- name: torrent-mover           # Unique rule ID (required)
  path: ~/Downloads/*.torrent   # Directory or glob pattern (required)
  events: [created]             # Event types (default: [created])
  action: move                  # Action type (required)
  command: /mnt/data/watch/     # Action-specific target (required)
  args: {}                      # Extra arguments (default: {})
  enabled: true                 # Active flag (default: true)
```

**Fields:**

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `name` | yes | -- | string | Unique rule identifier |
| `path` | yes | -- | string | Directory or glob pattern to monitor |
| `events` | no | `[created]` | list[enum] | `created`, `modified`, `deleted`, `moved` |
| `action` | yes | -- | enum | `shell`, `skill`, `workflow`, `move`, `copy` |
| `command` | yes | -- | string | Command to run or target directory |
| `args` | no | `{}` | dict | Extra arguments (exposed as `WATCHER_{KEY}` env vars for shell actions) |
| `enabled` | no | `true` | boolean | Whether the rule is active |

**Action types:**

| Action | `command` value | Behavior |
|--------|----------------|----------|
| `shell` | Shell command | Runs command with `WATCHER_FILE` set to triggering path |
| `skill` | Skill name | Runs the named skill with `file` argument |
| `workflow` | Workflow name | Triggers the named workflow |
| `move` | Target directory | Moves the triggering file to the directory |
| `copy` | Target directory | Copies the triggering file to the directory |

### `~/.claude-superpowers/rotation_policies.yaml` -- Credential Rotation

Defines rotation policies for vault credentials.

```yaml
ANTHROPIC_API_KEY:
  max_age_days: 90
  last_rotated: "2026-01-15T00:00:00+00:00"

SLACK_BOT_TOKEN:
  max_age_days: 180
  last_rotated: "2025-12-01T00:00:00+00:00"
```

**Fields:**

| Field | Default | Type | Description |
|-------|---------|------|-------------|
| `max_age_days` | `90` | integer | Maximum days before credential is considered expired |
| `last_rotated` | `""` | string (ISO 8601) | Date when the credential was last rotated |

Warning is raised at 80% of `max_age_days`. Expired status at 100%.

---

## Skill Manifest Schema (`skill.yaml`)

Every skill directory must contain a `skill.yaml` manifest.

```yaml
name: network-scan              # Unique kebab-case ID (required)
version: "0.1.0"                # Semver string (required)
description: "Scan subnets"     # One-line summary (required)
author: DreDay                  # Author name (required)
script: run.sh                  # Entry point, relative to skill dir (required)
slash_command: true             # Register as Claude Code slash command (default: false)
triggers: []                    # Event triggers (default: [])
dependencies: [nmap, jq]        # Required binaries on PATH (default: [])
permissions: [ssh, vault]       # Permission scopes (default: [])
```

**Field reference:**

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `name` | yes | -- | string | Kebab-case identifier, unique across all skills |
| `version` | yes | -- | string | Semantic version |
| `description` | yes | -- | string | Shown in `claw skill list` output |
| `author` | yes | -- | string | Author attribution |
| `script` | yes | -- | string | Entry point script relative to skill directory |
| `slash_command` | no | `false` | boolean | If true, `claw skill sync` creates a Claude Code slash command |
| `triggers` | no | `[]` | list[string] | Event triggers for cron integration |
| `dependencies` | no | `[]` | list[string] | Binaries checked via `which` before execution |
| `permissions` | no | `[]` | list[string] | Permission scopes for sandboxed execution |

**Permissions:**

| Permission | Effect |
|------------|--------|
| `vault` | Sandboxed execution receives full environment including vault secrets |
| `ssh` | Declares SSH access intent |
| `nmap` | Declares network scanning capability |
| (custom) | Allowed; only `vault` is currently enforced |

Without `vault` permission, sandboxed execution strips the environment to `PATH`, `HOME`, `LANG`, `TERM` only.

---

## Workflow Schema (`workflows/*.yaml`)

Workflow definitions live in the `workflows/` directory.

```yaml
name: deploy                    # Workflow name (required)
description: "Pull, test, deploy, verify"  # Summary (required)
notify_profile: critical        # Notification profile to use on completion (optional)

steps:                          # Ordered list of steps (required)
  - name: git-pull              # Step name (required)
    type: shell                 # Step type (required)
    command: "git pull"         # Command/target (required)
    on_failure: abort           # Failure behavior (default: abort)
    timeout: 300                # Timeout in seconds (default: 300)
    condition: ""               # Run condition (default: "" = always)
    args: {}                    # Extra arguments (default: {})

rollback:                       # Rollback steps, run when on_failure=rollback triggers
  - name: undo-deploy
    type: shell
    command: "docker compose down"
```

**Step types:**

| Type | `command` value | Description |
|------|----------------|-------------|
| `shell` | Shell command | Runs via `subprocess.run()` |
| `claude_prompt` | Prompt text | Runs through the job LLM provider (`JOB_MODEL`) with optional OpenAI fallback |
| `skill` | Skill name | Executes a registered skill |
| `http` | URL | HTTP request (POST by default, configurable via `args.method`) |
| `approval_gate` | -- | Pauses for human confirmation (auto-approved in dry-run) |

**Step options:**

| Field | Default | Type | Description |
|-------|---------|------|-------------|
| `on_failure` | `abort` | enum | `abort` (stop workflow), `continue` (proceed), `rollback` (run rollback steps) |
| `timeout` | `300` | integer | Maximum seconds before step is killed |
| `condition` | `""` | enum | `previous.ok`, `previous.failed`, `always`, or `""` (always) |
| `args` | `{}` | dict | Extra arguments; shell steps receive these as `WF_*` env vars |

---

## Cron Job Configuration

Jobs are stored in `~/.claude-superpowers/cron/jobs.json`:

```json
{
  "network-scan-6h": {
    "type": "skill",
    "skill": "network-scan",
    "schedule": "every 6h",
    "enabled": true,
    "created": "2026-02-28T10:30:00Z"
  }
}
```

**Schedule formats:**

| Format | Example | Description |
|--------|---------|-------------|
| Cron expression | `"0 */6 * * *"` | Standard 5-field cron: `minute hour day month weekday` |
| Interval | `"every 6h"` | Units: `s`, `m`, `h`, `d`. Combinable: `every 2h30m` |
| Daily-at | `"daily at 09:00"` | Once per day at the specified HH:MM |

**Job types:**

| Type | Required Fields | Description |
|------|----------------|-------------|
| `shell` | `command` | Subprocess execution |
| `claude` | `prompt` | LLM prompt via configured job provider (`JOB_MODEL`) |
| `webhook` | `url`, optional `body` | HTTP POST to a URL |
| `skill` | `skill`, optional `args` | Runs a registered skill |

**Output routing** (optional `output` field):

| Format | Example | Description |
|--------|---------|-------------|
| Direct | `"slack:#alerts"` | `<channel>:<target>` |
| Profile | `"critical"` | Uses a notification profile |

---

## Docker Compose Services

Defined in `docker-compose.yaml`:

| Service | Port | Image | Description |
|---------|------|-------|-------------|
| `redis` | 6379 | `redis:7-alpine` | Session storage, message pubsub |
| `msg-gateway` | 8100 | Built from `msg_gateway/Dockerfile` | HTTP API for sending messages |
| `dashboard` | 8200 | Built from `dashboard/Dockerfile` | Web UI + REST API |
| `browser-engine` | 8300 | Built from `browser_engine/Dockerfile` | Playwright + Chrome headless browser automation engine |
| `telegram-bot` | -- | Built from `telegram-bot/Dockerfile` | Telegram bot service (no exposed port; connects outbound to Telegram API) |

All services read from `.env` via `env_file`. The dashboard mounts `~/.claude-superpowers` for access to jobs, memory, and audit data. The browser-engine mounts `~/.claude-superpowers/browser/profiles` for session persistence.

---

## Settings Dataclass

`superpowers/config.py` defines a `Settings` dataclass loaded by `Settings.load()`. The `.env` file is read with a minimal built-in parser (no external dependency). Only variables not already set in the shell environment are loaded from `.env`.

```python
from superpowers.config import Settings

settings = Settings.load()
print(settings.redis_url)          # "redis://localhost:6379/0"
print(settings.data_dir)           # Path("~/.claude-superpowers")
```

Call `settings.ensure_dirs()` to create all required subdirectories under `data_dir`.
