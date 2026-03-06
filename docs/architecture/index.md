# Architecture Overview

Nexus Core is built as a modular Python platform with eight integrated subsystems, a CLI entry point (`claw`), and optional Docker services for the full stack.

---

## System Diagram

```
+------------------------------------------------------------------+
|                         claw CLI (Click)                          |
|  vault | skill | cron | msg | ssh | browse | workflow | memory   |
|  agent | orchestrate | dag | pack | policy | watcher | status    |
+------+-------+------+------+------+------+-------+-------+------+
       |       |      |      |      |      |       |       |
       v       v      v      v      v      v       v       v
+------------------------------------------------------------------+
|                    Core Python Package                            |
|                                                                  |
|  +----------+  +---------+  +----------+  +----------+           |
|  |  Vault   |  |  Skill  |  |   Cron   |  |   Msg    |           |
|  | (age enc)|  | Registry|  |  Engine  |  | Gateway  |           |
|  +----------+  | + Loader|  |(APSched) |  |(FastAPI) |           |
|                +---------+  +----------+  +----------+           |
|  +----------+  +---------+  +----------+  +----------+           |
|  |   SSH    |  | Browser |  | Workflow |  |  Memory  |           |
|  |(Paramiko)|  |(Playwrt)|  |  Engine  |  | (SQLite) |           |
|  +----------+  +---------+  +----------+  +----------+           |
|                                                                  |
|  +----------+  +---------+  +----------+  +----------+           |
|  |  Agent   |  |   DAG   |  |  Policy  |  |  Watcher |           |
|  | Registry |  | Executor|  |  Engine  |  |(watchdog)|           |
|  +----------+  +---------+  +----------+  +----------+           |
+------------------------------------------------------------------+
       |              |              |              |
       v              v              v              v
+------------------------------------------------------------------+
|                     Infrastructure Layer                          |
|                                                                  |
|  Settings (.env)    SQLite (memory, cron)    Redis (pubsub)      |
|  Audit Log          Docker Compose           File System         |
+------------------------------------------------------------------+
```

---

## Component Interactions

### CLI Layer

The `claw` CLI is built with [Click](https://click.palletsprojects.com/). Each subsystem registers its own command group in `superpowers/cli.py`. There are 24 top-level commands covering all platform capabilities.

### Core Subsystems

1. **Vault** -- Encrypts credentials in a JSON blob using the `age` CLI tool. Identity keys are stored at `~/.claude-superpowers/age-identity.txt`. Credentials are accessed by skills only when explicitly permitted in `skill.yaml`.

2. **Skill System** -- Skills are directories under `skills/` with a `skill.yaml` manifest. The registry discovers them, validates manifests, and syncs slash commands as symlinks into `~/.claude/commands/`. The loader handles dependency checking and sandboxed execution.

3. **Cron Engine** -- APScheduler with SQLite job store. Supports four job types: `shell` (subprocess), `claude` (headless Claude CLI), `webhook` (HTTP POST), and `skill` (skill loader). Schedule expressions support cron, interval, and daily-at formats.

4. **Messaging** -- FastAPI gateway that normalizes send/receive across Telegram, Slack, Discord, email, and iMessage. Notification profiles map named profiles (`critical`, `info`, `daily-digest`) to channel+format combinations.

5. **SSH Fabric** -- Paramiko-based module with connection pooling. Supports running commands on individual hosts or groups. Health checks ping and SSH-test all configured hosts. Includes Home Assistant bridge for smart home control.

6. **Browser Engine** -- Playwright with Chromium. Supports headless and headed modes, session persistence (cookies, localStorage), DOM extraction helpers, and screenshot capture.

7. **Workflow Engine** -- YAML-defined multi-step workflows with step types: `shell`, `claude-prompt`, `skill`, `http`, and `approval-gate`. Supports conditions, quality gates, and rollback actions.

8. **Memory** -- SQLite database at `~/.claude-superpowers/memory.db` with tables for facts, preferences, project context, and conversation summaries. Auto-context injection queries relevant memories based on current directory and recent commands.

### Extended Subsystems

- **Agent Registry** -- Discovers and manages subagents under `subagents/`. Supports auto-recommendation based on task description.
- **DAG Executor** -- Dependency-aware parallel execution of workflow steps.
- **Policy Engine** -- Safety policies that gate command execution, file access, and output scanning for secrets.
- **Pack Manager** -- Bundles of skills, workflows, and agents that can be installed from local directories or git URLs.
- **File Watchers** -- `watchdog`-based directory monitors that trigger skills or workflows on file changes.
- **Reporting** -- Saves, lists, and exports operational reports.
- **Benchmarks** -- Performance measurement for orchestration scenarios.

---

## Data Flow

```
User Request
    |
    v
claw CLI (Click)
    |
    +---> Vault (decrypt creds) ---> age identity file
    |
    +---> Skill Loader ---> subprocess (bash/python script)
    |         |
    |         +---> Vault access (if permitted)
    |
    +---> Cron Engine ---> APScheduler ---> Job Runner
    |                                          |
    |                                          +---> shell / claude / webhook / skill
    |
    +---> Msg Gateway ---> Channel Adapters ---> Telegram / Slack / Discord / Email
    |
    +---> SSH Fabric ---> Paramiko ---> Remote Hosts
    |
    +---> Browser Engine ---> Playwright ---> Chromium
    |
    +---> Workflow Engine ---> Step Executor ---> (any of the above)
    |
    +---> Memory DB ---> SQLite queries
    |
    +---> Audit Log (append-only)
```

---

## Runtime Data

All runtime state lives under `~/.claude-superpowers/`:

```
~/.claude-superpowers/
  age-identity.txt       # age private key (chmod 600)
  vault.enc              # Encrypted JSON credential store
  memory.db              # Persistent memory SQLite database
  audit.log              # Append-only audit trail
  cron/
    jobs.json            # Job manifest
    jobstore.sqlite      # APScheduler trigger state
    output/{id}/         # Per-job execution logs
  browser/
    profiles/            # Saved browser sessions
  skills/                # Runtime skill data
  logs/
    cron-daemon.log      # Daemon log file
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| CLI | Click 8.x, Rich 13.x |
| Encryption | age (CLI subprocess) |
| Scheduling | APScheduler 3.x + SQLite |
| HTTP | FastAPI, aiohttp, uvicorn |
| Browser | Playwright (Chromium) |
| SSH | Paramiko 3.x |
| Persistence | SQLite, Redis 5.x |
| AI Integration | MCP (FastMCP), Anthropic SDK |
| File Watching | watchdog 4.x |
| Testing | pytest 8.x, ruff |
| Build | setuptools 69+, Docker Compose |

---

## Docker Services

The Docker Compose stack provides optional services:

| Service | Port | Purpose |
|---------|------|---------|
| Redis | 6379 | Session store, pubsub message bus |
| Message Gateway | 8100 | FastAPI messaging normalization |
| Dashboard | 8200 | Web UI for monitoring and control |
| Browser Engine | 8300 | Playwright + Chromium automation |
| Telegram Bot | -- | Inbound message handler |

All services are optional. The `claw` CLI works standalone without Docker.

---

## See Also

- [Component Reference](../reference/architecture.md) -- detailed component descriptions
- [CLI Reference](../reference/cli.md) -- all commands
- [Configuration](../reference/CONFIGURATION.md) -- environment variables
