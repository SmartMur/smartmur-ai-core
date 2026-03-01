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
│   └── launchd.py            # macOS launchd plist generation + management
├── skills/                   # Skill directories (each has skill.yaml)
│   ├── _template/            # Copy-paste starter skill
│   └── network-scan/         # Example: scan home network subnets
├── browser_engine/           # (Phase 5) Playwright-based browser automation
├── msg_gateway/              # (Phase 4) Slack/Telegram/Discord/email gateway
├── ssh_fabric/               # (Phase 6) Remote execution over SSH
├── workflows/                # (Phase 7) Multi-step workflow engine
├── tests/                    # Unit and integration tests
├── docs/                     # This documentation
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
│   ├── daemon.log            # Daemon process log
│   └── output/{id}/          # Per-job execution logs
├── vault/                    # (reserved)
└── logs/                     # Execution logs
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
              │ + launchd) ││      │      │      │
              └─────┬──────┘│      │      │      │
                    v       │      │      │      │
              ┌────────────┐│      │      │      │
              │ Cron Runner││      │      │      │
              │ (job exec) ││      │      │      │
              └────────────┘│      │      │      │
                            v      v      v      v
              ┌──────────────────────────────────────┐
              │         Future Phases (3-8)           │
              │   msg | browser | ssh | wkflow       │
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
2. **Vault** encrypts/decrypts a JSON blob using the `age` CLI. The identity file location is stored in macOS Keychain for convenience.
3. **Skill Registry** discovers skills by scanning `skills/*/skill.yaml`, validates manifests, and syncs slash commands as symlinks into `~/.claude/commands/`.
4. **Skill Loader** checks runtime dependencies (binaries on PATH), builds the execution command, and runs scripts in either full or sandboxed environments.
5. **Skill Creator** scaffolds new skill directories from templates (bash or python), generates `skill.yaml`, `run.sh`/`run.py`, and `command.md`.
6. **Cron Engine** (`cron_engine.py`) initializes APScheduler with a SQLite job store, parses schedule expressions (cron, interval, daily-at), and dispatches jobs to the runner. Schedule and job metadata are persisted in `jobs.json`.
7. **Cron Runner** (`cron_runner.py`) executes jobs by type: subprocess for shell, `claude -p` for claude, HTTP POST for webhooks, and skill loader invocation for skills. Captures stdout/stderr/exit code to per-job log files.
8. **Launchd** (`launchd.py`) generates a macOS launchd plist, installs/uninstalls via `launchctl`, and queries daemon status. The plist is written to `~/Library/LaunchAgents/com.claude-superpowers.cron.plist`.
9. **Settings** loads configuration from `.env` and environment variables into a typed dataclass.

## Tech Stack

| Component        | Technology                        |
|------------------|-----------------------------------|
| Language         | Python 3.12+ (targets 3.14)       |
| CLI Framework    | Click 8.x                         |
| Terminal Output  | Rich 13.x                         |
| Encryption       | age (CLI) via subprocess           |
| Skill Manifests  | YAML (PyYAML 6.x)                 |
| Scheduling       | APScheduler 3.x                   |
| HTTP/API         | aiohttp 3.x, FastAPI (Phase 4+)   |
| Browser          | Playwright (Phase 5)              |
| SSH              | Paramiko 3.x (Phase 6)            |
| Persistence      | Redis 5.x (Phase 7+)              |
| Testing          | pytest 8.x, ruff (linting)        |
| Build            | setuptools 69+                    |

## Phase Roadmap

| Phase | Name                          | Status         |
|-------|-------------------------------|----------------|
| 1     | Core scaffold, vault, skills  | **Complete**   |
| 2     | Cron daemon (APScheduler)     | **Complete**   |
| 3     | Messaging gateway             | Planned        |
| 4     | Browser engine (Playwright)   | Planned        |
| 5     | SSH fabric (Paramiko)         | Planned        |
| 6     | Workflow orchestrator          | Planned        |
| 7     | Dashboard + status API         | Planned        |

### Phase 1 Deliverables (Complete)

- Project scaffold with `pyproject.toml`, `claw` entry point
- Encrypted vault with age keypair generation, macOS Keychain integration
- Skill registry with discovery, validation, install/uninstall
- Skill loader with dependency checking and sandboxed execution
- Skill creator with bash/python templates and auto-sync
- CLI commands for all of the above
- Slash command generation via symlinks into `~/.claude/commands/`

### Phase 2 Deliverables (Complete)

- APScheduler-based cron engine with SQLite job store
- Four job types: shell, claude, webhook, skill
- Three schedule formats: cron expressions, interval strings, daily-at patterns
- Job execution runner with stdout/stderr/exit code capture
- Per-job output logging to `~/.claude-superpowers/cron/output/{id}/`
- macOS launchd daemon with install/uninstall/status management
- CLI commands: `claw cron list/add/remove/enable/disable/logs/run/status`
- CLI commands: `claw daemon install/uninstall/status/logs`
- Job persistence via `jobs.json` + SQLite
- Heartbeat skill for homelab infrastructure monitoring
