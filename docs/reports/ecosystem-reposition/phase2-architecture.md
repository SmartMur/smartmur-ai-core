# SmartMur Ecosystem — Layered Architecture Model

**Version**: 2.0
**Date**: 2026-03-03
**Status**: Architecture Reference Document

---

## 1. Layered Stack Model

The SmartMur ecosystem is organized into six architectural layers. Each layer has a clear responsibility boundary, communicates only with its immediate neighbors (or via the Event Bus), and can be developed, tested, and deployed independently.

### Layer 0 — Physical & Network Infrastructure

**What it is**: The bare-metal and virtualized compute, storage, and networking substrate that everything else runs on.

**Components**:
- Proxmox VE hypervisors running K3s worker nodes and Docker hosts
- TrueNAS storage providing NFS/SMB shares for persistent data
- UniFi network fabric (switches, APs, firewall rules, VLANs)
- Cloudflare tunnels for secure external ingress without port forwarding

**Repos**: `homelab` (Docker Compose definitions for host-level services), `k3s-cluster` (Ansible/Terraform provisioning, Flux GitOps)

**Key interfaces**:
- SSH (port 22) for remote command execution from Layer 3
- Proxmox API (port 8006) for VM lifecycle management
- Docker socket for container orchestration on Docker hosts
- Kubernetes API (port 6443) for K3s workload management

---

### Layer 1 — Platform Services

**What it is**: The shared services that every higher layer depends on — message bus, persistent storage, observability, identity, and security.

**Components**:
- **Redis** (port 6379) — Pub/sub message bus, ephemeral cache, session store
- **SQLite** — Persistent state for cron jobs (`scheduler.db`), memory store (`memory.db`), audit log
- **Encrypted Vault** — `age`-encrypted credential store (`vault.enc`) with identity file auth
- **Prometheus + Grafana + Loki** — Metrics collection, dashboards, and log aggregation
- **Wazuh + CrowdSec** — Security monitoring, IDS, threat intelligence
- **Keycloak** — Identity provider for SSO across services (future integration)

**Repos**: `homelab` (monitoring stack, security stack), `claude-superpowers` (Redis in Compose, SQLite databases, vault module)

**Key interfaces**:
- Redis protocol (pub/sub channels, key/value ops)
- SQLite WAL-mode connections (file-level, no network)
- Vault API (`superpowers.vault.Vault` — `get`/`set`/`delete`/`list`)
- Prometheus `/metrics` endpoints scraped from all services

---

### Layer 2 — Core Automation Engine

**What it is**: The Python application platform that provides all automation primitives — scheduling, messaging, SSH command execution, browser automation, workflow orchestration, file watching, and persistent memory. This is the brain of the system.

**Components**:

| Module | File | Purpose |
|---|---|---|
| **Cron Engine** | `superpowers/cron_engine.py` | APScheduler + SQLite job store. Four job types: `shell`, `claude`, `webhook`, `skill`. Cron expressions, interval, and daily-at schedules. Output routing to files or messaging channels. |
| **Message Gateway** | `msg_gateway/app.py` | FastAPI service (port 8100) normalizing send/receive across 5 channels: Slack, Telegram, Discord, email (SMTP/IMAP), iMessage. |
| **Channel Registry** | `superpowers/channels/registry.py` | Lazy-loading adapter factory. Auto-detects configured channels from env vars/vault. |
| **Notification Profiles** | `superpowers/profiles.py` | Named groups (`critical`, `info`, `daily-digest`) mapping to channel+target combos. Skills and cron jobs reference profiles, not raw channels. |
| **SSH Fabric** | `superpowers/ssh_fabric/` | Paramiko-based connection pool with lazy creation, max-age expiry, liveness checks. Auth via key, password (from vault), or agent. |
| **Browser Engine** | `browser_engine/app.py` | FastAPI service (port 8300) wrapping Playwright + headless Chromium. Persistent sessions with profile-based cookie/localStorage storage. Navigate, screenshot, extract, fill forms, click, evaluate JS. |
| **Workflow Engine** | `superpowers/workflow/engine.py` | YAML-defined multi-step pipelines. Step types: `shell`, `claude-prompt`, `skill`, `http`, `approval-gate`. Conditions, rollback, and notification on completion. |
| **File Watcher** | `superpowers/watcher/engine.py` | Watchdog-based directory monitor. Rules trigger actions: `shell`, `skill`, `workflow`, `move`, `copy`. |
| **Memory Store** | `superpowers/memory/store.py` | SQLite-backed structured knowledge base. Categories: `fact`, `preference`, `project_context`, `conversation_summary`. Search, decay (90-day auto-archive), access counting. |
| **LLM Provider** | `superpowers/llm_provider.py` | Abstraction layer supporting Claude CLI, Anthropic SDK, OpenAI SDK. Automatic fallback chain. Role-based model routing (`chat` vs `job`). |
| **Audit Log** | `superpowers/audit.py` | Append-only JSONL log of every skill invocation, cron execution, message sent, and SSH command run. |
| **Intake Pipeline** | `superpowers/intake.py` | Request decomposition, requirement extraction, skill auto-mapping, parallel execution with ThreadPoolExecutor, role-based routing (planner/executor/verifier). |
| **Infra Fixer** | `superpowers/infra_fixer.py` | Docker health monitor scanning all projects (40+ containers). Detects crash loops, unhealthy containers, stopped services. Auto-restart capability. |

**Repo**: `claude-superpowers`

---

### Layer 3 — Skill & Plugin System

**What it is**: The extensible skill layer that wraps automation primitives into reusable, discoverable, sandboxed units of work. Skills are the primary unit of composition in the platform.

**Components**:
- **Skill Registry** (`superpowers/skill_registry.py`) — Discovers skills via `skill.yaml` manifests, auto-generates Claude Code slash commands
- **Skill Loader** (`superpowers/skill_loader.py`) — Executes skills in sandboxed subprocesses with controlled env vars, vault access gating
- **Skill Creator** (`superpowers/skill_creator.py`) — Scaffolds new skills from templates (5 built-in: shell, python, claude, http, composite)
- **SkillHub** (`superpowers/skillhub.py`) — Git-based skill sharing: push/pull/list/diff between local and shared repos
- **Auto-Install** (`superpowers/auto_install.py`) — Template-based skill creation from natural language requirements

**Built-in Skills**:

| Skill | Type | Purpose |
|---|---|---|
| `heartbeat` | Shell | Pings 6 hosts, probes 3 HTTPS services, formatted status table |
| `network-scan` | Shell | Network discovery and port scanning |
| `ssl-cert-check` | Shell | TLS certificate expiry monitoring |
| `docker-monitor` | Shell | Container health checks across all Docker hosts |
| `backup-status` | Shell | Backup job verification |
| `deploy` | Python | Local deployment pipeline: git pull, pip install, docker build, health check, test |
| `github-admin` | Python | Repository audit, branch protection, security scanning |
| `tunnel-setup` | Python | Cloudflare tunnel token management |
| `qa-guardian` | Python | Code quality scanner (12 checks, 4 categories) |
| `infra-fixer` | Python | Docker infrastructure auto-remediation |
| `cloudflared-fixer` | Python | Tunnel crash-loop detection and recovery |

**Repo**: `claude-superpowers` (skills at `skills/`), `claude-code-skill-factory` (skill creation patterns)

---

### Layer 4 — Interface & Control Plane

**What it is**: The user-facing surfaces through which humans and external systems interact with the platform — the dashboard, CLI, Telegram bot, and MCP server.

**Components**:
- **Dashboard** (`dashboard/app.py`) — FastAPI + HTMX SPA on port 8200. JWT-authenticated. 17 API router modules covering cron, messaging, SSH, workflows, memory, skills, audit, vault, watchers, browser, chat, notifications, jobs, settings, GitHub, and status. Static file serving for the frontend.
- **CLI (`claw`)** — Click-based CLI entry point. Subcommands: `cron`, `msg`, `skill`, `ssh`, `browse`, `workflow`, `memory`, `vault`, `intake`, `setup`, `status`. Installed as editable package via `pyproject.toml`.
- **Telegram Bot** (`telegram-bot/entrypoint.py`) — Long-polling or webhook-based inbound listener. Claude AI responses, session management (TTL, history limits), concurrency control (per-chat and global limits), admin access requests, verification flow.
- **MCP Server** (`superpowers/mcp_server.py`) — Model Context Protocol server exposing memory tools and workflow tools as MCP resources for Claude Code integration.

**Repo**: `claude-superpowers`

---

### Layer 5 — AI & Agent Orchestration

**What it is**: The intelligence layer that adds autonomous reasoning, multi-agent coordination, and AI-driven decision-making on top of the automation platform.

**Components**:
- **Intake Pipeline** — Decomposes natural language requests into task graphs, auto-maps to skills, dispatches parallel execution with role assignment (planner/executor/verifier)
- **Role Router** (`superpowers/role_router.py`) — Assigns specialized roles to intake tasks based on content analysis
- **LLM Fallback Chain** — Primary provider (Claude) with automatic failover to OpenAI. Role-based model selection (interactive chat vs background jobs)
- **QA Guardian** (`superpowers/qa_guardian.py`) — Autonomous code quality enforcement: 12 checks, 4 categories, JSON reports, Telegram notifications
- **Claude Code Tresor** — Agent orchestration framework for complex multi-step reasoning tasks
- **Agent OS** — Operating system abstractions for persistent agent processes
- **Lighthouse AI** — AI-powered code analysis and review

**Repos**: `claude-superpowers`, `claude-code-tresor`, `agent-os`, `Lighthouse-AI`

---

## 2. Architecture Diagram

```
+===========================================================================+
|                                                                           |
|   LAYER 5 — AI & AGENT ORCHESTRATION                                      |
|                                                                           |
|   +-------------------+  +----------------+  +-------------------------+  |
|   | Intake Pipeline   |  | Role Router    |  | LLM Provider            |  |
|   | - decompose       |  | - planner      |  | - Claude CLI/SDK        |  |
|   | - auto-map skills |  | - executor     |  | - OpenAI fallback       |  |
|   | - parallel exec   |  | - verifier     |  | - role-based routing    |  |
|   +--------+----------+  +-------+--------+  +------------+------------+  |
|            |                      |                        |              |
|   +--------v----------+  +-------v--------+  +------------v------------+  |
|   | QA Guardian       |  | claude-code-   |  | Lighthouse-AI           |  |
|   | - 12 checks       |  |   tresor       |  | - code analysis         |  |
|   | - auto-enforce    |  | - agent orch.  |  | - review automation     |  |
|   +-------------------+  +----------------+  +-------------------------+  |
|                                                                           |
+========+============+==================+=================+================+
         |            |                  |                 |
         | invoke     | dispatch         | prompt          | analyze
         v            v                  v                 v
+===========================================================================+
|                                                                           |
|   LAYER 4 — INTERFACE & CONTROL PLANE                                     |
|                                                                           |
|   +------------------+  +-----+  +-----------------+  +-----------------+ |
|   | Dashboard :8200  |  | CLI |  | Telegram Bot    |  | MCP Server      | |
|   | - FastAPI+HTMX   |  |     |  | - polling/hook  |  | - memory tools  | |
|   | - JWT auth       |  | claw|  | - AI responses  |  | - workflow tools| |
|   | - 17 API routers |  |     |  | - session mgmt  |  | - Claude Code   | |
|   +--------+---------+  +--+--+  +--------+--------+  +--------+--------+ |
|            |               |              |                     |          |
+========+===+===============+==============+=====+===============+==========+
         |                   |              |     |               |
         | REST              | subprocess   |     | pub/sub       | MCP
         v                   v              v     v               v
+===========================================================================+
|                                                                           |
|   LAYER 3 — SKILL & PLUGIN SYSTEM                                        |
|                                                                           |
|   +--------------------+  +-------------------+  +----------------------+ |
|   | Skill Registry     |  | Skill Loader      |  | SkillHub             | |
|   | - YAML discovery   |  | - sandboxed exec  |  | - git push/pull      | |
|   | - slash cmd gen    |  | - env isolation   |  | - shared repo sync   | |
|   +--------------------+  | - vault gating    |  +----------------------+ |
|                           +-------------------+                           |
|   +-------------------------------------------------------------------+  |
|   | Built-in Skills                                                   |  |
|   | heartbeat | network-scan | ssl-cert-check | docker-monitor        |  |
|   | deploy    | github-admin | tunnel-setup   | qa-guardian           |  |
|   | infra-fixer | cloudflared-fixer | backup-status                   |  |
|   +-------------------------------------------------------------------+  |
|                                                                           |
+======+==========+==========+==========+===========+==========+============+
       |          |          |          |           |          |
       | shell    | skill    | http     | claude    | workflow | watcher
       v          v          v          v           v          v
+===========================================================================+
|                                                                           |
|   LAYER 2 — CORE AUTOMATION ENGINE                                       |
|                                                                           |
|   +---------------+  +------------------+  +---------------------------+  |
|   | Cron Engine   |  | Message Gateway  |  | SSH Fabric                |  |
|   | - APScheduler |  | :8100            |  | - paramiko pool           |  |
|   | - SQLite jobs |  | - 5 channels     |  | - key/password/agent auth |  |
|   | - 4 job types |  | - profiles       |  | - connection reuse        |  |
|   +-------+-------+  +--------+---------+  +-------------+-------------+  |
|           |                    |                          |                |
|   +-------v-------+  +--------v---------+  +-------------v-------------+  |
|   | Workflow Eng. |  | Browser Engine   |  | File Watcher              |  |
|   | - YAML steps  |  | :8300            |  | - watchdog                |  |
|   | - conditions  |  | - Playwright     |  | - YAML rules              |  |
|   | - rollback    |  | - session mgmt   |  | - trigger actions         |  |
|   | - approvals   |  | - DOM extraction |  +---------------------------+  |
|   +---------------+  +------------------+                                 |
|                                                                           |
|   +------------------+  +-------------------+  +------------------------+ |
|   | Memory Store     |  | Audit Log         |  | Infra Fixer            | |
|   | - SQLite WAL     |  | - append-only     |  | - 40+ containers      | |
|   | - search/decay   |  | - JSONL           |  | - auto-restart         | |
|   | - categories     |  | - searchable      |  | - health reports       | |
|   +------------------+  +-------------------+  +------------------------+ |
|                                                                           |
+======+=================+=================+================================+
       |                 |                 |
       | redis           | sqlite          | vault
       v                 v                 v
+===========================================================================+
|                                                                           |
|   LAYER 1 — PLATFORM SERVICES                                            |
|                                                                           |
|   +-----------+  +-----------+  +------------+  +------------------------+|
|   | Redis     |  | SQLite    |  | Encrypted  |  | Monitoring             ||
|   | :6379     |  | WAL mode  |  | Vault      |  | Prometheus + Grafana   ||
|   | - pub/sub |  | - cron DB |  | - age enc  |  | Loki (logs)            ||
|   | - cache   |  | - memory  |  | - identity |  | Wazuh + CrowdSec      ||
|   | - session |  | - audit   |  |   file     |  | (IDS, threat intel)    ||
|   +-----------+  +-----------+  +------------+  +------------------------+|
|                                                                           |
+======+=================+=================+================================+
       |                 |                 |
       | docker          | ssh             | API
       v                 v                 v
+===========================================================================+
|                                                                           |
|   LAYER 0 — PHYSICAL & NETWORK INFRASTRUCTURE                            |
|                                                                           |
|   +--------------------+  +------------------+  +----------------------+  |
|   | Proxmox VE         |  | Docker Hosts     |  | TrueNAS              |  |
|   | - K3s nodes        |  | - Compose stacks |  | - NFS/SMB shares     |  |
|   | - VM lifecycle     |  | - 9 projects     |  | - ZFS snapshots      |  |
|   +--------------------+  | - 40+ containers |  +----------------------+  |
|                           +------------------+                            |
|   +--------------------+  +------------------+                            |
|   | UniFi Network      |  | Cloudflare       |                            |
|   | - VLANs            |  | - tunnels        |                            |
|   | - firewall rules   |  | - DNS            |                            |
|   | - APs + switches   |  | - zero-trust     |                            |
|   +--------------------+  +------------------+                            |
|                                                                           |
+===========================================================================+
```

---

## 3. Repo-to-Layer Mapping

| Repository | Layer | Role | Connects To |
|---|---|---|---|
| **claude-superpowers** | L2, L3, L4, L5 | Core platform. Houses the automation engine (L2), skill system (L3), all user interfaces (L4), and AI orchestration (L5). The central nervous system. | L1 via Redis, SQLite, Vault. L0 via SSH Fabric and Docker API. |
| **k3s-cluster** | L0 | Infrastructure-as-code for the Kubernetes substrate. Ansible playbooks for Proxmox VM provisioning, Terraform for K3s bootstrap, Flux for GitOps. | L1 receives metrics via Prometheus. L2 manages via SSH Fabric. |
| **homelab** | L0, L1 | Docker Compose definitions for host-level services spanning infrastructure (L0) and platform services (L1): monitoring stack, security stack, Gitea, Guacamole, Frigate, Keycloak. | L2 monitors via Infra Fixer. L4 displays in Dashboard. |
| **home_media** | L0 | Media automation stack: Plex, Jellyfin, Sonarr, Radarr, Prowlarr, qBittorrent. Runs as Docker Compose on a dedicated host. | L2 monitors via Infra Fixer. L2 File Watcher triggers on new downloads. |
| **claude-code-tresor** | L5 | Agent orchestration framework. Provides multi-agent coordination patterns for complex reasoning tasks. | L4 via MCP. L3 by invoking skills. L2 via LLM Provider. |
| **claude-code-skill-factory** | L3 | Skill creation factory with templates, validation, and publishing workflows. Feeds the SkillHub. | L3 SkillHub for distribution. L5 Intake for auto-installation. |
| **agent-os** | L5 | Agent operating system abstractions: persistent processes, memory, tool access. Provides runtime for long-lived agents. | L2 Memory Store. L1 Redis for state. L3 Skills for actions. |
| **Lighthouse-AI** | L5 | AI-powered code analysis, review automation, and quality scoring. | L5 QA Guardian integration. L4 Dashboard reporting. |
| **dotfiles** | L0 | Developer environment setup: shell configs, tool installation, SSH config, editor settings. Bootstraps new hosts. | L0 provisions the environment that all layers run in. |
| **design-os** | -- | Fork. Design system reference. Not integrated into the automation stack. | -- |
| **Smoke** | -- | Fork. Testing framework reference. Not integrated into the automation stack. | -- |

---

## 4. Data Flow

### 4.1 Command Flow (User-Initiated)

```
User
  |
  +--[CLI: claw cron add ...]---------> Cron Engine ----> SQLite (jobs.json)
  |                                          |
  +--[Dashboard: POST /api/msg/send]--> Msg Gateway ----> Channel Adapter ---> Slack/Telegram/...
  |                                          |
  +--[Telegram: "!scan network"]------> Inbound -------> Intake Pipeline
  |                                      Listener            |
  +--[CLI: claw skill run deploy]-----> Skill Loader ---> Subprocess (sandboxed)
  |                                          |
  +--[MCP: memory.remember]-----------> MCP Server -----> Memory Store ----> SQLite
```

### 4.2 Scheduled Execution Flow (Cron-Initiated)

```
APScheduler timer fires
  |
  v
CronEngine._execute_job(job_id)
  |
  +--[shell]----> subprocess.run() ----> stdout/stderr
  |
  +--[claude]---> LLMProvider.invoke() -> Claude/OpenAI API -> response text
  |
  +--[webhook]--> urllib POST ----------> remote HTTP endpoint -> response
  |
  +--[skill]----> SkillRegistry.get() --> SkillLoader.run() --> subprocess
  |
  v
_route_output()
  |
  +--[file]-----> write to ~/.claude-superpowers/cron/output/{id}/{ts}.log
  |
  +--[channel]--> ChannelRegistry.get() -> adapter.send() -> Slack/Telegram/...
  |
  +--[profile]--> ProfileManager.send() -> fan-out to N channel+target combos
```

### 4.3 Event-Driven Flow (Watcher/Inbound)

```
Filesystem event (watchdog)              Inbound message (Telegram)
  |                                        |
  v                                        v
WatcherEngine._on_event()              InboundListener.on_message()
  |                                        |
  +-- pattern match against rules          +-- pattern match (!command)
  |                                        |
  v                                        v
Action dispatch:                        Intake Pipeline:
  shell  -> subprocess                    extract_requirements()
  skill  -> SkillLoader                   build_plan()
  move   -> shutil.move                   auto_install() for each task
  copy   -> shutil.copy2                  ThreadPoolExecutor.submit()
  workflow -> WorkflowEngine                |
                                            v
                                        SkillLoader.run_sandboxed()
                                            |
                                            v
                                        Response -> Telegram reply
```

### 4.4 Metrics & Observability Flow

```
All Services
  |
  +--[Prometheus /metrics]-----> Prometheus -----> Grafana dashboards
  |
  +--[Structured logs]--------> Loki ------------> Grafana log queries
  |
  +--[Audit log entries]------> audit.log (JSONL)
  |                                |
  |                                +---> Dashboard /api/audit/tail
  |                                +---> CLI: claw audit search
  |
  +--[Health checks]----------> Dashboard /api/status
  |                                |
  |                                +---> Cron daemon status
  |                                +---> Redis connectivity
  |                                +---> Browser engine sessions
  |                                +---> Message gateway channels
  |                                +---> Memory store stats
  |
  +--[Security events]--------> Wazuh -----------> Alerts
  |                             CrowdSec ---------> IP blocklists
  |
  +--[Infra Fixer reports]----> JSON reports -----> Telegram notifications
                                    |
                                    +---> Dashboard /api/status
```

---

## 5. Integration Points

### 5.1 Inter-Layer Communication Matrix

| From | To | Protocol | Mechanism | Example |
|---|---|---|---|---|
| L4 (Dashboard) | L2 (Cron Engine) | In-process | Python import, direct method call | `CronEngine().list_jobs()` |
| L4 (Dashboard) | L2 (Browser Engine) | HTTP REST | `httpx` to `http://browser-engine:8300` | `POST /screenshot` |
| L4 (Telegram Bot) | L2 (Msg Gateway) | In-process | `InboundListener` -> `ChannelRegistry` | Pattern-matched inbound dispatch |
| L4 (CLI) | L2 (All engines) | In-process | Click command -> Python module | `claw cron list` -> `CronEngine.list_jobs()` |
| L4 (MCP Server) | L2 (Memory Store) | In-process | MCP tool handler -> `MemoryStore` | `memory.remember` tool call |
| L3 (Skills) | L2 (SSH Fabric) | In-process | Skill script imports `ssh_fabric` | `ConnectionPool.get_client("proxmox")` |
| L3 (Skills) | L1 (Vault) | In-process | `Vault.get()` (gated by skill.yaml perms) | Retrieve SSH password for host |
| L2 (Cron Engine) | L1 (SQLite) | File I/O | SQLAlchemy job store, JSON job persistence | `scheduler.db`, `jobs.json` |
| L2 (Cron Engine) | L2 (Msg Gateway) | In-process | `_send_to_channel()` -> `ChannelRegistry` | Job output to Slack profile |
| L2 (Workflow) | L2 (All engines) | In-process | Step dispatcher calls engine methods | `shell` -> subprocess, `skill` -> SkillLoader |
| L2 (Msg Gateway) | L1 (Redis) | Redis protocol | Pub/sub for message bus | Inbound message fanout |
| L2 (SSH Fabric) | L0 (Hosts) | SSH | Paramiko TCP connection | `executor.run("proxmox", "qm list")` |
| L2 (Infra Fixer) | L0 (Docker) | Subprocess | `docker ps`, `docker inspect`, `docker restart` | Container health scan |
| L1 (Redis) | -- | TCP 6379 | Docker network (`default`) | All services on same Compose network |

### 5.2 Docker Compose Service Topology

```
                    +------------------+
                    |   npm_default    |    (external network:
                    |   network        |     reverse proxy)
                    +--------+---------+
                             |
+----------------------------+-----------------------------------+
|                    Docker Compose: claude-superpowers           |
|                                                                |
|   +-----------+     +--------------+     +------------------+  |
|   |   redis   |     | msg-gateway  |     |    dashboard     |  |
|   |   :6379   |<----+   :8100      |     |    :8200         |  |
|   |           |     |              |     |                  +--+--> npm_default
|   +-----+-----+     +--------------+     +--------+---------+  |
|         |                                         |             |
|         |           +--------------+              |             |
|         +---------->| browser-eng  |<-------------+             |
|         |           |   :8300      |                            |
|         |           +--------------+                            |
|         |                                                       |
|         |           +--------------+                            |
|         +---------->| telegram-bot |                            |
|                     | (no port)    |                            |
|                     +--------------+                            |
|                                                                |
+----------------------------------------------------------------+
```

### 5.3 Authentication & Security Boundaries

| Boundary | Mechanism | Details |
|---|---|---|
| Dashboard API | JWT (HS256) | `DASHBOARD_USER`/`DASHBOARD_PASS` credentials. Token issued via `/auth/login`, validated on every `/api/*` route. Insecure default detection. |
| Telegram Bot | Chat ID allowlist | `ALLOWED_CHAT_IDS` env var. Unrecognized chats trigger admin approval flow. |
| Telegram Webhook | Secret token header | `X-Telegram-Bot-Api-Secret-Token` validated fail-closed. |
| Vault | age encryption | Identity file (`age-identity.txt`) required for decrypt. No network exposure. |
| SSH Fabric | Key/password/agent | Credentials from vault or SSH agent. Connection pool with max-age expiry. |
| Skill Sandbox | Env stripping | `run_sandboxed()` strips environment, only passes vault access if `skill.yaml` grants `vault: true`. |
| Webhooks | Signature validation | `WEBHOOK_REQUIRE_SIGNATURE=true` (fail-closed default). |
| Rate limiting | Per-IP and per-user | Configurable via `RATE_LIMIT_PER_IP` (60/min) and `RATE_LIMIT_PER_USER` (120/min). |

### 5.4 Persistent Storage Map

```
~/.claude-superpowers/                  (SUPERPOWERS_DATA_DIR)
  |
  +-- vault.enc                         age-encrypted credential store
  +-- age-identity.txt                  vault decryption identity
  +-- memory.db                         SQLite memory store (WAL mode)
  +-- audit.log                         append-only JSONL audit trail
  +-- profiles.yaml                     notification profile definitions
  +-- watchers.yaml                     file watcher rule definitions
  |
  +-- cron/
  |     +-- jobs.json                   cron job definitions (atomic write)
  |     +-- scheduler.db               APScheduler SQLite job store
  |     +-- cron-daemon.pid            daemon PID file
  |     +-- output/{job-id}/{ts}.log   per-execution output logs
  |
  +-- browser/
  |     +-- profiles/{name}/           Chromium user data dirs (cookies, localStorage)
  |
  +-- skills/                          user-installed skills
  +-- workflows/                       user-defined workflow YAML files
  +-- runtime/                         intake pipeline session state
  +-- ssh/                             SSH host registry
  +-- logs/                            application logs
  +-- msg/                             message queue persistence
```

---

## 6. Cross-Cutting Concerns

### 6.1 Configuration Resolution Order

Every service follows the same configuration precedence:

1. **Environment variable** (highest priority)
2. **Encrypted vault** (`vault.enc` via `Vault.get()`)
3. **`.env` file** (loaded once at startup, never overrides existing env vars)
4. **Code defaults** (lowest priority)

This is implemented in `Settings.load()` via the `_secret()` helper function, which tries env var first then vault fallback.

### 6.2 Error Handling Philosophy

- **Messaging failures never break automation**: `_send_to_channel()` catches `ChannelError` silently. A failed Slack notification does not abort a cron job.
- **Vault is optional**: `Settings._vault_get()` returns empty string on any exception. Services degrade gracefully without vault access.
- **SSH connections are lazy**: `ConnectionPool.get_client()` only connects on first use. Dead connections are detected and reconnected transparently.
- **Skill execution is isolated**: `run_sandboxed()` strips the environment. A skill crash does not affect the host process.

### 6.3 Deployment Modes

| Mode | Stack | Use Case |
|---|---|---|
| **Full Docker** | All 5 services via `docker-compose up` | Production on Docker host |
| **CLI-only** | `pip install -e .` + `claw` commands | Developer workstation, quick automation |
| **Hybrid** | CLI locally + Redis/browser-engine in Docker | Development with browser automation |
| **K3s** | Helm charts (future) via `k3s-cluster` Flux | Production Kubernetes deployment |

---

## 7. Evolution Roadmap

The layered model enables targeted investment at each level:

| Layer | Current State | Next Milestone |
|---|---|---|
| L0 Infrastructure | Manual provisioning, Ansible scripts | Full IaC with Terraform state in Git, automated VM lifecycle |
| L1 Platform | Redis + SQLite, monitoring via separate stack | Unified Prometheus federation, Keycloak SSO integration |
| L2 Engine | All 8 engines operational (982 tests) | Event sourcing for audit trail, WebSocket push for real-time updates |
| L3 Skills | 11 built-in skills, SkillHub sync | Skill marketplace, versioned skill dependencies, skill composition |
| L4 Interfaces | Dashboard, CLI, Telegram, MCP | Mobile-responsive dashboard, Discord bot, webhook API for external integrations |
| L5 AI | Intake pipeline, LLM fallback, QA Guardian | Autonomous agent loops, planning with memory, self-healing infrastructure |
