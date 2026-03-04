<p align="center">
  <img src="assets/nexus-core-banner.svg" alt="Nexus Core" width="100%" />
</p>

<h1 align="center">Nexus Core</h1>

<p align="center">
  <strong>Self-hosted AI operations platform.</strong><br/>
  Skills. Scheduling. Messaging. SSH. Browser automation. Workflows. Memory. Vault.<br/>
  Your infrastructure, your AI, your rules.
</p>

<p align="center">
  <a href="https://github.com/SmartMur/claude-superpowers/actions/workflows/ci.yml"><img src="https://github.com/SmartMur/claude-superpowers/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/tests-982_passing-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/python-3.12+-blue" alt="Python" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License" /></a>
  <img src="https://img.shields.io/badge/docker-compose-blue" alt="Docker" />
  <img src="https://img.shields.io/badge/MCP_tools-43-purple" alt="MCP Tools" />
  <img src="https://img.shields.io/badge/REST_endpoints-70-orange" alt="REST API" />
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> |
  <a href="#what-it-does">What It Does</a> |
  <a href="#the-compound-workflow">The Compound Workflow</a> |
  <a href="#comparison">Comparison</a> |
  <a href="docs/guides/getting-started.md">Full Docs</a>
</p>

---

<!-- Hero screenshot or terminal GIF goes here -->
<!-- <p align="center"><img src="assets/demo.gif" alt="Nexus Core demo" width="80%" /></p> -->

## Why?

You run your own hardware. You use Claude Code. You want your AI to do more than write code -- you want it to **operate your infrastructure**: schedule jobs, SSH into servers, screenshot dashboards, send alerts, remember context, execute multi-step workflows.

Nexus Core makes that real. One platform. Eight integrated subsystems. 982 tests. Zero cloud dependencies.

---

## Quickstart

```bash
# Clone and install
git clone https://github.com/SmartMur/claude-superpowers.git
cd claude-superpowers
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env   # Edit with your tokens

# Run
claw status            # Verify installation
claw skill list        # See available skills
claw skill run heartbeat  # Run your first skill
```

**With Docker** (recommended for full stack):

```bash
docker compose up -d   # Starts: Redis, message gateway, dashboard, browser engine, Telegram bot
```

Dashboard at `http://localhost:8200`. Browser engine at `http://localhost:8300`.

---

## What It Does

### Eight Integrated Subsystems

| Subsystem | Capability | CLI |
|-----------|-----------|-----|
| **Skill System** | 14 built-in skills. Registry, loader, auto-install from templates, SkillHub sync to shared repos. Sandboxed execution with vault access gating. | `claw skill list / run / create / sync` |
| **Cron Engine** | APScheduler + SQLite. Four job types: `shell`, `claude`, `webhook`, `skill`. Cron expressions, intervals, daily-at. Output routing to files or messaging channels. | `claw cron add / list / remove / logs` |
| **Messaging** | Telegram, Slack, Discord, email, iMessage. Notification profiles (`critical`, `info`, `daily-digest`) fan out to multiple channels. Inbound triggers route messages to skills. | `claw msg send / notify` |
| **SSH Fabric** | Paramiko connection pool with lazy creation and liveness checks. Multi-host execution. Host groups. Health checks. Home Assistant REST bridge. | `claw ssh <host> "<command>"` |
| **Browser Automation** | Playwright + headless Chromium. Persistent session profiles (cookies, localStorage). Navigate, screenshot, extract text/tables, fill forms, evaluate JS. | `claw browse open / screenshot / extract` |
| **Workflow Engine** | YAML-defined pipelines. Step types: `shell`, `claude_prompt`, `skill`, `http`, `approval_gate`. Conditions, rollback actions, notifications. | `claw workflow run / list` |
| **Memory Store** | SQLite-backed. Categories: fact, preference, project_context, conversation_summary. Full-text search. 90-day decay with auto-archive. Auto-context injection into Claude prompts. | `claw memory remember / search / context` |
| **Encrypted Vault** | age-encrypted credential store. Atomic writes. Rotation policies with warning/expired thresholds. Audit-logged access. Sandboxed injection into skills. | `claw vault init / set / get / rotation` |

### Plus

| Component | Details |
|-----------|---------|
| **Dashboard** | FastAPI + HTMX. 70 REST endpoints across 17 routers. HTTP Basic authentication. Covers every subsystem. |
| **MCP Server** | 43 native Claude Code tools via Model Context Protocol. Messaging, SSH, browser, workflows, cron, skills, memory, vault, audit -- callable directly from Claude Code. |
| **Intake Pipeline** | Decomposes natural language requests into task graphs. Auto-maps to skills. Role-based dispatch (planner/executor/verifier). Parallel execution. Telegram status notifications. |
| **File Watchers** | watchdog-based directory monitoring. Rules trigger actions: shell, skill, workflow, move, copy. |
| **Audit Log** | Append-only JSONL. Every skill invocation, cron execution, message sent, SSH command run. Searchable via CLI and dashboard. |
| **CI/CD** | GitHub Actions: ruff lint, pytest matrix (3.12 + 3.13), Docker build, deploy via SSH. |

---

## The Compound Workflow

This is what no single competitor can do. A single YAML workflow that chains all eight subsystems:

```yaml
name: morning-infrastructure-check
steps:
  - name: check-vms
    type: shell
    command: "claw ssh proxmox 'qm list'"

  - name: diagnose-issues
    type: claude_prompt
    prompt: "Analyze this VM list. Are any VMs stopped that should be running?"
    input_from: check-vms

  - name: screenshot-dashboard
    type: shell
    command: "claw browse screenshot https://proxmox.local:8006 --output /tmp/pve.png"

  - name: log-to-memory
    type: shell
    command: "claw memory remember 'morning-check' '{{ steps.diagnose-issues.output }}'"

  - name: alert-operator
    type: skill
    skill: heartbeat
    notify: critical

  - name: approve-restart
    type: approval_gate
    channel: telegram
    message: "VMs need restart. Approve?"

  - name: restart-vms
    type: shell
    command: "claw ssh proxmox 'qm start {{ vm_id }}'"
    condition: "steps.approve-restart.approved"
```

**Cron schedules it. SSH executes it. Claude reasons about it. The browser screenshots it. Memory stores it. Messaging delivers it. The approval gate pauses for human judgment. The vault secures every credential involved.**

That is eight subsystems in one pipeline. Try doing that with n8n, OpenClaw, or a collection of shell scripts.

---

## Architecture

```text
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
   |        | | try  | |      | | 5 ch. | | Pool | |Play- | | YAML | |SQLite |
   +--------+ +------+ +------+ +-------+ +------+ +------+ +------+ +-------+
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
                    |                |                |
               Dashboard       Docker Compose    Telegram Bot
             (FastAPI+HTMX)   (5 services)      (polling/webhook)
              port 8200                           AI responses
```

### Docker Compose Stack

| Service | Port | Purpose |
|---------|------|---------|
| `redis` | 6379 | Pub/sub, cache, sessions |
| `msg-gateway` | 8100 | Multi-channel messaging API |
| `dashboard` | 8200 | Web UI + REST API |
| `browser-engine` | 8300 | Playwright automation API |
| `telegram-bot` | -- | Inbound message processing |

### Runtime Data

All state at `~/.claude-superpowers/`:

```text
vault.enc              # age-encrypted credentials
memory.db              # SQLite memory store (WAL mode)
audit.log              # Append-only JSONL audit trail
profiles.yaml          # Notification profile definitions
watchers.yaml          # File watcher rules
cron/jobs.json         # Cron job manifest
cron/scheduler.db      # APScheduler SQLite state
browser/profiles/      # Chromium session data
```

---

## Comparison

### vs. OpenClaw

| Dimension | Nexus Core | OpenClaw |
|-----------|-----------|----------|
| **Focus** | Infrastructure operations | Personal AI assistant |
| **SSH Fabric** | Paramiko pool, multi-host, health checks | Basic system access |
| **Cron Engine** | APScheduler, 4 job types, SQLite store | Basic cron support |
| **Browser Automation** | Playwright, session persistence, DOM extraction | Browser control |
| **Encrypted Vault** | age encryption, rotation policies, audit | OS keychain |
| **Workflow Engine** | YAML pipelines, approval gates, rollback | Skill chains |
| **File Watchers** | watchdog, 5 action types, glob patterns | -- |
| **Messaging Channels** | 5 (Telegram, Slack, Discord, email, iMessage) | 50+ |
| **Test Suite** | 982 tests | Unknown |
| **Positioning** | "Runs your infrastructure" | "Talks to you" |

OpenClaw has broader channel support. Nexus Core has deeper infrastructure control. Different tools for different operators.

### vs. n8n

| Dimension | Nexus Core | n8n |
|-----------|-----------|-----|
| **Interface** | CLI + YAML + Claude Code | Visual drag-and-drop |
| **AI Integration** | Claude-native (skills, prompts, MCP) | AI nodes (bolt-on) |
| **SSH** | Built-in pool with health checks | SSH node (per-execution) |
| **Credential Management** | age-encrypted vault with rotation | Built-in credential store |
| **Workflow Authoring** | YAML (AI generates them) | Visual editor |
| **Integrations** | 5 messaging channels + SSH + browser | 400+ nodes |
| **Target** | Power users who write code | Business users who drag nodes |

n8n is click-first. Nexus Core is code-first. In a Claude Code workflow, the AI writes the YAML -- the visual editor is Claude itself.

### vs. Agent Frameworks (LangChain, CrewAI, AutoGPT)

| Dimension | Nexus Core | Agent Frameworks |
|-----------|-----------|-----------------|
| **Type** | Ready-to-run platform | Libraries for building agents |
| **Time to first result** | `pip install && claw skill run heartbeat` | Write agent code, configure tools, deploy |
| **Infrastructure awareness** | SSH, Docker, Proxmox, Home Assistant | None (cloud-agnostic abstractions) |
| **Production runtime** | Cron, watchers, messaging, dashboard | You build the runtime |

Nexus Core is the platform. Agent frameworks are the building blocks. Different layers.

---

## Built-in Skills

| Skill | Type | Purpose |
|-------|------|---------|
| `heartbeat` | Shell | Ping hosts, probe HTTPS services, formatted status table |
| `network-scan` | Shell | Network discovery and port scanning |
| `ssl-cert-check` | Shell | TLS certificate expiry monitoring |
| `docker-monitor` | Shell | Container health checks across Docker hosts |
| `backup-status` | Shell | Backup job verification |
| `container-watchdog` | Shell | Container restart loop detection and alerting |
| `ops-report` | Shell | Operational status summary across all subsystems |
| `deploy` | Python | Deployment pipeline: git pull, pip, docker build, health check |
| `github-admin` | Python | Repository audit, branch protection, security scanning |
| `tunnel-setup` | Python | Cloudflare tunnel token management |
| `qa-guardian` | Python | Code quality scanner: 12 checks, 4 categories |
| `infra-fixer` | Python | Docker infrastructure auto-remediation (40+ containers) |
| `cloudflared-fixer` | Python | Tunnel crash-loop detection and recovery |
| `workspace-intake-smoke` | Shell | Intake pipeline smoke test |

Create new skills in seconds:

```bash
claw skill create --name my-tool --type python
# Generates: skills/my-tool/skill.yaml + skills/my-tool/run.py + skills/my-tool/command.md
```

---

## Documentation

### Guides

| Document | Description |
|----------|-------------|
| [Getting Started](docs/guides/getting-started.md) | Installation and first-skill walkthrough |
| [Deployment](docs/guides/DEPLOYMENT.md) | Docker Compose, systemd, reverse proxy, TLS |
| [Upgrade](docs/guides/UPGRADE.md) | Version migration, breaking changes, rollback |

### Reference

| Document | Description |
|----------|-------------|
| [Architecture](docs/reference/architecture.md) | Component diagram, data flow, tech stack |
| [Configuration](docs/reference/CONFIGURATION.md) | Every env var, config file, and schema |
| [Security](docs/reference/SECURITY.md) | Auth model, vault, sandboxing, hardening |
| [Skills](docs/reference/skills.md) | Skill system, manifests, loader, sandboxing |
| [Cron](docs/reference/cron.md) | Scheduler, job types, daemon management |
| [Messaging](docs/reference/messaging.md) | Multi-channel messaging, notification profiles |
| [SSH](docs/reference/ssh.md) | SSH fabric, hosts, health checks |
| [Browser](docs/reference/browser.md) | Playwright engine, profiles, DOM toolkit |
| [Workflows](docs/reference/workflows.md) | YAML workflows, step types, rollback |
| [Memory](docs/reference/memory.md) | Persistent memory, categories, decay |
| [Dashboard](docs/reference/dashboard.md) | Web UI, REST API, authentication |
| [MCP Server](docs/reference/mcp-server.md) | 43 MCP tools for Claude Code |

### Operations

| Document | Description |
|----------|-------------|
| [Runbooks](docs/runbooks/RUNBOOKS.md) | Deploy, rollback, incident triage, backup/restore |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| CLI | Click 8.x, Rich 13.x |
| Encryption | age (subprocess) |
| Scheduling | APScheduler 3.x + SQLite |
| HTTP | FastAPI, uvicorn, aiohttp |
| Browser | Playwright (Chromium) |
| SSH | Paramiko 3.x |
| Messaging | slack_sdk, Telegram Bot API, Discord API, smtplib |
| Storage | SQLite (WAL), Redis |
| Frontend | Alpine.js, htmx |
| Testing | pytest 8.x (982 tests) |
| Linting | ruff |
| MCP | FastMCP |
| Containers | Docker Compose |

---

## Project Structure

```text
claude-superpowers/
  superpowers/            # Core Python package
    cli.py                #   Click entry point (claw)
    vault.py              #   age-encrypted vault
    skill_registry.py     #   Skill discovery
    cron_engine.py        #   APScheduler setup
    config.py             #   Settings loader
    audit.py              #   Audit log
    intake.py             #   Request orchestration
    channels/             #   Messaging adapters
    memory/               #   SQLite memory store
    browser/              #   Playwright wrappers
    ssh_fabric/           #   SSH connection pool
    workflow/             #   YAML workflow engine
    watcher/              #   File watcher daemon
    mcp_server.py         #   MCP tool server
  skills/                 # Skill directories
  workflows/              # YAML workflow definitions
  msg_gateway/            # FastAPI messaging service
  dashboard/              # FastAPI web dashboard
  telegram-bot/           # Telegram bot service
  browser_engine/         # Playwright Docker service
  tests/                  # 982 tests
  docs/                   # Documentation
  docker-compose.yaml     # 5-service stack
  pyproject.toml          # Package metadata
```

---

## Part of the Nexus Platform

Nexus Core is the brain of the [Nexus ecosystem](https://github.com/SmartMur). It orchestrates and monitors:

- [**Nexus Cluster**](https://github.com/SmartMur/k3s-cluster) -- K3s on Proxmox via Ansible + Terraform
- [**Nexus Infra**](https://github.com/SmartMur/homelab) -- 90+ self-hosted service blueprints
- [**Nexus Media**](https://github.com/SmartMur/home_media) -- Media automation stack
- [**Nexus Bootstrap**](https://github.com/SmartMur/dotfiles) -- Developer environment provisioning

Extended by:

- [**Nexus Vault Agent**](https://github.com/SmartMur/claude-code-tresor) -- Agent orchestration
- [**Nexus Skill Factory**](https://github.com/SmartMur/claude-code-skill-factory) -- Skill creation framework
- [**Nexus Agent OS**](https://github.com/SmartMur/agent-os) -- Agent runtime environment

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short:

1. Fork the repo
2. Create a feature branch
3. Run tests: `PYTHONPATH=. pytest --ignore=tests/test_telegram_concurrency.py`
4. Submit a pull request

---

## License

MIT License. See [LICENSE](LICENSE).

---

<p align="center">
  <sub>Sovereignty is not a feature. It is the architecture.</sub>
</p>
