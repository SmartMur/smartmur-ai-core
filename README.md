# Claude Superpowers

A local-first automation platform that gives Claude Code autonomous capabilities: encrypted credential management, pluggable skills, scheduled jobs, multi-channel messaging, browser automation, SSH fabric, workflow orchestration, persistent memory, and file watchers. All running on your own hardware.

**CLI**: `claw` | **Python 3.12+** | **982 tests** | **12 skills** | **4 workflows** | **43 MCP tools** | **44 REST endpoints**

---

## Architecture

```
                          You / Claude Code / Telegram Bot
                                     |
                          +----------+-----------+
                          |     claw CLI (Click) |
                          |  claw-mcp (MCP/stdio)|
                          +----------+-----------+
                                     |
        +-------+--------+----------+----------+--------+-------+--------+
        |       |        |          |          |        |       |        |
        v       v        v          v          v        v       v        v
   +--------+ +------+ +------+ +-------+ +------+ +------+ +------+ +-------+
   | Vault  | |Skills| | Cron | |  Msg  | |  SSH | |Browse| |Work- | |Memory |
   | (age)  | |Regis-| |Engine| |Gateway| |Fabric| |Engine| |flows | | Store |
   |        | | try  | | APSch| | Slack | |Param-| |Play- | | YAML | |SQLite |
   |        | |Loader| | SQLite |Telegr.| | iko  | |wright| |Engine| |       |
   +--------+ +------+ +------+ | Disc. | +------+ +------+ +------+ +-------+
                                 | Email |
                                 +-------+
        |       |        |          |          |        |       |        |
        +-------+--------+----------+----------+--------+-------+--------+
                                     |
                          +----------+-----------+
                          |   Settings / .env    |
                          |   Audit Log (JSONL)  |
                          |   File Watchers      |
                          +----------------------+
                                     |
                    +----------------+----------------+
                    |                |                 |
               Dashboard       Docker Compose     Telegram Bot
             (FastAPI+Alpine)  (redis, gateway,   (polling, auth,
              port 8200         dashboard)         sessions)
```

### Runtime Data

All state lives in `~/.claude-superpowers/`:

```
~/.claude-superpowers/
  age-identity.txt      # age private key (chmod 600)
  vault.enc             # Encrypted credential store
  audit.log             # Append-only audit log (JSONL)
  memory.db             # SQLite memory store
  rotation_policies.yaml
  profiles.yaml         # Notification profiles
  hosts.yaml            # SSH host definitions
  watchers.yaml         # File watcher rules
  cron/
    jobs.json           # Job manifest
    jobstore.sqlite     # APScheduler state
    output/{id}/        # Per-job execution logs
  browser/profiles/     # Playwright session storage
  runtime/              # Intake pipeline state
  ssh/health.json       # SSH health report
  logs/                 # Daemon logs
```

---

## Quickstart

```bash
# 1. Clone
git clone <repo-url> claude-superpowers
cd claude-superpowers

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install
pip install -e ".[dev]"

# 4. Install age (required for vault)
# Debian/Ubuntu:
sudo apt install -y age
# macOS:
brew install age

# 5. Configure
cp .env.example .env
# Edit .env with your tokens (Slack, Telegram, etc.)

# 6. Initialize vault
claw vault init

# 7. Start Docker services (optional)
docker compose up -d

# 8. Verify
claw --version
claw status
```

### Install Playwright (for browser automation)

```bash
pip install playwright
playwright install chromium
```

---

## How It Works

### Skills

Skills are self-contained automation units in `skills/`. Each has a `skill.yaml` manifest and an executable script (`run.sh` or `run.py`). Skills can be run via CLI, scheduled as cron jobs, triggered by file watchers, or invoked from workflows.

```bash
claw skill list                          # List all skills
claw skill run heartbeat                 # Run a skill
claw skill create --name my-tool --type bash  # Scaffold a new skill
claw skill sync                          # Register slash commands
```

12 built-in skills: `backup-status`, `cloudflared-fixer`, `deploy`, `docker-monitor`, `github-admin`, `heartbeat`, `infra-fixer`, `network-scan`, `qa-guardian`, `ssl-cert-check`, `tunnel-setup`, `workspace-intake-smoke`.

### Cron / Scheduler

APScheduler-based daemon supporting four job types (`shell`, `claude`, `webhook`, `skill`) and three schedule formats (cron expressions, intervals, daily-at). Runs as a systemd user service on Linux or launchd agent on macOS.

```bash
claw cron add my-job --type skill --skill heartbeat --schedule "every 15m"
claw cron list
claw daemon install
```

### Messaging

Multi-channel messaging via Slack, Telegram, Discord, and email. Notification profiles fan out messages to multiple channels at once.

```bash
claw msg send slack "#alerts" "deploy complete"
claw msg notify critical "PVE1 is down"
```

### SSH Fabric

Remote command execution across hosts defined in `~/.claude-superpowers/hosts.yaml`. Connection pooling via paramiko, health checks with ICMP ping and SSH probes, Home Assistant integration.

```bash
claw ssh proxmox "uptime"
claw ssh servers "df -h"
claw ssh health
```

### Browser Automation

Playwright-based browser engine with persistent profiles, screenshots, text/table extraction, form filling, and JavaScript evaluation.

```bash
claw browse open https://example.com --headed
claw browse screenshot https://example.com --selector "#main"
claw browse extract https://example.com --selector "h1"
```

### Workflows

YAML-defined multi-step pipelines with conditions, approval gates, rollback, and notification integration. Step types: `shell`, `claude_prompt`, `skill`, `http`, `approval_gate`.

```bash
claw workflow list
claw workflow run deploy --dry-run
claw workflow run deploy
```

4 built-in workflows: `deploy`, `backup`, `morning-brief`, `qa-guardian`.

### Memory

SQLite-backed persistent memory store with categories (`fact`, `preference`, `project_context`, `conversation_summary`), search, decay, and auto-context injection for Claude prompts.

```bash
claw memory remember "db-host" "timescale.local:5432" --project hommie
claw memory search "ssh"
claw memory context --project hommie
```

### File Watchers

Directory monitoring via `watchdog` that triggers actions (`shell`, `skill`, `workflow`, `move`, `copy`) on file events. Configured in `~/.claude-superpowers/watchers.yaml`.

```bash
claw watcher list
claw watcher start
```

### Vault

age-encrypted credential store. Atomic writes, sandboxed injection into skills, optional macOS Keychain integration.

```bash
claw vault init
claw vault set API_KEY sk-abc123
claw vault get API_KEY --reveal
```

### Dashboard

Web UI at port 8200 (FastAPI + Alpine.js + htmx). 44 REST API endpoints across 11 routers covering all subsystems. Protected by HTTP Basic authentication.

```bash
claw dashboard                    # Start locally
docker compose up dashboard       # Via Docker
```

### MCP Server

43 native Claude Code tools exposed via the Model Context Protocol. Messaging, SSH, browser, workflows, cron, skills, memory, vault, and audit -- all callable directly from Claude Code without shell commands.

```json
{
  "mcpServers": {
    "claw": {
      "command": "claw-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

### Intake Pipeline

Request orchestration system that extracts requirements from free-form text, maps them to skills, assigns agent roles (`planner`, `executor`, `verifier`), and executes in parallel. Telegram notifications at start/finish.

```bash
claw intake run "scan network and check docker health" --execute
```

---

## Feature Summary

| Subsystem | Highlights |
|-----------|-----------|
| Vault | age encryption, atomic writes, sandboxed injection |
| Skills | 12 built-in, auto-scaffold, slash command sync |
| Cron | 4 job types, 3 schedule formats, systemd/launchd |
| Messaging | Slack, Telegram, Discord, email; notification profiles |
| SSH | Paramiko pool, host groups, health checks, Home Assistant |
| Browser | Playwright, persistent profiles, DOM extraction |
| Workflows | 4 built-in, conditions, rollback, approval gates |
| Memory | SQLite, categories, decay, auto-context injection |
| Watchers | 5 action types, glob patterns, event filters |
| Dashboard | 44 endpoints, 11 pages, HTTP Basic auth |
| MCP Server | 43 tools, stdio protocol, lazy initialization |
| Intake | Role routing, parallel execution, Telegram notifications |
| Audit | Append-only JSONL, search, tail |
| CI/CD | GitHub Actions: lint, test matrix, Docker build, deploy |

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | Component diagram, directory structure, tech stack |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every env var, config file, and schema reference |
| [docs/SECURITY.md](docs/SECURITY.md) | Auth model, vault, sandboxing, hardening, risks |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker Compose, systemd, reverse proxy, TLS |
| [docs/RUNBOOKS.md](docs/RUNBOOKS.md) | Deploy, rollback, incident triage, backup/restore |
| [docs/UPGRADE.md](docs/UPGRADE.md) | Version migration, breaking changes, rollback |
| [docs/getting-started.md](docs/getting-started.md) | Installation and first-skill walkthrough |
| [docs/vault.md](docs/vault.md) | Encrypted credential store |
| [docs/skills.md](docs/skills.md) | Skill system, manifests, loader, sandboxing |
| [docs/cron.md](docs/cron.md) | Scheduler, job types, daemon management |
| [docs/messaging.md](docs/messaging.md) | Multi-channel messaging, profiles |
| [docs/ssh.md](docs/ssh.md) | SSH fabric, hosts, health checks, Home Assistant |
| [docs/browser.md](docs/browser.md) | Playwright engine, profiles, DOM toolkit |
| [docs/workflows.md](docs/workflows.md) | YAML workflows, step types, rollback |
| [docs/memory.md](docs/memory.md) | Persistent memory, categories, decay |
| [docs/watchers.md](docs/watchers.md) | File watchers, actions, rules |
| [docs/dashboard.md](docs/dashboard.md) | Web UI, REST API, authentication |
| [docs/telegram-bot.md](docs/telegram-bot.md) | Telegram bot architecture, commands, modes |
| [docs/mcp-server.md](docs/mcp-server.md) | MCP tools for Claude Code |
| [docs/intake.md](docs/intake.md) | Intake orchestration pipeline |
| [docs/ci-cd.md](docs/ci-cd.md) | GitHub Actions CI/CD pipelines |
| [docs/heartbeat.md](docs/heartbeat.md) | Infrastructure health check skill |
| [docs/cloudflared-setup.md](docs/cloudflared-setup.md) | Cloudflare tunnel setup |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| CLI | Click 8.x |
| Terminal | Rich 13.x |
| Encryption | age (CLI subprocess) |
| Scheduling | APScheduler 3.x + SQLite |
| HTTP/API | FastAPI, aiohttp, uvicorn |
| Browser | Playwright (Chromium) |
| SSH | Paramiko 3.x |
| Messaging | slack_sdk, urllib (Telegram/Discord), smtplib |
| Persistence | SQLite (memory, cron), Redis (sessions, pubsub) |
| Frontend | Alpine.js, htmx |
| Testing | pytest 8.x |
| Linting | ruff |
| MCP | mcp (FastMCP) |
| Containers | Docker Compose |

---

## Project Structure

```
claude-superpowers/
  superpowers/            # Core Python package
    cli.py                # Click entry point (claw)
    vault.py              # age-encrypted vault
    skill_registry.py     # Skill discovery + validation
    skill_loader.py       # Execution + sandboxing
    cron_engine.py        # APScheduler setup
    cron_runner.py        # Job execution
    config.py             # Settings dataclass + .env loader
    audit.py              # Append-only audit log
    intake.py             # Request orchestration
    channels/             # Messaging adapters
    memory/               # SQLite memory store
    browser/              # Playwright engine (re-exported)
    ssh_fabric/           # SSH connection pool + executor
    workflow/             # YAML workflow engine
    watcher/              # File watcher daemon
    mcp_server.py         # MCP tool server
  skills/                 # Skill directories (skill.yaml + scripts)
  workflows/              # YAML workflow definitions
  msg_gateway/            # FastAPI messaging gateway
  dashboard/              # FastAPI web dashboard
  telegram-bot/           # Telegram bot polling service
  tests/                  # 982 tests
  docs/                   # Documentation
  deploy/                 # Deployment configs
  docker-compose.yaml     # Redis + gateway + dashboard
  pyproject.toml          # Package metadata + dependencies
  .env.example            # Configuration template
```

---

## License

Private project. All rights reserved.
