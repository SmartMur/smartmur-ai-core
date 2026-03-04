# Phase 4: Messaging Upgrade

**Date**: 2026-03-03
**Author**: SmartMur Brand Strategy
**Scope**: Complete README and messaging overhaul for the Nexus ecosystem
**Depends on**: Phase 1 (Identity), Phase 2 (Architecture), Phase 5 (Star Strategy), Phase 6 (Competitive)

---

## Table of Contents

1. [Organization README](#1-organization-readme)
2. [Nexus Core README Template](#2-nexus-core-readme-template)
3. [Standardized Module/Extension README Template](#3-standardized-moduleextension-readme-template)
4. [Contributor Guide Outline](#4-contributor-guide-outline)
5. [Why This Exists](#5-why-this-exists)
6. [Before/After Examples](#6-beforeafter-examples)

---

## 1. Organization README

> This is the content for `SmartMur/.github/profile/README.md` -- the org-level profile README that appears at `github.com/smartmur`.

```markdown
<p align="center">
  <img src="https://raw.githubusercontent.com/SmartMur/.github/main/assets/nexus-banner.svg" alt="Nexus -- Sovereign AI Operations Platform" width="100%" />
</p>

<h1 align="center">Nexus</h1>

<p align="center">
  <strong>Sovereign AI Operations Platform</strong><br/>
  Your infrastructure, your AI, your rules.
</p>

<p align="center">
  <a href="https://github.com/SmartMur/claude-superpowers"><img src="https://img.shields.io/badge/Nexus_Core-Production-22c55e?style=flat-square" alt="Core Status" /></a>
  <a href="https://github.com/SmartMur/claude-superpowers"><img src="https://img.shields.io/badge/tests-982_passing-brightgreen?style=flat-square" alt="Tests" /></a>
  <a href="https://github.com/SmartMur/claude-superpowers"><img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square" alt="Python" /></a>
  <a href="https://github.com/SmartMur/claude-superpowers/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License" /></a>
</p>

---

### What is Nexus?

Nexus is a self-hosted AI operations platform that turns your infrastructure into an autonomous, intelligent system -- without surrendering control to any cloud provider.

It combines an AI agent runtime, a full DevOps toolkit, and multi-channel messaging into a single platform that runs entirely on your own hardware. What would happen if Backstage, n8n, and Claude Code had a self-hosted child that refused to phone home.

---

### The Ecosystem

```text
                         +-----------------------+
                         |     NEXUS CORE        |
                         | claude-superpowers    |
                         |                       |
                         | AI Runtime / Skills   |
                         | Cron / Workflows      |
                         | Messaging Gateway     |
                         | SSH Fabric / Browser  |
                         | Vault / Memory / MCP  |
                         | Dashboard (70 APIs)   |
                         | 982 tests             |
                         +-----------+-----------+
                                     |
                    manages / orchestrates / monitors
                                     |
            +------------+-----------+-----------+------------+
            |            |                       |            |
   +--------+---+ +-----+------+  +-------------+--+ +------+--------+
   |NEXUS       | |NEXUS       |  |NEXUS            | |NEXUS          |
   |CLUSTER     | |INFRA       |  |MEDIA            | |BOOTSTRAP      |
   |k3s-cluster | |homelab     |  |home_media       | |dotfiles       |
   |            | |            |  |                  | |               |
   |K3s+Ansible | |90+ Docker  |  |Plex/Jellyfin    | |Shell/Git/SSH  |
   |+Terraform  | |stacks      |  |*arr suite       | |Security tools |
   +------------+ +------------+  +------------------+ +---------------+
```

| Tier | Repo | Role |
|------|------|------|
| **Core** | [`claude-superpowers`](https://github.com/SmartMur/claude-superpowers) | AI operations runtime: skills, scheduling, messaging, SSH, browser automation, workflows, memory, vault, dashboard |
| **Module** | [`k3s-cluster`](https://github.com/SmartMur/k3s-cluster) | Kubernetes reference architecture: Ansible + Terraform + GitOps on Proxmox |
| **Module** | [`homelab`](https://github.com/SmartMur/homelab) | 90+ self-hosted service blueprints with security hardening |
| **Module** | [`home_media`](https://github.com/SmartMur/home_media) | Media automation stack: acquisition, transcoding, streaming |
| **Module** | [`dotfiles`](https://github.com/SmartMur/dotfiles) | Developer environment bootstrap: shell, Git, SSH, security tooling |
| **Extension** | [`claude-code-tresor`](https://github.com/SmartMur/claude-code-tresor) | Agent orchestration with secure credential handling |
| **Extension** | [`claude-code-skill-factory`](https://github.com/SmartMur/claude-code-skill-factory) | Skill creation framework for Claude Code agents |
| **Extension** | [`agent-os`](https://github.com/SmartMur/agent-os) | Agent operating system: runtime, memory, tool access |

---

### Why Nexus?

**The problem**: Running AI-powered operations on your own hardware today requires stitching together a dozen disconnected tools -- a cron scheduler here, an SSH wrapper there, a messaging bot somewhere else, secrets in `.env` files, no unified memory, no coordination layer.

**The solution**: Nexus integrates eight subsystems into one tested, cohesive platform:

| Subsystem | What it does |
|-----------|-------------|
| **Skill System** | Registry, loader, auto-install, SkillHub sync. 11 built-in skills. |
| **Cron Engine** | APScheduler + SQLite. Four job types: shell, claude, webhook, skill. |
| **Messaging** | Telegram, Slack, Discord, email, iMessage. Notification profiles. |
| **SSH Fabric** | Paramiko connection pool. Multi-host execution. Home Assistant bridge. |
| **Browser Automation** | Playwright. Session persistence. DOM extraction toolkit. |
| **Workflow Engine** | YAML pipelines. Shell/claude/skill/http/approval-gate steps. |
| **Memory Store** | SQLite. Auto-context injection. 90-day decay. |
| **Encrypted Vault** | age encryption. Rotation policies. Audit logging. |

No single competing project covers all eight. That compound integration is the point.

---

### Getting Started

```bash
git clone https://github.com/SmartMur/claude-superpowers.git
cd claude-superpowers
pip install -e ".[dev]"
claw status
```

Full quickstart: [`claude-superpowers/README.md`](https://github.com/SmartMur/claude-superpowers#quickstart)

---

### Philosophy

We believe infrastructure operators deserve AI tools that run on their hardware, respect their data, and answer to them alone. No telemetry. No cloud lock-in. No "upgrade to Enterprise for SSH access."

Every repo in this organization follows three principles:

1. **Local-first**: Zero external service dependencies for core functionality.
2. **Security-default**: Encrypted vault, pre-commit hooks, secret scrubbing, sandboxed execution.
3. **Reference architecture**: Not personal configs -- generalizable blueprints you can adopt.

Read the full manifesto: [Why This Exists](#)

---

<p align="center">
  <sub>Built by operators, for operators. Sovereignty is not a feature -- it is the architecture.</sub>
</p>
```

---

## 2. Nexus Core README Template

> This replaces the current `claude-superpowers/README.md`. The flagship repo README -- the single most important document in the ecosystem.

```markdown
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
| **Dashboard** | FastAPI + HTMX. 70 REST endpoints across 17 routers. JWT authentication. Covers every subsystem. |
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

<!-- Replace with a graphical Mermaid diagram for production -->

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
| `deploy` | Python | Deployment pipeline: git pull, pip, docker build, health check |
| `github-admin` | Python | Repository audit, branch protection, security scanning |
| `tunnel-setup` | Python | Cloudflare tunnel token management |
| `qa-guardian` | Python | Code quality scanner: 12 checks, 4 categories |
| `infra-fixer` | Python | Docker infrastructure auto-remediation (40+ containers) |
| `cloudflared-fixer` | Python | Tunnel crash-loop detection and recovery |

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
```

---

## 3. Standardized Module/Extension README Template

> This template applies to all Module repos (k3s-cluster, homelab, home_media, dotfiles) and Extension repos (claude-code-tresor, claude-code-skill-factory, agent-os). Each repo fills in the placeholders. The structure is consistent across the ecosystem.

```markdown
<!-- TEMPLATE: Copy and fill in all {PLACEHOLDER} values -->

<p align="center">
  <img src="assets/{banner-file}.svg" alt="{NEXUS_NAME}" width="100%" />
</p>

<h1 align="center">{NEXUS_NAME}</h1>

<p align="center">
  <strong>{ONE_LINE_DESCRIPTION}</strong><br/>
  Part of the <a href="https://github.com/SmartMur">Nexus</a> ecosystem.
</p>

<p align="center">
  <!-- Badges: adjust per repo -->
  <a href="..."><img src="https://img.shields.io/badge/{badge1}" alt="{badge1_alt}" /></a>
  <a href="..."><img src="https://img.shields.io/badge/{badge2}" alt="{badge2_alt}" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License" /></a>
  <a href="https://github.com/SmartMur/{repo}"><img src="https://img.shields.io/badge/GitHub-SmartMur%2F{repo}-181717?logo=github" alt="Repo" /></a>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> |
  <a href="#what-it-does">What It Does</a> |
  <a href="#nexus-integration">Nexus Integration</a> |
  <a href="docs/">Docs</a>
</p>

---

## Why?

<!-- 2-3 sentences. What problem does this repo solve? Why would someone adopt it?
     Frame as outcome, not feature list. -->

{OUTCOME_STATEMENT}

---

## Quickstart

```bash
{QUICKSTART_COMMANDS}
```

---

## What It Does

<!-- Feature grid: 4-8 rows, one per capability. Brief. -->

| Capability | Description |
|-----------|-------------|
| {cap_1} | {desc_1} |
| {cap_2} | {desc_2} |
| {cap_3} | {desc_3} |
| {cap_4} | {desc_4} |

---

## Architecture

<!-- ASCII or Mermaid diagram showing repo structure and key relationships. -->

```text
{ARCHITECTURE_DIAGRAM}
```

---

## Repo Structure

```text
{REPO_TREE}
```

---

## Nexus Integration

This repository is **{NEXUS_NAME}** -- the {TIER_DESCRIPTION} of the [Nexus Platform](https://github.com/SmartMur).

<!-- Describe specifically HOW this repo connects to Nexus Core. -->

**How Nexus Core uses this repo:**

- {integration_point_1}
- {integration_point_2}
- {integration_point_3}

**Related repos:**

| Repo | Relationship |
|------|-------------|
| [`claude-superpowers`](https://github.com/SmartMur/claude-superpowers) | Nexus Core -- orchestrates this repo via {mechanism} |
| [`{related_repo}`](https://github.com/SmartMur/{related_repo}) | {relationship_description} |

---

## Security

<!-- Every repo must have a security section. -->

{SECURITY_DETAILS}

See [SECURITY.md](SECURITY.md) for disclosure policy.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT License. See [LICENSE](LICENSE).

---

<p align="center">
  <sub>Part of <a href="https://github.com/SmartMur">Nexus</a> -- Sovereign AI Operations Platform</sub>
</p>
```

### Template Field Guide

| Field | Module repos | Extension repos |
|-------|-------------|----------------|
| `{NEXUS_NAME}` | "Nexus Cluster", "Nexus Infra", "Nexus Media", "Nexus Bootstrap" | "Nexus Vault Agent", "Nexus Skill Factory", "Nexus Agent OS" |
| `{TIER_DESCRIPTION}` | "infrastructure substrate" | "AI ecosystem extension" |
| `{QUICKSTART_COMMANDS}` | Repo-specific install/deploy steps (max 5 commands) | Repo-specific install steps |
| `{NEXUS_INTEGRATION}` | Describe how Nexus Core's SSH fabric, infra-fixer, or deploy workflow manages this repo | Describe how this extends Nexus Core's skill system, vault, or agent dispatch |

### Mandatory Sections (Every Repo)

1. Hero banner with Nexus branding
2. Badges row (minimum: platform, license, repo link)
3. One-line description with "Part of the Nexus ecosystem" link
4. Why? section (outcome-driven, not feature-list)
5. Quickstart (max 5 commands)
6. What It Does (table format)
7. Architecture (diagram)
8. Nexus Integration (cross-links)
9. Security section
10. Contributing link
11. License
12. Footer with Nexus branding

### Sections NOT Allowed

- "Credits" (generic, adds no value)
- "Support" without actionable links
- "TODO" lists (use GitHub Issues)
- Personal notes or "my setup" language
- Unresolved `CHANGE_ME` placeholders

---

## 4. Contributor Guide Outline

> Structure for `CONTRIBUTING.md`. Each repo gets its own copy with repo-specific details, but the structure is consistent across the ecosystem.

```markdown
# Contributing to {NEXUS_NAME}

Thank you for your interest in contributing to the Nexus ecosystem.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How to Contribute](#how-to-contribute)
3. [Development Setup](#development-setup)
4. [Coding Standards](#coding-standards)
5. [Commit Convention](#commit-convention)
6. [Pull Request Process](#pull-request-process)
7. [Issue Guidelines](#issue-guidelines)
8. [Security](#security)

---

## Code of Conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
Be respectful, constructive, and professional.

---

## How to Contribute

### Good First Issues

Look for issues labeled `good first issue` or `help wanted`.

### Types of Contributions

- **Bug fixes**: Found a bug? Open an issue first, then submit a PR.
- **New features**: Discuss in an issue before writing code. We value design alignment.
- **Documentation**: Typos, clarifications, new guides -- always welcome.
- **Skills** (Nexus Core only): New skills that follow the skill manifest format.
- **Tests**: More coverage is always appreciated. We maintain 982+ tests.
- **Security**: See [Security](#security) below for responsible disclosure.

---

## Development Setup

### Prerequisites

{REPO_SPECIFIC_PREREQUISITES}

### Local Setup

```bash
{REPO_SPECIFIC_SETUP_COMMANDS}
```

### Running Tests

```bash
{REPO_SPECIFIC_TEST_COMMANDS}
```

---

## Coding Standards

### Python (Nexus Core and Python-based repos)

- **Formatter/Linter**: ruff (configured in `pyproject.toml`)
- **Type hints**: Required for all public functions
- **Docstrings**: Required for all public classes and functions
- **Imports**: Sorted by ruff. No unused imports.
- **Max line length**: 120 characters

### Shell Scripts

- **Linting**: shellcheck (all scripts must pass)
- **Shebang**: `#!/usr/bin/env bash`
- **Error handling**: `set -euo pipefail` at the top
- **Quoting**: All variable expansions must be quoted

### YAML

- **Indentation**: 2 spaces
- **No trailing whitespace**
- **Comments**: Explain non-obvious values

### General

- No hardcoded secrets, IPs, paths, or machine-specific values
- All sensitive values in `.env` or vault
- `.env.example` files for every `.env`

---

## Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`, `perf`

**Scope**: The subsystem affected (e.g., `vault`, `cron`, `ssh`, `messaging`, `dashboard`)

**Examples**:

```
feat(ssh): add connection timeout configuration
fix(cron): prevent duplicate job scheduling on daemon restart
docs(workflows): add approval gate example to reference
test(vault): add rotation policy expiry edge cases
```

---

## Pull Request Process

1. **Branch from `main`**. Name your branch: `{type}/{short-description}` (e.g., `feat/ssh-timeout`, `fix/cron-duplicate`).
2. **Write tests** for any new functionality. PRs that decrease test coverage will be discussed.
3. **Run the full test suite** locally before pushing.
4. **Update documentation** if your change affects user-facing behavior.
5. **Fill out the PR template**. Describe what changed, why, and how to test it.
6. **One approval required** for merge. Maintainers may request changes.
7. **Squash merge** is the default merge strategy.

### PR Template

```markdown
## What

<!-- Brief description of the change -->

## Why

<!-- What problem does this solve? Link to issue if applicable -->

## How to Test

<!-- Steps to verify the change works -->

## Checklist

- [ ] Tests pass locally
- [ ] Linter passes (`ruff check .`)
- [ ] Documentation updated (if applicable)
- [ ] No secrets committed
- [ ] Commit messages follow convention
```

---

## Issue Guidelines

### Bug Reports

Include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version, Docker version)
- Relevant logs or error messages

### Feature Requests

Include:
- The problem you are trying to solve (not just the solution you want)
- How you currently work around it
- Why this belongs in the core platform vs. a skill/plugin

---

## Security

**Do not open public issues for security vulnerabilities.**

Report security issues via the process described in [SECURITY.md](SECURITY.md).

We will acknowledge receipt within 48 hours and provide an estimated fix timeline within 7 days.

---

## Questions?

Open a [Discussion](https://github.com/SmartMur/{repo}/discussions) for questions that are not bugs or feature requests.
```

---

## 5. Why This Exists

> Manifesto content for the organization README and the Nexus Core README. Use as a standalone page or inline section.

### The Problem

Every year, AI tools get more powerful and more centralized. Cloud platforms offer "AI-powered infrastructure management" -- but the AI runs on their servers, trains on your data, and requires a subscription that grows with your usage.

For individuals and small teams who run their own hardware -- homelabbers, indie hackers, solo DevOps engineers, security researchers -- this tradeoff is unacceptable. You chose self-hosting because you value control, privacy, and independence. Your AI tools should reflect those same values.

But today, if you want AI-powered operations on your own infrastructure, you face a fragmented landscape:

- **Agent frameworks** (LangChain, CrewAI, AutoGen) give you building blocks but no runtime. You still need to build the scheduler, the messaging layer, the SSH pool, the credential store, the dashboard. That is months of glue code before you automate a single task.

- **AI assistants** (OpenClaw, Claude Code) are powerful in conversations but lack persistent autonomy. They respond when you ask. They do not wake up at 7am, check your VMs, screenshot your dashboards, and send you a Telegram digest.

- **Self-hosted platforms** (Coolify, Portainer, n8n) manage containers or workflows but have no AI awareness. They cannot reason about why a service is failing or dynamically generate a remediation script.

- **DevOps tools** (Ansible, Terraform, Backstage) are enterprise-grade but enterprise-complex, cloud-native by default, and AI-agnostic.

No single project sits at the intersection of all four. That intersection is what we call **Sovereign AI Infrastructure**: AI that runs on your hardware, manages your systems, and answers to you alone.

### The Solution

Nexus fills that gap. It is a complete, self-hosted AI operations platform that combines:

1. **An AI agent runtime** -- skills, memory, multi-model routing, intake pipeline, role-based dispatch
2. **A full DevOps toolkit** -- SSH fabric, browser automation, cron scheduling, workflow engine, file watchers, encrypted vault
3. **Multi-channel messaging** -- Telegram, Slack, Discord, email, iMessage with notification profiles and inbound triggers
4. **A control plane** -- Dashboard, CLI, MCP server, Telegram bot

All integrated. All tested (982 tests). All running on your own hardware. Zero cloud dependencies for core functionality.

### The Principles

**Local-first**: Every feature works without an internet connection. External services (Telegram, Slack) are optional integrations, never dependencies. If Anthropic's API goes down, your cron jobs still run, your SSH fabric still connects, your watchers still trigger.

**Security-default**: Credentials live in an age-encrypted vault with rotation policies, not in `.env` files. Skills run in sandboxed subprocesses with stripped environments. Vault access is gated per-skill via YAML manifests. Every action is audit-logged in append-only JSONL. Pre-commit hooks scrub secrets before they reach Git.

**Reference architecture**: This is not "my homelab scripts." Every component is designed to be adopted by anyone running similar infrastructure. IPs, passwords, and paths live in configuration, never in code. Documentation covers the why, not just the how.

**Compound integration over individual features**: Any one subsystem (cron, SSH, messaging) is trivial to build. The value is in their integration. A morning workflow that SSHes into servers, reasons about the output with Claude, screenshots a dashboard, stores the incident in memory, sends an alert via Telegram, waits for human approval, then executes a fix -- that compound pipeline is something no individual tool provides.

### The Audience

Nexus is for people who:

- Run their own servers (physical or virtual) and want AI to help manage them
- Use Claude Code and want persistent, autonomous capabilities beyond conversation
- Prefer YAML and terminals over drag-and-drop GUIs
- Value sovereignty over convenience
- Are willing to invest setup time for long-term operational power

Nexus is not for people who:

- Want a visual workflow builder (use n8n)
- Want a personal AI chatbot on WhatsApp (use OpenClaw)
- Want a no-code AI app builder (use Dify)
- Need 400+ cloud service integrations (use n8n or Zapier)

We would rather be the best tool for 10,000 serious operators than an adequate tool for 100,000 casual users.

---

## 6. Before/After Examples

### Example 1: claude-superpowers (Nexus Core)

#### BEFORE

```markdown
# Claude Superpowers

A local-first automation platform that gives Claude Code autonomous capabilities:
encrypted credential management, pluggable skills, scheduled jobs, multi-channel
messaging, browser automation, SSH fabric, workflow orchestration, persistent
memory, and file watchers. All running on your own hardware.

**CLI**: `claw` | **Python 3.12+** | **982 tests** | **14 skills** | **4 workflows** | **43 MCP tools** | **70 REST endpoints**

---

## Architecture

[ASCII diagram]

## Quickstart

[8-step install process]

## How It Works

### Skills
### Cron / Scheduler
### Messaging
[...10 more sections, each a paragraph + code block...]

## License

Private project. All rights reserved.
```

**Problems**:
- Name contains a trademark ("Claude") and sounds like a wrapper, not a platform
- No hero image, no badges, no visual hook
- Feature list opening instead of value proposition
- 8-step quickstart (should be 3-5)
- "Private project. All rights reserved." -- kills adoption, forking, and starring
- No comparison table -- visitor cannot evaluate vs. alternatives
- No "why" section -- tells what it does but not why anyone should care
- Flat structure -- every subsystem gets equal weight, creating information overload
- No ecosystem context -- this repo appears isolated

#### AFTER

```markdown
[Hero banner with Nexus branding]

# Nexus Core

Self-hosted AI operations platform.
Skills. Scheduling. Messaging. SSH. Browser automation. Workflows. Memory. Vault.
Your infrastructure, your AI, your rules.

[CI badge] [Tests: 982] [Python 3.12+] [License: MIT] [Docker] [MCP: 43 tools]

## Why?
You run your own hardware. You use Claude Code. You want your AI to do more
than write code -- you want it to operate your infrastructure.

## Quickstart
[4 commands: clone, install, configure, run]

## The Compound Workflow
[Single YAML example showing all 8 subsystems chained together]

## Comparison
[Table: Nexus vs. OpenClaw vs. n8n vs. Agent Frameworks]

## Part of the Nexus Platform
[Cross-links to all ecosystem repos]

## License
MIT License.
```

**Improvements**:
- Platform name (Nexus Core) replaces trademark-containing name
- Hero banner + badges in first viewport
- Value proposition leads ("You run your own hardware. You want your AI to operate your infrastructure.")
- 4-step quickstart replaces 8-step
- MIT license replaces "All rights reserved"
- Compound workflow example demonstrates the unique differentiator
- Comparison table lets visitors evaluate instantly
- Ecosystem section creates cross-linking network effects

---

### Example 2: k3s-cluster (Nexus Cluster)

#### BEFORE

```markdown
# k3s Cluster -- Proxmox + TrueNAS

[5 badges]

Production-oriented automation for provisioning and operating a multi-node k3s
cluster across Proxmox hosts, with TrueNAS-backed persistent storage and Traefik ingress.

[8 doc links in plain text]

## Overview
- Terraform VM provisioning across multiple Proxmox hosts
- Ansible-based cluster bootstrap and app deployment
[...]

## Quick Start
# 1) Install tooling
# 2) Prepare Proxmox template (one-time)
# 3) Configure Terraform vars locally
# 4) Provision VMs
# 5) Bootstrap k3s
# 6) Configure storage
# 7) Create runtime secrets locally
# 8) Deploy apps
```

**Problems**:
- Title is descriptive but disconnected from the ecosystem
- No value proposition -- jumps straight to feature bullets
- Doc links in plain text (not a table, not scannable)
- 8-step quickstart with `CHANGE_ME` placeholders
- No ecosystem context -- this repo looks standalone
- No "why" -- why would someone adopt this over kubeadm or k3sup?

#### AFTER

```markdown
[Hero banner with Nexus Cluster branding]

# Nexus Cluster

Opinionated K3s reference architecture: Ansible provisioning, Terraform state,
GitOps-ready deployment on Proxmox with TrueNAS-backed storage.
Part of the Nexus ecosystem.

[Platform badge] [IaC badge] [License: MIT] [Repo badge]

## Why?
Provisioning a production-grade K3s cluster on Proxmox requires coordinating
Terraform for VMs, Ansible for bootstrap, MetalLB for load balancing, and
NFS for persistent storage. This repo automates the entire lifecycle --
from empty Proxmox hosts to running workloads -- in a repeatable, auditable pipeline.

## Quickstart
git clone ... && cd k3s-cluster
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit with your Proxmox credentials
bash scripts/01-provision.sh   # Create VMs
bash scripts/02-cluster-setup.sh   # Bootstrap K3s + addons

## Nexus Integration
This is Nexus Cluster -- the Kubernetes substrate of the Nexus Platform.

How Nexus Core uses this repo:
- SSH fabric executes commands on cluster nodes
- Deploy workflow triggers rolling updates via kubectl
- Infra-fixer monitors node health and alerts via Telegram
- Cron-driven health checks verify cluster state on schedule

[Table: Related Nexus repos with links]

## License
MIT License.
```

**Improvements**:
- Nexus Cluster name establishes ecosystem membership
- "Part of the Nexus ecosystem" link in subtitle
- Why section frames the problem (coordinating Terraform + Ansible + MetalLB + NFS) and the outcome (repeatable pipeline)
- Quickstart condensed from 8 steps to 4
- Nexus Integration section with specific cross-links
- Consistent footer branding

---

### Example 3: homelab (Nexus Infra)

#### BEFORE

```markdown
[Hero SVG]

# Homelab Infrastructure Repository

[5 badges]

A comprehensive, security-focused collection of 90+ self-hosted services for your homelab.

[Quick Links section]
[One-Click Deployment Scripts]
[Community Showcases]
[Hardware Requirements table]
[Prerequisites checklist]
[Security First section]
[Quick Start: 4 steps]
["I Want To..." Use Case Guide -- 8 scenarios]
[Repository Structure]
[Security Features]
[Complete Service Catalog -- 90+ services in 15 tables]
[Beginner's Journey -- 30-day roadmap]
[Network Architecture diagram]
[FAQ -- 15+ questions]
[Learning Resources]
[Configuration Examples]
[Documentation links]
[Maintenance section]
[Contributing section]
[Important Notes]
```

**Problems**:
- Massive README (~1000 lines) that tries to be everything: catalog, tutorial, FAQ, troubleshooting guide, and reference manual
- "Homelab Infrastructure Repository" is generic -- could be any of 10,000 homelab repos on GitHub
- No ecosystem context -- completely standalone
- Beginner-focused throughout (30-day journey, FAQ for basics) -- does not signal the platform sophistication
- "Community Showcases" links to example files that likely do not exist yet
- curl|bash deployment pattern flagged as a security concern in the org audit
- No Nexus branding or cross-links

#### AFTER

```markdown
[Hero banner with Nexus Infra branding]

# Nexus Infra

90+ production-grade self-hosted service blueprints. Security-hardened Docker Compose
stacks for monitoring, networking, media, productivity, and infrastructure.
Part of the Nexus ecosystem.

[Services: 90+] [Security: First] [License: MIT] [Repo badge]

## Why?
Self-hosting 90 services means managing 90 Docker Compose files, 90 sets of credentials,
90 network configurations, and 90 potential security holes. This repo provides hardened,
tested blueprints with externalized secrets, pre-commit validation, and consistent
deployment patterns. Not a collection of configs -- a reference architecture.

## Quickstart
git clone https://github.com/SmartMur/homelab.git
cd homelab
./scripts/init-homelab.sh      # Setup wizard: hooks, env files, secrets
cd Traefik && docker compose up -d   # Deploy your first service

## What It Does
| Category | Services | Examples |
|----------|---------|---------|
| Security & Auth | 9 | Traefik, Authelia, Vaultwarden, CrowdSec |
| Networking & DNS | 9 | Pi-hole, WireGuard, Headscale, Cloudflare Tunnel |
| Monitoring | 10 | Uptime Kuma, Grafana, Watchtower, Wazuh |
| Media | 6 | Jellyfin, Immich, Frigate |
| Productivity | 9 | Nextcloud, Paperless-ngx, Trilium, Vikunja |
| Development | 5 | Gitea, Code-Server, IT-Tools |
| Home Automation | 3 | Home Assistant, Mosquitto, Zigbee2MQTT |
| Infrastructure | 4 | Ansible, Terraform, Kubernetes, Docker Swarm |
| + 7 more categories | 35+ | Gaming, backup, AI, communication, search... |

Full catalog: [SERVICE_CATALOG.md](SERVICE_CATALOG.md)

## Security
- All credentials externalized to `.env` (gitignored, templated)
- Pre-commit hooks: secret detection, YAML validation
- `scripts/validate-secrets.sh` -- mandatory pre-push gate
- `scripts/generate-secrets.sh` -- cryptographic secret generation
- No curl|bash remote execution in production paths

## Nexus Integration
This is Nexus Infra -- the service substrate of the Nexus Platform.

How Nexus Core manages this repo:
- Container watchdog monitors all 90+ services for health
- Infra-fixer auto-restarts crashed containers and alerts via Telegram
- Deploy workflow executes `docker compose pull && up -d` across stacks
- Cron-driven health checks verify service availability on schedule
- Dashboard displays real-time container status across all stacks

[Table: Related Nexus repos]

## Guides
| Document | Audience |
|----------|---------|
| [Getting Started](docs/GETTING_STARTED.md) | First-time setup |
| [Quick Deploy](QUICK-DEPLOY.md) | Deploy a stack in 30 minutes |
| [Proxmox Deployment](PROXMOX-DEPLOYMENT.md) | Proxmox-specific guide |
| [Security Rulebook](docs/SECURITY_RULEBOOK.md) | Incident handling |
| [Beginner Journey](BEGINNER-GUIDE.md) | 30-day learning path |

## License
MIT License.
```

**Improvements**:
- Name: "Nexus Infra" positions it as a platform module, not "a person's homelab configs"
- Condensed from ~1000 lines to ~100 lines in the README, with deep content moved to linked docs
- Service catalog summarized as a category table (scannable) with link to full catalog
- "Why" section reframes from "collection of services" to "reference architecture with security hardening"
- Nexus Integration section establishes how Nexus Core's container watchdog, infra-fixer, and deploy workflow directly manage these stacks
- Security section updated: removed curl|bash pattern, emphasizes pre-commit and validation
- Consistent ecosystem branding and cross-links

---

## Implementation Checklist

| # | Action | Priority | Effort | Repo |
|---|--------|----------|--------|------|
| 1 | Create `SmartMur/.github/profile/README.md` with org README content from Section 1 | P0 | 1 hr | `.github` |
| 2 | Rewrite `claude-superpowers/README.md` using Nexus Core template from Section 2 | P0 | 2 hr | claude-superpowers |
| 3 | Create `CONTRIBUTING.md` for claude-superpowers using Section 4 structure | P0 | 1 hr | claude-superpowers |
| 4 | Choose and add LICENSE file (MIT recommended) | P0 | 5 min | claude-superpowers |
| 5 | Create visual assets: banner SVG, badges, social preview | P0 | 3 hr | All repos |
| 6 | Rewrite k3s-cluster README using module template from Section 3 | P1 | 1 hr | k3s-cluster |
| 7 | Rewrite homelab README: condense to ~100 lines, move catalog to separate file | P1 | 2 hr | homelab |
| 8 | Rewrite home_media README using module template | P1 | 1 hr | home_media |
| 9 | Rewrite dotfiles README using module template | P1 | 45 min | dotfiles |
| 10 | Add Nexus Integration section to extension repos (tresor, skill-factory, agent-os) | P2 | 2 hr | Extensions |
| 11 | Add "Part of the Nexus Platform" footer to all 10 repos | P2 | 1 hr | All repos |
| 12 | Record terminal GIF for Nexus Core README hero section | P2 | 2 hr | claude-superpowers |
| 13 | Take dashboard screenshot for README | P2 | 30 min | claude-superpowers |
| 14 | Create Mermaid architecture diagram to replace ASCII art | P2 | 1 hr | claude-superpowers |

**Total estimated effort**: ~17 hours across all repos.

**Priority order**: LICENSE + Nexus Core README + Org README first. Module READMEs second. Extensions and visual polish third.

---

*This document provides the complete messaging upgrade for the Nexus ecosystem. Every section is production-ready copy that can be committed directly to the appropriate repository.*
