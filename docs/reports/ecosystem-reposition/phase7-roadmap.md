# Phase 7: 12-Month Roadmap & Long-Term Vision

**Date**: 2026-03-03
**Author**: SmartMur Strategic Planning
**Status**: Roadmap Approved
**Prerequisite**: Phases 1 (Identity), 2 (Architecture), 5 (Star Strategy), 6 (Competitive) complete

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [12-Month Roadmap (Quarterly Breakdown)](#2-12-month-roadmap)
3. [Core Feature Milestones](#3-core-feature-milestones)
4. [Ecosystem Expansion](#4-ecosystem-expansion)
5. [What Makes This 10k-Star Worthy](#5-what-makes-this-10k-star-worthy)
6. [What Makes This Conference-Talk Worthy](#6-what-makes-this-conference-talk-worthy)
7. [What Makes This Enterprise-Relevant](#7-what-makes-this-enterprise-relevant)
8. [Risk Analysis](#8-risk-analysis)
9. [Success Metrics & KPIs](#9-success-metrics--kpis)
10. [Appendix: Dependency Graph](#appendix-dependency-graph)

---

## 1. Executive Summary

Nexus is a self-hosted AI operations platform that combines 8 integrated subsystems (cron, messaging, SSH fabric, browser automation, workflow engine, memory store, file watchers, encrypted vault) into a single platform controlled via CLI, dashboard, Telegram, and MCP. It has 982 tests, a Docker Compose stack, and all core features operational. It has zero public users, zero stars, and zero community.

This roadmap transforms Nexus from a working private project into a recognized open-source platform over 12 months. The plan is organized into four quarters, each with a theme, concrete deliverables, and measurable outcomes.

**The strategic bet**: Nexus will not beat OpenClaw (130k stars) or n8n (177k stars) on breadth. It will beat them on depth -- becoming the definitive platform for AI-powered infrastructure operations. The niche is "people who run their own servers and want AI to help manage them." That niche contains every r/selfhosted subscriber (2M+), every Claude Code power user, and every DevOps engineer tired of writing one-off scripts.

**12-month target**: 5,000-10,000 GitHub stars, 50+ contributors, 3 conference appearances, 1 enterprise pilot.

---

## 2. 12-Month Roadmap

### Q1: Foundation & Launch (Months 1-3)

**Theme**: "Make it real. Make it public. Make first impressions count."

The entire quarter is about removing every reason someone would NOT star the repo (see Phase 5 analysis) and creating the minimum viable launch package.

#### Month 1: Pre-Launch Preparation

| Week | Deliverable | Acceptance Criteria | Owner |
|------|------------|-------------------|-------|
| W1 | **License selection and application** | MIT LICENSE file in repo root. "All rights reserved" removed from README. License badge added. | Admin |
| W1 | **Repo rename to `nexus`** | GitHub repo renamed from `claude-superpowers` to `nexus`. Old name redirects. pyproject.toml `name` updated. CLI remains `claw` (brand asset). | Admin |
| W1 | **GitHub org profile** | SmartMur org README with Nexus branding, pinned repos (6), GitHub Topics on all 10 repos. Org bio: "Nexus -- self-hosted AI operations platform." | Admin |
| W2 | **Visual identity: logo + banner** | Text-based logo (monospace font, accent color). Hero banner (1280x640) with logo + tagline + one dashboard screenshot. Social preview image set on repo. | Design |
| W2 | **README rewrite (killer README)** | New README following Phase 5 proven structure: hero banner, one-line value prop, GIF/screenshot in first viewport, 3-bullet "Why?", 3-step quickstart, feature highlights with images, graphical architecture diagram, comparison table, docs links, contributing link, license. | Dev |
| W2 | **Badges** | CI status, Python 3.12+, tests (982 passing), license (MIT), Docker Compose, MCP tools (43). All green. All linking to relevant resources. | Dev |
| W3 | **Terminal recording** | 30-second VHS/asciinema GIF showing: `claw skill run heartbeat`, `claw cron list`, `claw msg telegram "hello"`. Embedded in README. | Dev |
| W3 | **Dashboard screenshot** | Real screenshot of running dashboard showing status page, skill list, cron jobs. Annotated with callouts. Embedded in README. | Dev |
| W3 | **One-line install** | `curl -fsSL https://nexus.sh/install | sh` or `docker compose up -d` -- both paths documented and tested. Install script handles venv, pip, system deps. | Dev |
| W4 | **Documentation site** | MkDocs Material hosted on GitHub Pages at `docs.nexus.sh` (or `smartmur.github.io/nexus`). All existing `docs/` content migrated. Search enabled. | Dev |
| W4 | **CONTRIBUTING.md + issue templates** | Contribution guide, PR template, bug/feature issue templates. Code of conduct. "Good first issues" labeled (minimum 10). | Dev |
| W4 | **Ollama integration (multi-LLM, phase 1)** | `LLMProvider` updated to support Ollama as a backend. `NEXUS_LLM_PROVIDER=ollama` env var. Local models (llama3, mistral) work for all `claude-prompt` workflow steps and chat. Tests added. | Dev |

**Month 1 Exit Criteria**: Repo is public, visually polished, installable in < 5 minutes, documented, and supports at least 2 LLM backends (Claude + Ollama).

#### Month 2: Public Launch

| Week | Deliverable | Acceptance Criteria | Owner |
|------|------------|-------------------|-------|
| W5 | **OpenAI integration** | `LLMProvider` supports OpenAI API (GPT-4o, GPT-4o-mini). `NEXUS_LLM_PROVIDER=openai` env var. Automatic fallback chain: Claude -> OpenAI -> Ollama. Per-task model routing config. Tests added. | Dev |
| W5 | **Quick-start video** | 3-minute YouTube video: "Your first AI-powered server automation in 3 minutes." Shows install, heartbeat skill, Telegram notification. | Content |
| W6 | **Hacker News launch** | "Show HN: Nexus -- self-hosted AI that manages your infrastructure" post. Timed for Tuesday 10am ET. Author available for 8 hours of comment response. | Marketing |
| W6 | **Reddit launch (simultaneous)** | Posts to r/selfhosted, r/homelab, r/devops, r/claudeai, r/LocalLLaMA. Each post tailored to subreddit audience. | Marketing |
| W6 | **awesome-selfhosted submission** | PR to awesome-selfhosted with Nexus in "Automation" or "Software Development - IDE" category. | Marketing |
| W7 | **Post-launch fixes** | Triage all GitHub issues from launch week. Fix top 5 bugs. Respond to every issue within 24h. | Dev |
| W7 | **Discord server** | Community Discord with channels: general, support, showcase, contributing, announcements. Invite link in README and docs. | Community |
| W8 | **Blog post: architecture deep-dive** | "How Nexus Connects 8 Subsystems into One Platform" -- published on dev.to, hashnode, and personal blog. Cross-posted to HN. | Content |

**Month 2 Exit Criteria**: Public launch complete. Hacker News posted. 50+ GitHub stars. Discord community active. All launch-week bugs triaged.

#### Month 3: Post-Launch Momentum

| Week | Deliverable | Acceptance Criteria | Owner |
|------|------------|-------------------|-------|
| W9 | **Webhook inbound triggers** | New trigger type in workflow engine: `webhook`. External services can POST to `/api/webhooks/{id}` to trigger workflows. Auth via HMAC signature. | Dev |
| W9 | **WhatsApp channel adapter** | WhatsApp Business API adapter in `msg_gateway/channels/`. Requires user to provide their own WhatsApp Business API credentials. Send + receive. | Dev |
| W10 | **Skill browser web UI** | `/skills` page on dashboard showing browsable, searchable catalog of installed skills. One-click run. Install from SkillHub. | Dev |
| W10 | **Submit to product directories** | Product Hunt launch, AlternativeTo listing, StackShare listing, ToolJet alternatives pages. | Marketing |
| W11 | **Publish 5 skills to external catalogs** | Publish heartbeat, network-scan, ssl-cert-check, deploy, and docker-monitor skills to ClawHub and Tresor as distribution channels. | Dev |
| W11 | **First community blog roundup** | "Week 4: What the community built with Nexus" -- showcase 3-5 user-contributed workflows or skills. | Content |
| W12 | **Interactive onboarding wizard** | `claw setup init` guides new users through: LLM provider selection, channel configuration, first skill run, first cron job. Step-by-step with validation at each step. | Dev |

**Month 3 / Q1 Exit Criteria**: 150+ GitHub stars. 3+ external contributors. Webhook triggers working. WhatsApp channel live. Onboarding wizard shipped. Documentation site stable with analytics.

---

### Q2: Growth & Features (Months 4-6)

**Theme**: "Close the gaps. Build the moat deeper. Earn the community."

Q2 focuses on the three features identified in Phase 6 as critical gaps: multi-model support (completed in Q1), visual workflow builder, and agent orchestration.

#### Month 4: Visual Workflow Builder (MVP)

| Deliverable | Acceptance Criteria | Effort |
|------------|-------------------|--------|
| **Workflow visualization (read-only)** | Dashboard page at `/workflows/{name}` renders any YAML workflow as a visual DAG using a JavaScript library (Dagre, ELK, or ReactFlow via CDN). Nodes show step type, name, status. Edges show dependencies and conditions. | 2 weeks |
| **Workflow run visualization** | Active/completed workflow runs overlay status (pending/running/passed/failed) on each node in real time via WebSocket or SSE polling. Click a node to see its output. | 1 week |
| **Workflow editor (basic)** | Add/remove/reorder steps via drag-and-drop on the visual DAG. Changes serialize back to YAML. Save button writes to disk. Does NOT require implementing a full node editor -- this is structural editing of existing step types. | 2 weeks |
| **Workflow templates gallery** | Dashboard page showing 10+ starter workflow templates (deploy, backup, morning-brief, cert-renewal, security-scan, etc.) with "Use This Template" button that clones to user's workflow directory. | 1 week |

**Month 4 Acceptance**: Any YAML workflow can be viewed, run, and monitored visually. Basic structural editing works. 10+ templates available. This is NOT a full n8n-style node editor -- it is a visualization and management layer on top of YAML workflows.

#### Month 5: Agent Orchestration (Beat Tresor Sprint)

| Deliverable | Acceptance Criteria | Effort |
|------------|-------------------|--------|
| **Agent registry** (`superpowers/agent_registry.py`) | Agent manifests load from `subagents/**/agent.md`. `claw agent list` shows all agents with descriptions. `claw agent run <name>` executes. `claw agent recommend` suggests agents based on task context. | 12h |
| **DAG executor** (`superpowers/orchestrator.py`) | Dependency-aware parallel execution for multi-agent and multi-step orchestrations. Topological sort, conflict detection, safe parallelization. Proven by tests with fan-out/fan-in patterns. | 16h |
| **Orchestration command pack** (10 commands) | `claw` commands for: `audit`, `vuln-scan`, `compliance`, `profile`, `benchmark`, `deploy-validate`, `health-check`, `incident`, `code-health`, `debt-analysis`. Each produces structured JSON + markdown output. | 16h |
| **Reporting module** (`superpowers/reporting.py`) | Every orchestration command emits a structured artifact (JSON) + summary (Markdown). Reports stored in `~/.claude-superpowers/reports/`. Dashboard page at `/reports`. | 14h |
| **Auto agent selection** | Workflows and jobs auto-pick agents by analyzing task description and repo context. Override via `--agent` flag. | 10h |
| **Dashboard orchestration monitor** | `/orchestrations` page showing run queue, DAG execution graph, artifact links, status per node. | 12h |

**Month 5 Acceptance**: Tresor parity achieved. Agent registry operational. DAG executor proven with tests. 10 orchestration commands runnable. Competitive benchmark published.

#### Month 6: Community & RAG

| Deliverable | Acceptance Criteria | Effort |
|------------|-------------------|--------|
| **RAG pipeline (basic)** | `claw memory ingest <file>` processes PDF, Markdown, and plain text into chunked embeddings stored in SQLite (using sqlite-vec or similar). `claw memory search "query"` returns semantically relevant chunks. Works with local embedding models (via Ollama) or OpenAI embeddings. | 3 weeks |
| **Community skill marketplace (v1)** | Web page (GitHub Pages or dashboard) showing community-contributed skills with: name, description, author, install count, one-click install command. Skills hosted as Git repos. Index maintained as a JSON manifest. | 2 weeks |
| **Pack installer** | `claw setup install-pack <name>` installs curated bundles of skills + workflows + agent configs. Built-in packs: `homelab-essentials`, `security-ops`, `devops-toolkit`, `media-manager`. Checksum validation, rollback on failure. | 1 week |
| **Awesome Nexus list** | Curated list repo (`awesome-nexus`) with community workflows, skills, integrations, blog posts, videos, and deployment guides. Submit to awesome-list ecosystem. | 3 days |
| **Monthly community call** | First monthly community call on Discord. Agenda: roadmap update, contributor spotlight, live demo of new features, Q&A. Recorded and posted to YouTube. | Ongoing |

**Month 6 / Q2 Exit Criteria**: 500+ GitHub stars. Visual workflow viewer shipped. Agent orchestration operational. RAG pipeline working. Community marketplace launched. 10+ external contributors. First community call held.

---

### Q3: Scale & Community (Months 7-9)

**Theme**: "Let others build on the platform. Make Nexus self-sustaining."

#### Month 7: Plugin Architecture & SDK

| Deliverable | Acceptance Criteria |
|------------|-------------------|
| **Plugin SDK** | Python package (`nexus-sdk`) that third-party developers use to build skills, channel adapters, workflow step types, and dashboard widgets. Typed interfaces, auto-discovery, versioned compatibility. Published to PyPI. |
| **Channel plugin interface** | Any messaging channel can be added as a pip-installable plugin. Interface: `NexusChannel` base class with `send()`, `receive()`, `health()` methods. Existing 5 channels refactored to use this interface. |
| **Workflow step plugin interface** | Custom step types can be registered via plugins. Interface: `NexusStep` base class with `execute()`, `validate()`, `rollback()` methods. |
| **Matrix channel adapter** | Matrix/Element messaging channel as the first community-contributed channel plugin. Validates the plugin interface works for external developers. |
| **Signal channel adapter** | Signal messaging via signal-cli or signal-api as a plugin. Covers the #2 most-requested messaging channel after WhatsApp. |

#### Month 8: Mobile & Notifications

| Deliverable | Acceptance Criteria |
|------------|-------------------|
| **Mobile-responsive dashboard** | Dashboard works on phones and tablets. Responsive CSS, touch-friendly controls, simplified navigation. PWA manifest for "Add to Home Screen." |
| **Push notifications** | Web push notifications from dashboard for: workflow completions, alert escalations, approval gates, cron failures. Service worker + push API. |
| **Notification center** | Dashboard widget showing all recent notifications with read/unread status, filtering by type, and bulk actions. API endpoint for external consumption. |
| **Telegram mini-app** | Telegram bot enhanced with inline keyboards for: skill execution, workflow triggering, cron management, status checks. No need to remember commands -- interactive menus. |

#### Month 9: Stability & Documentation

| Deliverable | Acceptance Criteria |
|------------|-------------------|
| **1,500+ test suite** | Test coverage expanded from 982 to 1,500+ tests. New tests for: plugin SDK, channel plugins, DAG executor edge cases, RAG pipeline, webhook triggers, mobile views. |
| **Soak testing harness** | Automated 24-hour soak test that runs the full stack under load: cron jobs firing, workflows executing, messages routing, browser automating, SSH commands running. Zero crash loops, zero memory leaks, < 5% error rate. |
| **Cookbook site** | 30+ cookbook recipes at `cookbook.nexus.sh`: "Monitor SSL certs and alert on Telegram," "Auto-restart crashed Docker containers," "Morning briefing with weather + server status + calendar," "Deploy from GitHub webhook." Each recipe is copy-paste-ready. |
| **Contributor documentation** | Architecture guide for contributors: how to add a skill, how to add a channel, how to add a workflow step type, how to write tests. Video walkthrough. |
| **Internationalization (i18n)** | CLI and dashboard support English and one additional language (Spanish or Chinese, based on community interest). Framework for adding more languages. |

**Q3 Exit Criteria**: 1,500+ GitHub stars. Plugin SDK on PyPI. 7+ messaging channels. Mobile dashboard functional. 20+ contributors. 30+ cookbook recipes.

---

### Q4: Authority & Enterprise (Months 10-12)

**Theme**: "Establish authority. Attract enterprises. Prepare for sustainability."

#### Month 10: Enterprise Features

| Deliverable | Acceptance Criteria |
|------------|-------------------|
| **RBAC (Role-Based Access Control)** | Dashboard and API support multiple users with roles: `admin`, `operator`, `viewer`. Admins manage users. Operators can execute skills/workflows. Viewers can only read status. SSO integration via OIDC (Keycloak, Authentik, Okta). |
| **Audit compliance module** | Enhanced audit log with: tamper detection (hash chaining), export to SIEM (syslog, JSON, CEF), retention policies, compliance report generation (SOC 2 controls mapping). |
| **Policy engine** | YAML-defined policies that gate operations: "require approval for any SSH command to production hosts," "block workflows that touch vault secrets without MFA," "rate-limit skill executions per user." |
| **Multi-tenant namespaces** | Logical separation of skills, workflows, cron jobs, and vault entries by namespace. Teams can share a Nexus instance without seeing each other's data. |

#### Month 11: Kubernetes & Scale

| Deliverable | Acceptance Criteria |
|------------|-------------------|
| **Helm chart** | `nexus-helm` repo with production-grade Helm chart. Values for: replicas, resource limits, ingress, TLS, PVC, secrets management. Tested on K3s, K8s (EKS/GKE/AKS). Published to Artifact Hub. |
| **Horizontal scaling** | Message gateway and browser engine support multiple replicas behind a load balancer. Redis used for session affinity and job distribution. Cron engine uses distributed locking (Redis) to prevent duplicate execution. |
| **Prometheus metrics** | All services expose `/metrics` endpoints. Grafana dashboard template included. Alerts for: high error rate, cron failure, channel delivery failure, memory store growth. |
| **Backup and restore** | `claw backup create` exports all state (SQLite DBs, vault, workflows, skills, cron jobs, reports) to an encrypted tarball. `claw backup restore` imports. Scheduled via cron. |

#### Month 12: Authority & Sustainability

| Deliverable | Acceptance Criteria |
|------------|-------------------|
| **Conference talk delivered** | At least one conference talk delivered (KubeCon, FOSDEM, All Things Open, or equivalent). See Section 6 for proposed talks. |
| **Enterprise pilot** | At least one organization (startup, SMB, or team within a company) running Nexus in a non-hobby capacity. Documented case study. |
| **Sustainability model** | One of: (a) GitHub Sponsors active with 10+ sponsors, (b) Nexus Pro license for enterprise features (RBAC, audit compliance, multi-tenant), (c) Consulting/support offering documented. |
| **v1.0 release** | Semantic versioning adopted. v1.0 tagged with: stability guarantees, migration guide from 0.x, changelog, release notes. Published to PyPI. Docker images on Docker Hub and GHCR. |
| **Roadmap for year 2** | Community-driven roadmap for year 2 published. Voted on by contributors. Includes: Nexus Desktop, visual DAG editor v2, AI agent marketplace, native Windows support. |

**Q4 / Year 1 Exit Criteria**: 5,000+ GitHub stars. 50+ contributors. Helm chart on Artifact Hub. Enterprise features available. Conference talk delivered. v1.0 released. Sustainability model in place.

---

## 3. Core Feature Milestones

### Priority 1: Multi-LLM Support (Q1)

**Why first**: Phase 6 identified Claude-only LLM lock-in as the single most damaging competitive gap. Every major competitor supports 10+ providers. Users of GPT, Gemini, Ollama, and Mistral are locked out entirely.

| Milestone | Quarter | Details |
|-----------|---------|---------|
| Ollama backend | Q1M1 | Local models via Ollama API. Zero cloud dependency for AI features. |
| OpenAI backend | Q1M2 | GPT-4o, GPT-4o-mini via OpenAI SDK. |
| Automatic fallback chain | Q1M2 | Claude -> OpenAI -> Ollama. Configurable priority. |
| Per-task model routing | Q1M2 | Config to route `chat` tasks to fast models, `job` tasks to capable models. |
| Google Gemini backend | Q2 | Gemini Pro/Flash via Google AI SDK. |
| Anthropic direct API | Q2 | Anthropic SDK without Claude CLI dependency. |
| Custom endpoint support | Q3 | Any OpenAI-compatible API (vLLM, LMStudio, text-generation-webui). |

**Acceptance criteria for "multi-LLM complete"**: A user can install Nexus, configure `NEXUS_LLM_PROVIDER=ollama`, and use every feature (workflows, intake, chat, cron jobs with claude-prompt steps) without any cloud API key. This is the "sovereign" promise fulfilled.

### Priority 2: Visual Workflow Builder (Q2)

**Why second**: Phase 6 analysis shows visual builders are the #1 adoption driver for automation tools. n8n (177k stars) and Dify (130k stars) both attribute a significant portion of their growth to visual interfaces. YAML-only workflow definition is a hard ceiling on non-developer adoption.

| Milestone | Quarter | Details |
|-----------|---------|---------|
| Read-only DAG visualization | Q2M4 | Any YAML workflow renders as a visual graph on the dashboard. |
| Live run monitoring | Q2M4 | Running workflows show real-time status per node. |
| Structural editing | Q2M4 | Add, remove, reorder steps via drag-and-drop. Serializes to YAML. |
| Template gallery | Q2M4 | 10+ starter templates with one-click clone. |
| Condition editor | Q3 | Visual editor for step conditions (if/else branching). |
| Full node editor (v2) | Year 2 | ReactFlow-based full drag-and-drop workflow builder. New step creation from canvas. |

**Strategic note**: The Q2 visual builder is intentionally NOT a full n8n-style node editor. Building a competitive visual workflow editor is a multi-year effort. Instead, Nexus will ship a visualization and management layer on top of YAML -- which is achievable in 4-6 weeks -- and position it as "visual monitoring with AI-powered workflow generation." The pitch: "You don't need to drag and drop. Tell Claude what you want and it writes the workflow." This reframes the lack of a GUI as a feature, not a gap.

### Priority 3: Agent Orchestration (Q2)

**Why third**: This is the "Beat Tresor" sprint. Tresor is a direct competitor in the Claude Code ecosystem with growing traction. Nexus must demonstrate superior agent orchestration to claim the "platform, not a skill collection" position.

| Milestone | Quarter | Details |
|-----------|---------|---------|
| Agent registry + CLI | Q2M5 | `claw agent list/run/recommend`. Manifests in `subagents/`. |
| DAG executor | Q2M5 | Dependency-aware parallel execution with topological sort. |
| 10 orchestration commands | Q2M5 | audit, vuln-scan, compliance, profile, benchmark, deploy-validate, health-check, incident, code-health, debt-analysis. |
| Structured reporting | Q2M5 | JSON + Markdown artifacts for every orchestration run. |
| Auto agent selection | Q2M5 | Context-aware agent recommendation. |
| Dashboard monitor | Q2M5 | Run queue, DAG graph, artifact viewer. |

### Priority 4: Plugin Marketplace (Q3)

**Why fourth**: Once the platform is stable and has users (Q1-Q2), the growth multiplier shifts from features to ecosystem. A plugin marketplace enables community contributions without gating on core team bandwidth.

| Milestone | Quarter | Details |
|-----------|---------|---------|
| Plugin SDK (`nexus-sdk` on PyPI) | Q3M7 | Typed interfaces for skills, channels, step types, widgets. |
| Community skill browser (web) | Q2M6 | Browsable catalog with search, categories, install commands. |
| Ratings and reviews | Q3 | Users can rate skills. Sorted by popularity. |
| One-click install from browser | Q3 | "Install" button on skill page runs `claw skill install <name>`. |
| Verified publisher program | Q4 | Trusted contributors get a verified badge on their plugins. |

### Priority 5: Mobile Dashboard (Q3)

**Why fifth**: Mobile access matters for operations (you get paged at 2am, you check your phone). But it is not a launch blocker -- Telegram and Slack already provide mobile access to core functions.

| Milestone | Quarter | Details |
|-----------|---------|---------|
| Responsive CSS | Q3M8 | Dashboard usable on phones. Touch targets, simplified nav. |
| PWA manifest | Q3M8 | "Add to Home Screen" on iOS and Android. |
| Push notifications | Q3M8 | Web push for alerts, completions, approvals. |
| Offline status cache | Q4 | Service worker caches last-known status for offline viewing. |

### Priority 6: Enterprise Features (Q4)

**Why last**: Enterprise features are not star drivers. They are revenue drivers. Building them before having a community would be premature. But having them ready by month 10-12 enables the sustainability model.

| Milestone | Quarter | Details |
|-----------|---------|---------|
| RBAC | Q4M10 | Admin, operator, viewer roles. OIDC SSO. |
| Audit compliance | Q4M10 | Hash-chained audit log, SIEM export, SOC 2 mapping. |
| Policy engine | Q4M10 | YAML-defined operation gates with approval workflows. |
| Multi-tenancy | Q4M10 | Namespace isolation for teams. |
| Helm chart | Q4M11 | Production K8s deployment. Artifact Hub published. |

---

## 4. Ecosystem Expansion

### New Repositories to Build

Each repo below serves a specific function in the Nexus ecosystem. They should only be created when the feature they represent is ready -- empty repos with READMEs are worse than no repo.

#### 4.1 Nexus Recipes (`nexus-recipes`)

**What**: Community-contributed workflow library. Curated, tested, categorized.

**Structure**:
```
nexus-recipes/
  homelab/
    morning-briefing.yaml
    ssl-cert-monitor.yaml
    backup-verify.yaml
  devops/
    deploy-pipeline.yaml
    rollback-on-failure.yaml
    pr-review-bot.yaml
  security/
    vuln-scan-weekly.yaml
    credential-rotation.yaml
    intrusion-response.yaml
  media/
    download-monitor.yaml
    transcode-notify.yaml
  README.md        # browsable index with categories
  CONTRIBUTING.md  # how to submit a recipe
  test/            # CI that validates all YAML workflows parse correctly
```

**When to create**: Q2M6, alongside the community marketplace launch.

**Star potential**: High. Recipe repos are inherently bookmarkable. `awesome-selfhosted` (276k stars) proves curated lists attract stars even without executable code.

#### 4.2 Nexus Helm Chart (`nexus-helm`)

**What**: Production-grade Kubernetes deployment for Nexus.

**Contents**:
```
nexus-helm/
  charts/nexus/
    Chart.yaml
    values.yaml          # all configurable knobs
    templates/
      deployment.yaml    # nexus-core (dashboard + CLI)
      statefulset.yaml   # redis
      deployment.yaml    # browser-engine
      deployment.yaml    # msg-gateway
      deployment.yaml    # telegram-bot
      configmap.yaml     # env config
      secret.yaml        # vault identity, API keys
      ingress.yaml       # TLS termination
      pvc.yaml           # persistent volumes for SQLite, vault, skills
      hpa.yaml           # horizontal pod autoscaler
      networkpolicy.yaml # pod-to-pod restrictions
    tests/
      test-connection.yaml
  README.md
  INSTALL.md
```

**When to create**: Q4M11, after horizontal scaling is proven.

**Strategic value**: Kubernetes is the deployment target for any serious infrastructure. A Helm chart on Artifact Hub is discoverable by the entire K8s ecosystem. It also unlocks enterprise adoption -- teams running K8s will not adopt a Docker-Compose-only tool.

#### 4.3 Nexus Desktop (`nexus-desktop`)

**What**: Electron wrapper around the Nexus dashboard + embedded Nexus runtime. One-click install on macOS, Windows, Linux.

**Why**: Eliminates the Docker/Python/venv setup barrier entirely. Downloads as a .dmg/.exe/.AppImage, starts Nexus locally with SQLite + embedded browser engine. The "Obsidian model" -- a powerful local app with optional sync.

**When to create**: Year 2 (not in 12-month roadmap). Building a desktop app before the web experience is polished is a mistake.

**Star potential**: Very high. Desktop apps with download buttons convert visitors to users at dramatically higher rates than "clone + docker compose up" workflows.

#### 4.4 VS Code Extension (`nexus-vscode`)

**What**: VS Code extension that integrates Nexus into the editor sidebar: skill browser, workflow runner, cron manager, memory search, SSH terminal, status dashboard.

**Why**: VS Code has 14M+ monthly active users. An extension in the VS Code Marketplace is discoverable by the entire developer population. It also provides a natural bridge from "VS Code user" to "Nexus user."

**When to create**: Q3-Q4, after the Plugin SDK is stable.

**Contents**:
- Sidebar panel: Nexus status, skill list, cron jobs
- Command palette: `Nexus: Run Skill`, `Nexus: Create Workflow`, `Nexus: Remember`
- Status bar: connection status, last cron run
- Terminal integration: `claw` commands with output in VS Code terminal
- Webview: embedded dashboard panels

#### 4.5 Nexus Ansible Collection (`nexus-ansible`)

**What**: Ansible Galaxy collection with modules for managing Nexus programmatically: `nexus_skill`, `nexus_cron`, `nexus_workflow`, `nexus_vault`, `nexus_channel`.

**Why**: Bridges the gap between traditional infrastructure automation (Ansible) and AI-native automation (Nexus). Allows existing Ansible users to incorporate Nexus into their playbooks without rewriting everything.

**When to create**: Q3, after the REST API is stable and documented.

#### 4.6 Awesome Nexus (`awesome-nexus`)

**What**: Curated list of Nexus resources: skills, workflows, channel adapters, blog posts, videos, deployment guides, community projects.

**When to create**: Q2M6, as a seed for community discovery.

**Star potential**: Moderate as a standalone, but serves as a community hub and SEO anchor.

---

## 5. What Makes This 10k-Star Worthy

10,000 stars on GitHub requires a specific combination of factors. Based on analysis of 50+ projects that crossed this threshold (detailed in Phase 5), here is the concrete feature set and positioning that would earn Nexus 10k stars.

### The 10k-Star Feature Set

| Feature | Why It Matters for Stars | Status |
|---------|------------------------|--------|
| **One-line install** | Removes adoption friction. Every 10k+ project installs in < 2 minutes. | Needed Q1 |
| **Visual dashboard with screenshots** | "I can see what it does before I install it." Every 10k+ project has at least 3 screenshots in the README. | Needed Q1 |
| **Multi-LLM support** | Unlocks the entire AI community, not just Claude users. OpenAI alone adds 100M potential users. | Needed Q1 |
| **30-second demo GIF** | The single highest-impact visual asset. Repos with animated demos get 3x more stars per visitor. | Needed Q1 |
| **10+ working integrations** | Each integration is a new keyword, a new audience, a new reason to bookmark. 7 channels + 5 step types + N skills = compound discoverability. | Partial (need more channels) |
| **Plugin/skill marketplace** | Transforms from "a tool" to "an ecosystem." Ecosystems attract stars exponentially. | Needed Q2-Q3 |
| **Cookbook with 30+ recipes** | Each recipe is independently shareable and searchable. "Nexus recipe for monitoring SSL certs" becomes its own traffic source. | Needed Q3 |
| **Kubernetes deployment** | Unlocks the DevOps/platform engineering audience. K8s users expect Helm charts. | Needed Q4 |
| **1,500+ tests** | Signals exceptional quality. Most projects at this scale have < 200 tests. | Need to grow |
| **Active community** (50+ contributors) | Social proof cascade. Contributors attract more contributors. | Need to build |

### The 10k-Star Positioning

Feature set alone does not reach 10k. Positioning matters equally.

**Nexus must own a category**. The category is: **"AI-Native Infrastructure Automation."**

This means:

1. **Every Google search for "self-hosted AI automation"** should return Nexus in the top 5 results. This requires: SEO-optimized docs site, blog posts on target keywords, awesome-list presence, Stack Overflow answers referencing Nexus.

2. **Every conference talk about AI + DevOps** should mention Nexus as a reference. This requires: speaking at 2-3 conferences per year, publishing case studies, engaging with the DevOps/SRE community.

3. **Every homelab enthusiast considering "how do I add AI to my lab"** should find Nexus. This requires: presence on r/selfhosted, r/homelab, awesome-selfhosted, YouTube tutorials by homelab creators.

4. **Every Claude Code power user** should know Nexus exists. This requires: Anthropic developer community engagement, Claude Code forum posts, MCP tool listings, skill marketplace presence.

### The 10k Timeline

Reaching 10k stars in 12 months is aggressive but not unprecedented. Dify went from 0 to 130k in 18 months. Uptime Kuma went from 0 to 50k in 2 years. OpenClaw hit 130k in 6 weeks (extreme outlier with celebrity founder + viral timing).

For a solo/small-team project without an existing audience, realistic benchmarks from comparable projects (Dockge, Homepage, Liam ERD) suggest:

| Milestone | Typical Timeline | Accelerators |
|-----------|-----------------|-------------|
| 100 stars | 1-2 weeks post-launch | HN front page, viral Reddit post |
| 500 stars | 2-3 months | Sustained content marketing, awesome-list inclusion |
| 1,000 stars | 4-6 months | Product Hunt launch, YouTube coverage, conference mention |
| 2,500 stars | 6-9 months | Plugin ecosystem attracting contributors, organic SEO |
| 5,000 stars | 9-12 months | Category authority, repeat HN appearances, enterprise interest |
| 10,000 stars | 12-18 months | All of the above + community self-sustaining growth |

**Conservative 12-month target**: 5,000 stars.
**Stretch target**: 10,000 stars (requires at least one viral moment + sustained community growth).

---

## 6. What Makes This Conference-Talk Worthy

### Proposed Talks

#### Talk 1: "AI That Runs Your Infrastructure: Building a Sovereign AI Operations Platform"

**Target conferences**: KubeCon (Operations track), FOSDEM (Infra devroom), All Things Open, DevOpsDays
**Duration**: 30 minutes
**Abstract**:
> What happens when you give an AI agent SSH access, a cron scheduler, browser automation, and multi-channel messaging -- and tell it to manage your infrastructure? This talk presents Nexus, an open-source platform that turns Claude, GPT, and local LLMs into autonomous infrastructure operators. We will demonstrate a real workflow where an AI agent detects a failed container, diagnoses the issue using logs and screenshots, proposes a fix, waits for human approval via Telegram, executes the remediation, and documents the incident -- all without a human touching a keyboard. We will discuss the architecture (6-layer stack, 982 tests), the security model (encrypted vault, sandboxed execution, approval gates), and the hard lessons learned about giving AI agents access to production systems.

**Why it gets accepted**: The "AI + infrastructure" intersection is the hottest topic in DevOps. Conference organizers are desperate for talks that go beyond chatbot demos into real operational use cases.

#### Talk 2: "From Homelab to Platform: How 982 Tests and Zero Stars Became an Open-Source Movement"

**Target conferences**: Open Source Summit, SCALE (Southern California Linux Expo), PyCon
**Duration**: 25 minutes
**Abstract**:
> This is a talk about what happens when a homelab project gets serious. It started as personal automation scripts. It became a platform with 8 integrated subsystems, a 982-test suite, Docker Compose deployment, and multi-model AI support. But it had zero stars and zero users. This talk covers the strategic repositioning from "my homelab scripts" to "the sovereign AI operations platform" -- including the competitive analysis, the README rewrite, the launch strategy, and the hard truths about what actually earns GitHub stars (hint: it is not code quality). We will share real numbers: star growth curves, traffic sources, conversion rates, and what worked vs. what wasted time.

**Why it gets accepted**: Conference audiences love "zero to hero" stories with real numbers. The meta-narrative (how to position open-source projects) is universally relevant.

#### Talk 3: "Approval Gates: The Missing Safety Layer for AI Agents in Production"

**Target conferences**: MLOps World, AI Engineer Summit, Anthropic Dev Day (if exists)
**Duration**: 20 minutes
**Abstract**:
> Most AI agent frameworks assume full autonomy or nothing. In production infrastructure, neither extreme works. You cannot let an AI agent restart production servers without approval, and you cannot require manual approval for every log query. This talk presents the approval gate pattern implemented in Nexus: workflow steps that pause execution, send a notification to Telegram/Slack/email with context and options, wait for human confirmation, and resume or abort based on the response. We will show real examples, discuss the UX of "AI asking permission," and present a taxonomy of when to gate vs. when to let agents act autonomously.

**Why it gets accepted**: AI safety in production is a growing concern. This talk offers a concrete, implemented solution rather than theoretical hand-waving.

#### Talk 4: "Building a Plugin SDK for an Automation Platform: Lessons from Nexus"

**Target conferences**: PyCon, EuroPython, PyTexas
**Duration**: 30 minutes
**Abstract**:
> When we built Nexus, we needed third-party developers to extend it with new messaging channels, workflow step types, and skills -- without touching core code. This talk covers the design and implementation of the Nexus Plugin SDK: typed interfaces with `Protocol` classes, auto-discovery via entry points, sandboxed execution, version compatibility contracts, and the testing infrastructure that lets plugin authors validate their code against any Nexus version. Includes live demo of building a plugin from scratch.

**Why it gets accepted**: Plugin architecture is a perennial PyCon topic. Concrete implementation details from a real project are more valuable than abstract patterns.

### Conference Calendar (12-month)

| Conference | Date (approximate) | Talk Submitted | Relevance |
|-----------|-------------------|----------------|-----------|
| FOSDEM | Feb 2027 | Talk 1 or Talk 2 | Infrastructure devroom, massive European audience |
| PyCon US | May 2027 | Talk 4 | Python community, plugin architecture |
| KubeCon NA | Nov 2026 or May 2027 | Talk 1 | Operations track, K8s audience |
| All Things Open | Oct 2026 | Talk 2 | Broad open-source audience |
| DevOpsDays (local) | Various | Talk 1 or Talk 3 | Regional DevOps community |
| SCALE | Mar 2027 | Talk 2 | Linux/self-hosted community |
| AI Engineer Summit | 2027 | Talk 3 | AI engineering audience |
| Anthropic community event | TBD | Talk 1 | Claude Code ecosystem |

**Minimum viable conference presence**: 1 talk accepted and delivered within 12 months. Target: 3 talks across different conferences.

---

## 7. What Makes This Enterprise-Relevant

### Features Enterprises Would Pay For

Enterprises do not pay for features they can build themselves in a weekend. They pay for features that reduce risk, prove compliance, and save operational time. Here is what Nexus can offer.

#### Tier 1: Enterprise Core ($500-2,000/month per team)

| Feature | Enterprise Need | Implementation |
|---------|----------------|----------------|
| **RBAC with SSO** | "Who can run commands on production servers?" Enterprises need user isolation and audit trails per user. They need OIDC integration with existing identity providers (Okta, Azure AD, Keycloak). | Q4M10 |
| **Audit compliance reporting** | "Show me every action taken on infrastructure in the last 90 days, in a format my auditor accepts." SOC 2 Type II requires tamper-evident logs, access controls, and change management records. | Q4M10 |
| **Policy engine** | "No SSH command to production without manager approval." "No vault secret access without MFA." Enterprises need configurable guardrails that prevent AI agents from taking dangerous actions without oversight. | Q4M10 |
| **SLA monitoring** | "Alert me if any workflow takes longer than its SLA." Workflow execution time tracking with SLA thresholds and escalation chains. | Q4 |

#### Tier 2: Enterprise Scale ($2,000-5,000/month)

| Feature | Enterprise Need | Implementation |
|---------|----------------|----------------|
| **Multi-tenancy** | "3 teams share one Nexus instance. Team A cannot see Team B's vault secrets, skills, or workflows." Namespace isolation with configurable sharing. | Q4M10 |
| **High availability** | "Nexus cannot be a single point of failure." Redis Sentinel/Cluster for cache HA. Distributed cron locking. Multi-replica message gateway. Automated failover. | Q4M11 |
| **Priority support** | "When Nexus breaks at 2am, I need someone to respond." Guaranteed response times, dedicated Slack/email channel, quarterly architecture review. | Q4M12 |
| **Custom integrations** | "We use ServiceNow for ticketing and PagerDuty for alerting. Build us adapters." Professional services for custom channel adapters, workflow integrations, and skill development. | Ongoing |

#### Tier 3: Enterprise Premium ($5,000-15,000/month)

| Feature | Enterprise Need | Implementation |
|---------|----------------|----------------|
| **Air-gapped deployment** | "Our production environment has no internet access." Full offline installation with local LLM (Ollama), no external API calls, bundled dependencies. | Requires multi-LLM + Helm |
| **FedRAMP / HIPAA compliance assistance** | Documentation and configuration guidance for deploying Nexus in regulated environments. Encrypted at rest, encrypted in transit, audit trail. | Docs + hardening guide |
| **Custom training** | On-site or remote training for DevOps teams on building skills, workflows, and agent orchestrations. | Professional services |
| **Dedicated instance management** | Nexus-as-a-Service: we run and manage a Nexus instance for the customer on their infrastructure. | MSP model |

### Enterprise Sales Strategy

1. **Open-core model**: Core platform remains MIT/Apache 2.0 open source. Enterprise features (RBAC, compliance, multi-tenancy, HA) available under a commercial license.
2. **Self-service trial**: Enterprises can deploy Nexus via Helm chart and evaluate all features for 30 days. Enterprise features degrade gracefully (RBAC falls back to single-admin, audit log continues without compliance export).
3. **Land-and-expand**: One team adopts Nexus for homelab/dev. They demonstrate value. Other teams request access. The "multi-tenancy" requirement emerges naturally. Enterprise license follows.
4. **Channel partners**: Partner with managed hosting providers (Elest.io, PikaPods, Railway) to offer one-click Nexus deployment with enterprise features enabled.

### Why Enterprises Would Choose Nexus Over Alternatives

| Alternative | Why Nexus Wins |
|-------------|---------------|
| **n8n** | Nexus has SSH fabric, browser automation, encrypted vault, and AI-native workflows. n8n is workflow-only with no infrastructure management. |
| **Ansible Tower / AWX** | Nexus adds AI reasoning to every workflow. Ansible is static playbooks; Nexus workflows include `claude-prompt` steps that dynamically adapt. |
| **Backstage** | Nexus is lighter, faster to deploy, and AI-native. Backstage requires a dedicated team to maintain. Nexus runs on a single Docker Compose. |
| **DIY scripts** | Nexus provides the tested, audited, production-ready platform that enterprises cannot build themselves (or maintain) with a collection of scripts. |

---

## 8. Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Claude Code API/skill format changes** | High (Anthropic iterates fast) | High -- could break MCP integration, skill format, CLI hooks | Abstraction layers already exist. Pin to Claude Code versions. Maintain compatibility tests. Budget 1 week per quarter for upstream compatibility. |
| **Playwright/browser engine instability** | Medium | Medium -- browser automation is a differentiator | Pin Playwright versions. Run browser tests in CI. Fall back to screenshot-only mode if full automation fails. |
| **SQLite scaling limits** | Medium (at >10k cron jobs or >1M memory entries) | Medium -- performance degradation | Migration path to PostgreSQL documented. SQLite WAL mode handles most workloads. Only migrate when benchmarks prove necessity. |
| **Security vulnerability in exposed services** | Medium | Critical -- dashboard, webhook endpoint, Telegram bot are attack surfaces | Rate limiting implemented. JWT auth on dashboard. HMAC on webhooks. Regular dependency audits. Bug bounty program (future). |
| **Ollama/local model quality insufficient** | Medium | Medium -- users expecting GPT-4 quality from local models will be disappointed | Document model quality expectations clearly. Recommend model sizes per use case. Maintain Claude/OpenAI as primary paths. |

### Community Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Launch fails to gain traction** | Medium | High -- without initial momentum, the project stalls | Multiple launch vectors (HN, Reddit, Product Hunt, awesome-lists). If first launch underperforms, iterate on README/messaging and relaunch 30 days later. Projects often have 2-3 "launches." |
| **Contributors submit low-quality PRs** | High (common for popular repos) | Low-Medium -- review burden | Comprehensive contributing guide. PR template with checklist. CI that blocks merge without tests. "Good first issues" that channel new contributors to well-scoped tasks. |
| **Fork with better marketing** | Low-Medium | High -- someone forks Nexus, adds a visual editor, and markets it better | Maintain velocity. Ship the visual builder before someone else does. Build community loyalty through responsiveness and quality. The 982+ test suite is a moat against low-effort forks. |
| **Key maintainer burnout** | High (single-maintainer risk) | Critical -- project dies | Actively cultivate 3+ co-maintainers by Q3. Delegate review, release, and community management. Set boundaries on response times. Automate everything automatable. |
| **Community toxicity** | Low-Medium | Medium -- drives away contributors | Code of conduct enforced from day 1. Moderation in Discord. Block/ban policy. Welcoming first-contribution experience. |

### Market Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **OpenClaw adds infrastructure management** | Low (different focus) | High -- eliminates key differentiator | Move fast on SSH fabric, cron, and browser automation integrations. Establish "AI-native infra" as Nexus's category before competitors enter. |
| **Anthropic ships "Claude DevOps"** | Low-Medium | Critical -- upstream competition | Position Nexus as the open-source, model-agnostic, self-hosted alternative. If Anthropic ships a proprietary DevOps product, Nexus becomes the sovereign alternative. |
| **AI agent hype cycle crashes** | Medium (hype cycles are real) | Medium -- reduced interest in AI automation tools | Nexus has value independent of AI: cron engine, SSH fabric, workflow engine, vault are useful without LLM features. Position as "automation platform with optional AI" not "AI platform." |
| **Self-hosted movement loses momentum** | Low | Medium -- smaller addressable market | Self-hosting is growing, not shrinking. Privacy regulations (GDPR, CCPA) push more organizations toward self-hosted solutions. |
| **License complications** | Low | Medium -- legal friction for enterprise adoption | Choose MIT or Apache 2.0 (both well-understood). Document license compatibility for all dependencies. Enterprise tier uses a separate commercial license. |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Infrastructure costs for docs/CI/community** | Medium | Low-Medium | GitHub Pages (free), GitHub Actions (free for public repos), Discord (free). Total operational cost < $50/month for the first year. |
| **Domain/branding conflict** | Low-Medium ("Nexus" is a common word) | Medium -- forced rebrand is expensive | Check trademark databases before committing. Register `nexus.sh` or `nexus-ai.sh` domain early. Consider `nexus-ops.dev` if primary domain unavailable. |
| **Test suite maintenance burden** | Medium (982 tests is a lot) | Low-Medium -- slow CI, flaky tests | Parallelize test execution. Mark slow tests. Fix flaky tests immediately (never skip). Target < 3 minute CI time. |

---

## 9. Success Metrics & KPIs

### Q1: Foundation & Launch (Months 1-3)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **GitHub stars** | 150+ | GitHub API |
| **GitHub forks** | 20+ | GitHub API |
| **Unique cloners** | 100+ | GitHub Traffic insights |
| **README views** | 5,000+ | GitHub Traffic insights |
| **External contributors** | 3+ | GitHub contributor graph |
| **Open issues** | 20+ (healthy signal of usage) | GitHub Issues |
| **Closed issues** | 15+ (healthy signal of maintenance) | GitHub Issues |
| **Documentation site visitors** | 500+ unique | Analytics |
| **Discord members** | 50+ | Discord server stats |
| **Test count** | 1,100+ (from 982 baseline) | CI output |
| **LLM backends supported** | 3 (Claude, OpenAI, Ollama) | Feature checklist |
| **Install-to-first-skill time** | < 5 minutes | Manual testing |
| **HN launch** | 1 post, 50+ upvotes | HN |
| **Awesome-list inclusion** | 1+ lists | PR merged |

### Q2: Growth & Features (Months 4-6)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **GitHub stars** | 500+ | GitHub API |
| **GitHub forks** | 60+ | GitHub API |
| **External contributors** | 10+ | GitHub contributor graph |
| **PyPI downloads** | 500+ monthly | PyPI stats |
| **Docker Hub pulls** | 1,000+ | Docker Hub stats |
| **Community skills published** | 5+ (not by core team) | Marketplace index |
| **Workflow templates** | 10+ | Template gallery |
| **Blog posts (external, about Nexus)** | 3+ | Google Alerts |
| **Discord members** | 150+ | Discord server stats |
| **Test count** | 1,300+ | CI output |
| **Visual workflow builder** | Shipped (read + edit) | Feature checklist |
| **Agent orchestration commands** | 10 operational | Feature checklist |
| **RAG pipeline** | Working with local models | Feature checklist |
| **Product Hunt launch** | 1 launch, top-10 daily | Product Hunt |

### Q3: Scale & Community (Months 7-9)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **GitHub stars** | 1,500+ | GitHub API |
| **External contributors** | 20+ | GitHub contributor graph |
| **PyPI downloads** | 2,000+ monthly | PyPI stats |
| **Plugin SDK installs** | 100+ | PyPI stats |
| **Community plugins** | 10+ | Marketplace index |
| **Messaging channels** | 7+ (add Matrix, Signal) | Feature checklist |
| **Cookbook recipes** | 30+ | Cookbook site |
| **Conference CFPs submitted** | 3+ | Submission tracker |
| **YouTube tutorials (external)** | 3+ | YouTube search |
| **Discord members** | 300+ | Discord server stats |
| **Test count** | 1,500+ | CI output |
| **Mobile dashboard** | Shipped (responsive + PWA) | Feature checklist |
| **i18n languages** | 2+ | Feature checklist |

### Q4: Authority & Enterprise (Months 10-12)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **GitHub stars** | 5,000+ | GitHub API |
| **External contributors** | 50+ | GitHub contributor graph |
| **PyPI downloads** | 5,000+ monthly | PyPI stats |
| **Docker Hub pulls** | 10,000+ | Docker Hub stats |
| **Helm chart installs** | 100+ | Artifact Hub stats |
| **Enterprise pilots** | 1+ | Sales pipeline |
| **Conference talks delivered** | 1+ | Conference programs |
| **Conference talks accepted** | 2+ | Acceptance notifications |
| **Blog posts (external)** | 10+ total | Google Alerts |
| **Discord members** | 500+ | Discord server stats |
| **Test count** | 1,800+ | CI output |
| **v1.0 released** | Yes | GitHub Releases |
| **Revenue (if applicable)** | $1,000+ MRR | Payment processor |
| **GitHub Sponsors** | 10+ sponsors | GitHub Sponsors dashboard |

### Trailing Indicators (Measured Monthly)

| Metric | What It Tells You |
|--------|------------------|
| **Star velocity** (stars/week) | Overall growth momentum. Declining velocity = content/marketing needs refresh. |
| **Issue close time** (median) | Maintainer responsiveness. Target < 48h for bugs, < 1 week for features. |
| **PR merge time** (median) | Contributor experience. Target < 72h for clean PRs. |
| **Returning visitors** (docs site) | Whether users stick around. Target 30%+ return rate. |
| **Skill install count** | Whether the ecosystem is growing. Each skill install is a deeper engagement. |
| **Discord active users** (weekly) | Community health. Target 20%+ of total members active weekly. |

---

## Appendix: Dependency Graph

The following diagram shows the dependency relationships between major roadmap items. Items must be completed in dependency order; items at the same level can be parallelized.

```
                        LICENSE + RENAME
                             |
                    VISUAL IDENTITY + README
                             |
                   +---------+---------+
                   |                   |
              DOCS SITE          MULTI-LLM
              (MkDocs)        (Ollama+OpenAI)
                   |                   |
                   +---------+---------+
                             |
                        PUBLIC LAUNCH
                        (HN + Reddit)
                             |
              +--------------+--------------+
              |              |              |
        WEBHOOK         WHATSAPP      ONBOARDING
        TRIGGERS        CHANNEL        WIZARD
              |              |              |
              +--------------+--------------+
                             |
              +--------------+--------------+
              |              |              |
         VISUAL          AGENT          RAG
         WORKFLOW      ORCHESTRATION   PIPELINE
         BUILDER       (Beat Tresor)
              |              |              |
              +--------------+--------------+
                             |
              +--------------+--------------+
              |              |              |
         PLUGIN SDK    COMMUNITY       COOKBOOK
         (PyPI)        MARKETPLACE     (30 recipes)
              |              |              |
              +--------------+--------------+
                             |
              +--------------+--------------+
              |              |              |
         MOBILE          MATRIX +       i18n
         DASHBOARD       SIGNAL
              |              |
              +--------------+
                             |
              +--------------+--------------+
              |              |              |
          RBAC +         HELM CHART     POLICY
          SSO            (K8s)          ENGINE
              |              |              |
              +--------------+--------------+
                             |
                          v1.0
                        RELEASE
```

### Critical Path

The longest dependency chain determines the minimum time to v1.0:

```
License (W1) -> Visual Identity (W2) -> README (W2) -> Docs Site (W4) ->
Public Launch (M2W6) -> Visual Workflow (M4) -> Plugin SDK (M7) ->
RBAC (M10) -> Helm Chart (M11) -> v1.0 Release (M12)
```

This critical path has zero slack. Any delay on the critical path delays v1.0. Non-critical-path items (WhatsApp, RAG, cookbook, i18n) can slip without affecting the release date.

### Parallelization Opportunities

| Time Period | Parallel Workstreams |
|-------------|---------------------|
| M1 | Visual identity + Ollama integration + docs site (3 parallel) |
| M2 | OpenAI integration + launch prep + community setup (3 parallel) |
| M3 | Webhook triggers + WhatsApp + onboarding wizard (3 parallel) |
| M4 | Visual workflow builder + cookbook writing (2 parallel) |
| M5 | Agent orchestration + community marketplace prep (2 parallel) |
| M6 | RAG pipeline + awesome-nexus + community call setup (3 parallel) |
| M7 | Plugin SDK + Matrix adapter + contributor docs (3 parallel) |
| M8 | Mobile dashboard + Signal adapter + push notifications (3 parallel) |
| M9 | Soak testing + cookbook expansion + i18n (3 parallel) |
| M10 | RBAC + audit compliance + policy engine (3 parallel) |
| M11 | Helm chart + horizontal scaling + Prometheus metrics (3 parallel) |
| M12 | Conference prep + enterprise pilot + v1.0 packaging (3 parallel) |

---

## Summary

This roadmap is designed to be executable by a small team (1-3 people) with clear priorities: launch first (Q1), build the moat deeper (Q2), let the community multiply the effort (Q3), and monetize for sustainability (Q4).

The single most important insight from the competitive analysis is this: **Nexus does not need to be the biggest AI automation platform. It needs to be the best one for people who run their own infrastructure.** That niche is large enough for 10k+ stars, conference talks, and enterprise revenue -- but small enough that a focused team can own it before anyone else does.

The clock starts when the repo goes public. Every week of delay is a week where the "AI-native infrastructure automation" category remains unclaimed.

---

*Document generated as part of the SmartMur Ecosystem Repositioning initiative.*
*Phases completed: 1 (Identity), 2 (Architecture), 5 (Star Strategy), 6 (Competitive), 7 (Roadmap).*
*Remaining phases: 3 (Repo Reorganization), 4 (Messaging Upgrade).*
