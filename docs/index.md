# SmartMur Core

**Self-hosted AI operations platform.**

Skills. Scheduling. Messaging. SSH. Browser automation. Workflows. Memory. Vault.
Your infrastructure, your AI, your rules.

---

## What is SmartMur Core?

SmartMur Core (`claude-superpowers`) gives Claude Code autonomous operational capabilities: encrypted credential management, a pluggable skill system, scheduled jobs, multi-channel messaging, remote SSH execution, browser automation, multi-step workflow orchestration, and persistent memory.

One platform. Eight integrated subsystems. Zero cloud dependencies.

## Quick Install

```bash
git clone https://github.com/SmartMur/claude-superpowers.git
cd claude-superpowers
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
claw status
```

See the [Getting Started](getting-started/index.md) guide for full setup instructions.

---

## Eight Subsystems

| Subsystem | What it does | CLI |
|-----------|-------------|-----|
| **Skill System** | 14 built-in skills. Registry, loader, auto-install, sandboxed execution. | `claw skill list / run / create` |
| **Cron Engine** | APScheduler + SQLite. Shell, Claude, webhook, and skill job types. | `claw cron add / list / logs` |
| **Messaging** | Telegram, Slack, Discord, email. Notification profiles and inbound triggers. | `claw msg send / notify` |
| **SSH Fabric** | Paramiko-based remote execution. Connection pool, host groups, health checks. | `claw ssh run / health / hosts` |
| **Browser Engine** | Playwright-based automation. Navigate, screenshot, extract data, fill forms. | `claw browse open / screenshot` |
| **Workflows** | YAML-defined multi-step pipelines with conditions, quality gates, and rollback. | `claw workflow run / list` |
| **Memory** | SQLite-backed persistent store. Auto-context injection, decay, search. | `claw memory remember / recall` |
| **Vault** | age-encrypted credential storage. Rotation alerts, sandboxed access. | `claw vault set / get / list` |

---

## Additional Capabilities

- **Web Dashboard** -- FastAPI + Alpine.js dashboard at port 8200 (`claw dashboard`)
- **MCP Server** -- 43 tools exposed via Model Context Protocol for Claude Code integration
- **DAG Executor** -- Dependency-aware parallel task execution (`claw dag run`)
- **Agent System** -- Subagent registry with auto-recommendation (`claw agent list / run`)
- **Pack Manager** -- Install and share skill/workflow/agent bundles (`claw pack install`)
- **Policy Engine** -- Safety policies for command execution and file access (`claw policy check`)
- **File Watchers** -- Directory monitors that trigger skills on file changes (`claw watcher start`)
- **Audit Log** -- Append-only log of all skill, cron, SSH, and message operations

---

## Architecture at a Glance

```
                    claw CLI (Click)
  vault | skill | cron | msg | workflow | ssh | browse
    |       |       |      |       |       |       |
    v       v       v      v       v       v       v
  +-------------------------------------------------+
  |            Core Python Package                   |
  |  Vault  Skills  Scheduler  Messaging  SSH  ...  |
  +-------------------------------------------------+
    |                    |                    |
    v                    v                    v
  Settings           SQLite/Redis         Docker Stack
  (.env + config)    (persistence)        (gateway, browser)
```

See the full [Architecture Overview](architecture/index.md) for details.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| CLI | Click 8.x + Rich |
| Encryption | age (CLI) |
| Scheduling | APScheduler 3.x |
| HTTP/API | FastAPI, aiohttp |
| Browser | Playwright (Chromium) |
| SSH | Paramiko 3.x |
| Persistence | SQLite, Redis 5.x |
| MCP | FastMCP |
| Testing | pytest 8.x, ruff |

---

## Links

- [GitHub Repository](https://github.com/SmartMur/claude-superpowers)
- [Getting Started](getting-started/index.md)
- [CLI Reference](reference/cli.md)
- [Architecture](architecture/index.md)
- [Security Policy](reference/SECURITY.md)
