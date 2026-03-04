# Architecture Overview

## Project Vision

**claude-superpowers** (CLI: `claw`) gives Claude Code autonomous capabilities that mirror what [OpenClaw](https://github.com/open-claw) provides for other LLM agents: encrypted credential management, a pluggable skill system, scheduled jobs, messaging integrations, remote execution, and multi-step workflow orchestration.

The goal is simple: Claude Code should be able to do anything a senior engineer can do from a terminal -- store secrets safely, run scripts, scan networks, send notifications, SSH into boxes, and chain it all together.

## Directory Structure

```
claude-superpowers/
├── superpowers/              # Core Python package
│   ├── __init__.py           # Package version
│   ├── cli.py                # Click entry point (`claw`)
│   ├── cli_vault.py          # `claw vault` subcommands
│   ├── cli_skill.py          # `claw skill list/info/run/sync/validate`
│   ├── cli_skill_create.py   # `claw skill create` interactive scaffolder
│   ├── cli_cron.py           # `claw cron` + `claw daemon` subcommands
│   ├── config.py             # Settings dataclass + .env loader
│   ├── vault.py              # age-encrypted credential store
│   ├── skill_registry.py     # Skill discovery, validation, slash-command sync
│   ├── skill_loader.py       # Dependency checking + sandboxed execution
│   ├── skill_creator.py      # Skill scaffolding templates
│   ├── cron_engine.py        # APScheduler setup, schedule parsing, job dispatch
│   ├── cron_runner.py        # Job execution: subprocess, claude, HTTP, skill
│   ├── launchd.py            # Service management (systemd/launchd)
│   ├── job_runner.py         # Git-branch job orchestration
│   ├── setup_wizard.py       # Interactive setup wizard
│   ├── llm_provider.py       # LLM model routing abstraction
│   ├── template_manager.py   # Skill/workflow template management
│   ├── container_watchdog.py # Docker container health monitoring
│   └── voice_transcriber.py  # Audio transcription support
├── skills/                   # Skill directories (each has skill.yaml)
│   ├── _template/            # Copy-paste starter skill
│   ├── heartbeat/            # Infrastructure health check
│   ├── network-scan/         # Scan home network subnets
│   ├── deploy/               # Local deployment pipeline
│   ├── infra-fixer/          # Docker infrastructure monitor
│   ├── qa-guardian/          # Code quality scanner
│   ├── container-watchdog/   # Docker container health watcher
│   ├── ops-report/           # Operational reporting
│   └── ...                   # 14 skills total
├── msg_gateway/              # FastAPI messaging gateway + Telegram bot
├── dashboard/                # FastAPI web dashboard (Alpine.js + htmx)
├── workflows/                # YAML workflow definitions
├── tests/                    # 982 tests
├── docs/                     # Documentation
├── deploy/                   # Deployment configs (systemd, CI/CD)
└── pyproject.toml            # Project metadata + dependencies
```

### Runtime Data (`~/.claude-superpowers/`)

```
~/.claude-superpowers/
├── age-identity.txt          # age private key (chmod 600)
├── vault.enc                 # Encrypted JSON credential store
├── skills/                   # Runtime skill data
├── cron/                     # Cron job state
│   ├── jobs.json             # Job manifest
│   ├── jobstore.sqlite       # APScheduler trigger state
│   └── output/{id}/          # Per-job execution logs
├── vault/                    # (reserved)
└── logs/                     # Execution logs
    └── cron-daemon.log       # Cron daemon log file
```

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    claw CLI (Click)                      │
│  vault | skill | cron | msg | workflow | ssh | status   │
└──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┘
       │      │      │      │      │      │      │
       v      │      │      │      │      │      │
┌──────────┐  │      │      │      │      │      │
│  Vault   │  │      │      │      │      │      │
│  (age)   │  │      │      │      │      │      │
└──────────┘  │      │      │      │      │      │
              v      │      │      │      │      │
       ┌────────────┐│      │      │      │      │
       │  Skill     ││      │      │      │      │
       │  Registry  ││      │      │      │      │
       └─────┬──────┘│      │      │      │      │
             v       │      │      │      │      │
       ┌────────────┐│      │      │      │      │
       │  Skill     ││      │      │      │      │
       │  Loader    ││      │      │      │      │
       └────────────┘│      │      │      │      │
                     v      │      │      │      │
              ┌────────────┐│      │      │      │
              │ Cron Engine││      │      │      │
              │(APScheduler││      │      │      │
              │ + services)││      │      │      │
              └─────┬──────┘│      │      │      │
                    v       │      │      │      │
              ┌────────────┐│      │      │      │
              │ Cron Runner││      │      │      │
              │ (job exec) ││      │      │      │
              └────────────┘│      │      │      │
                            v      v      v      v
              ┌──────────────────────────────────────┐
              │       Messaging | Browser | SSH      │
              │       Workflows | Memory | Watchers  │
              └──────────────────────────────────────┘
                              │
                              v
                     ┌──────────────┐
                     │   Settings   │
                     │  (.env +     │
                     │   config.py) │
                     └──────────────┘
```

## Component Interactions

1. **CLI layer** (`cli.py`) registers Click command groups. Each subsystem (`vault`, `skill`, etc.) has its own CLI module.
2. **Vault** encrypts/decrypts a JSON blob using the `age` CLI. On macOS, the identity file location can be cached in Keychain as a convenience.
3. **Skill Registry** discovers skills by scanning `skills/*/skill.yaml`, validates manifests, and syncs slash commands as symlinks into `~/.claude/commands/`.
4. **Skill Loader** checks runtime dependencies (binaries on PATH), builds the execution command, and runs scripts in either full or sandboxed environments.
5. **Skill Creator** scaffolds new skill directories from templates (bash or python), generates `skill.yaml`, `run.sh`/`run.py`, and `command.md`.
6. **Cron Engine** (`cron_engine.py`) initializes APScheduler with a SQLite job store, parses schedule expressions (cron, interval, daily-at), and dispatches jobs to the runner. Schedule and job metadata are persisted in `jobs.json`.
7. **Cron Runner** (`cron_runner.py`) executes jobs by type: subprocess for shell, `claude -p` for claude, HTTP POST for webhooks, and skill loader invocation for skills. Captures stdout/stderr/exit code to per-job log files.
8. **Daemon service manager** (`launchd.py`) installs/uninstalls/query daemon status through `systemd --user` on Linux and `launchd` on macOS.
9. **Settings** loads configuration from `.env` and environment variables into a typed dataclass.

## Tech Stack

| Component        | Technology                        |
|------------------|-----------------------------------|
| Language         | Python 3.12+ (3.12 or 3.13 recommended) |
| CLI Framework    | Click 8.x                         |
| Terminal Output  | Rich 13.x                         |
| Encryption       | age (CLI) via subprocess           |
| Skill Manifests  | YAML (PyYAML 6.x)                 |
| Scheduling       | APScheduler 3.x                   |
| HTTP/API         | aiohttp 3.x, FastAPI, uvicorn     |
| Browser          | Playwright (Chromium)              |
| SSH              | Paramiko 3.x                      |
| Persistence      | SQLite (memory, cron), Redis 5.x (sessions, pubsub) |
| MCP              | mcp (FastMCP) for Claude Code integration |
| Testing          | pytest 8.x, ruff (linting)        |
| Build            | setuptools 69+                    |

## Phase Roadmap

| Phase | Name                          | Status         |
|-------|-------------------------------|----------------|
| 1     | Core scaffold, vault, skills  | **Complete**   |
| 2     | Cron daemon (APScheduler)     | **Complete**   |
| 3     | Messaging gateway             | **Complete**   |
| 4     | SSH fabric (Paramiko)         | **Complete**   |
| 5     | Browser engine (Playwright)   | **Complete**   |
| 6     | Workflow orchestrator          | **Complete**   |
| 7     | Persistent memory             | **Complete**   |
| 8     | Watchers, dashboard, glue     | **Complete**   |

All 8 phases are shipped. See the individual doc pages for details on each subsystem.
