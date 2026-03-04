# Phase 3: Repo Reorganization Strategy

**Date**: 2026-03-03
**Scope**: All 10 SmartMur GitHub repositories
**Goal**: Transform a collection of personal repos into a cohesive, discoverable, professionally branded open-source ecosystem

---

## Table of Contents

1. [Repo-by-Repo Analysis](#1-repo-by-repo-analysis)
   - [1.1 claude-superpowers (Nexus Core)](#11-claude-superpowers--nexus-core)
   - [1.2 k3s-cluster (Nexus Cluster)](#12-k3s-cluster--nexus-cluster)
   - [1.3 homelab (Nexus Infra)](#13-homelab--nexus-infra)
   - [1.4 home_media (Nexus Media)](#14-home_media--nexus-media)
   - [1.5 dotfiles (Nexus Bootstrap)](#15-dotfiles--nexus-bootstrap)
   - [1.6 claude-code-tresor (Nexus Vault Agent)](#16-claude-code-tresor--nexus-vault-agent)
   - [1.7 claude-code-skill-factory (Nexus Skill Factory)](#17-claude-code-skill-factory--nexus-skill-factory)
   - [1.8 agent-os (Nexus Agent OS)](#18-agent-os--nexus-agent-os)
   - [1.9 Lighthouse-AI](#19-lighthouse-ai)
   - [1.10 Smoke](#110-smoke)
2. [Merge and Archive Decisions](#2-merge-and-archive-decisions)
3. [Cross-Linking Strategy](#3-cross-linking-strategy)
4. [Topic Tags](#4-topic-tags)
5. [Pinned Repos](#5-pinned-repos)
6. [Execution Roadmap](#6-execution-roadmap)

---

## 1. Repo-by-Repo Analysis

---

### 1.1 claude-superpowers / Nexus Core

#### Current State

- **Structure**: Monorepo containing 6 Python packages (`superpowers/`, `msg_gateway/`, `dashboard/`, `browser_engine/`, `telegram-bot/`, `skills/`), 4 workflow definitions, 14 skills, 982 tests, 70 REST endpoints, 43 MCP tools.
- **README**: Functional but dry. ASCII architecture diagram, quickstart section, feature summary table, tech stack table, project structure tree. No hero image, no screenshots, no badges, no GIF demo. License line reads "Private project. All rights reserved." -- a critical blocker for any public adoption.
- **Docs**: Well-organized under `docs/` with `guides/`, `reference/`, `runbooks/`, `reports/`, `sessions/` subdirectories. 28 reference docs covering every subsystem. No docs site (MkDocs, Sphinx, or equivalent).
- **CI**: GitHub Actions workflow at `.github/workflows/ci.yml` (lint + test matrix on 3.12/3.13), plus release and deploy workflows. No CI badge in README.
- **Missing**: LICENSE file, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md (at root), hero image/banner, screenshots, demo GIF/video, social preview image.

#### Role in Ecosystem

The flagship product. Every other repo exists to serve, extend, or run alongside this one. Houses the AI operations runtime spanning Layers 2 through 5 of the architecture stack. This is what people install, this is what gets stars, this is what the brand lives or dies on.

#### Rename Recommendation

**Keep `claude-superpowers` as the GitHub repo slug.** Do not rename.

Rationale: The name has SEO value for anyone searching "claude code" + "automation" / "superpowers" / "skills." Renaming to `nexus` or `nexus-core` would lose that discoverability and compete with dozens of existing "nexus" repos. Instead, brand it as "Nexus Core" in the README, description, and documentation, while keeping the URL stable. The repo description and README header do the positioning work; the URL just needs to be memorable and searchable.

#### Positioning Rewrite

**GitHub repo description (160 chars max):**
```
Nexus Core — self-hosted AI operations platform. Skills, cron, messaging, SSH fabric, browser automation, workflows, encrypted vault. 982 tests.
```

#### README Intro Rewrite

```markdown
<p align="center">
  <img src="assets/nexus-banner.svg" alt="Nexus Core" width="100%" />
</p>

<h1 align="center">Nexus Core</h1>
<p align="center">
  <strong>Self-hosted AI operations platform for Claude Code</strong><br>
  Your infrastructure, your AI, your rules.
</p>

<p align="center">
  <a href="https://github.com/smartmur/claude-superpowers/actions"><img src="https://github.com/smartmur/claude-superpowers/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-22c55e.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Tests-982-22c55e" alt="982 tests">
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/Skills-14-0ea5e9" alt="14 skills">
  <img src="https://img.shields.io/badge/MCP_Tools-43-8B5CF6" alt="43 MCP tools">
</p>

---

Nexus Core turns Claude Code into an autonomous operations platform. Schedule cron
jobs that SSH into your servers, screenshot web dashboards via Playwright, diagnose
issues with AI, and send alerts to Telegram — all defined in a single YAML workflow,
all running on your own hardware.

**What it does**: encrypted vault, pluggable skills (14 built-in), APScheduler cron
engine, multi-channel messaging (Slack/Telegram/Discord/email), SSH fabric with
connection pooling, Playwright browser automation, YAML workflow engine with approval
gates, persistent memory store, file watchers, FastAPI dashboard (70 endpoints),
43 MCP tools for Claude Code, and an intake pipeline that decomposes natural language
requests into parallel skill executions.

**What it does not do**: phone home, require cloud services, or lock you into a
single LLM provider.
```

#### Badges

| Badge | Purpose | Priority |
|-------|---------|----------|
| CI status | Trust signal: tests pass on every commit | P0 |
| License (MIT) | Adoption signal: people can use and fork freely | P0 |
| Test count (982) | Quality signal: unusually high for this category | P0 |
| Python version | Compatibility signal | P0 |
| Skills count (14) | Feature depth | P1 |
| MCP tools count (43) | Claude Code integration depth | P1 |
| Docker | Deployment option | P1 |
| Code style (ruff) | Contributor signal | P2 |

#### Folder Restructuring

| Change | Rationale | Priority |
|--------|-----------|----------|
| Add `LICENSE` (MIT) at repo root | **Blocker for public launch.** Without a license, the repo is legally proprietary. | P0 |
| Add `CONTRIBUTING.md` at repo root | Required for contributor onboarding. Reference the test suite, ruff linting, PR process. | P0 |
| Add `SECURITY.md` at repo root | GitHub surfaces this as a security policy. Reference vault, sandboxing, responsible disclosure. | P0 |
| Add `CODE_OF_CONDUCT.md` at repo root | Standard for any public OSS project. Use Contributor Covenant. | P1 |
| Create `assets/` directory | Hero banner SVG, screenshots, demo GIF, architecture diagram PNG, social preview image (1280x640). | P0 |
| Move `to-do.md` to `.github/` or remove from public | Personal work queue should not be in the public root. Use GitHub Issues/Projects instead. | P0 |
| Rename `deploy/` to `contrib/systemd/` | Clarifies that these are contributed deployment configs, not the primary deployment path. | P2 |
| Add `examples/workflows/` | Sample workflows that demonstrate the 10-step compound integration (the moat story). | P1 |
| Add `.github/ISSUE_TEMPLATE/` | Bug report and feature request templates. | P1 |
| Add `.github/PULL_REQUEST_TEMPLATE.md` | PR template with checklist (tests pass, docs updated, etc.). | P1 |
| Add `.github/FUNDING.yml` | GitHub Sponsors / funding links if applicable. | P2 |

#### Documentation Improvements

| Doc | Status | Action | Priority |
|-----|--------|--------|----------|
| Quickstart / getting-started guide | Exists at `docs/guides/getting-started.md` | Promote to README with clear 5-minute path | P0 |
| Architecture overview | Exists at `docs/reference/architecture.md` | Add rendered diagram (Mermaid or PNG), link from README | P0 |
| API reference | Partially covered by subsystem docs | Generate OpenAPI spec from FastAPI, host as HTML | P2 |
| MkDocs site | Does not exist | Create `mkdocs.yml`, deploy to GitHub Pages | P1 |
| Changelog | Does not exist | Add `CHANGELOG.md` following Keep a Changelog format | P0 |
| Migration / upgrade guide | Exists at `docs/guides/UPGRADE.md` | Keep, add version-specific sections as releases ship | P1 |

#### Missing Diagrams and Screenshots

| Asset | Description | Priority |
|-------|-------------|----------|
| Hero banner | SVG banner: "Nexus Core" + tagline + abstract circuit/node graphic | P0 |
| Social preview | 1280x640 OG image for GitHub and social sharing | P0 |
| Dashboard screenshot | Full-page screenshot of the dashboard with real data | P0 |
| Terminal demo GIF | Recording of `claw status`, `claw skill run heartbeat`, `claw cron list` | P0 |
| Architecture diagram (rendered) | Mermaid or PNG version of the ASCII diagram, with color coding by layer | P1 |
| Workflow execution diagram | Visual showing the 10-step compound workflow from the competitive analysis | P1 |
| Telegram bot screenshot | Conversation showing AI response + skill execution result | P1 |
| Skill creation GIF | `claw skill create` scaffolding a new skill in real-time | P2 |

#### Action Priority

- **P0 (pre-launch)**: LICENSE, CONTRIBUTING.md, SECURITY.md, hero banner, social preview, dashboard screenshot, terminal GIF, README rewrite with Nexus branding, CI badge, CHANGELOG.md, remove "Private project" license line, move to-do.md out of root
- **P1 (launch week)**: MkDocs site, CODE_OF_CONDUCT, issue/PR templates, example workflows, architecture PNG, Telegram screenshot, skill/MCP count badges
- **P2 (month 1)**: OpenAPI docs, systemd contrib rename, FUNDING.yml, skill creation GIF, code style badge
- **P3 (quarter 1)**: Interactive docs, video tutorials, translated READMEs

---

### 1.2 k3s-cluster / Nexus Cluster

#### Current State

- **Structure**: Well-organized IaC repo with `ansible/`, `terraform/`, `manifests/`, `scripts/`, `docs/`. Has Makefile for common ops. 15+ doc files covering operations, security, monitoring.
- **README**: Already has badges (Platform, IaC, Security, pre-commit, License). Clean intro paragraph. Links to 8 docs. Architecture section present. No hero image.
- **Docs**: `docs/` contains 10 operational guides (BEGINNER_JOURNEY, GETTING_STARTED, OPERATIONS_AUDIT, SECURITY_RULEBOOK, etc.). Has CONTRIBUTING.md, SECURITY.md, SUPPORT.md, CHANGELOG.md, STACK.md.
- **License**: MIT (SmartMur, 2026).
- **Missing**: Hero banner, screenshots of Headlamp/cluster dashboard, no reference to Nexus ecosystem, no cross-links to claude-superpowers.

#### Role in Ecosystem

Layer 0 infrastructure. Nexus Core's SSH fabric and workflow engine manage this cluster. The cluster runs workloads Nexus schedules. This is the Kubernetes substrate for the platform's optional K8s deployment mode.

#### Rename Recommendation

**Keep `k3s-cluster` as the GitHub repo slug.**

Rationale: "k3s-cluster" is a highly searched term. People looking for k3s reference architectures will find this. Adding "nexus" to the URL would kill that organic discoverability. Brand it as "Nexus Cluster" in the README header and description only.

#### Positioning Rewrite

**GitHub repo description:**
```
Nexus Cluster — production-ready k3s on Proxmox. Terraform provisioning, Ansible bootstrap, Traefik ingress, TrueNAS storage, security-first manifests.
```

#### README Intro Rewrite

```markdown
<p align="center">
  <img src="assets/nexus-cluster-banner.svg" alt="Nexus Cluster" width="100%" />
</p>

# Nexus Cluster — k3s on Proxmox

Production-oriented automation for provisioning and operating a multi-node k3s
cluster across Proxmox hosts, with TrueNAS-backed persistent storage and Traefik
ingress. Designed as the Kubernetes substrate for the
[Nexus AI Operations Platform](https://github.com/smartmur/claude-superpowers).

Part of the **Nexus Platform** — [smartmur/claude-superpowers](https://github.com/smartmur/claude-superpowers)
```

#### Badges

Existing badges are good. Add:

| Badge | Purpose | Priority |
|-------|---------|----------|
| Nexus Platform | Ecosystem membership signal | P0 |
| Kubernetes version | Compatibility clarity | P1 |
| Terraform version | IaC version pinning | P1 |

#### Folder Restructuring

| Change | Rationale | Priority |
|--------|-----------|----------|
| Add `assets/` with hero banner | Visual consistency across ecosystem | P0 |
| No structural changes needed | Repo is already well-organized | -- |

#### Documentation Improvements

| Doc | Action | Priority |
|-----|--------|----------|
| Add "Part of Nexus Platform" section | Cross-link to core repo, explain the relationship | P0 |
| Add Headlamp dashboard screenshot | Show the management UI | P1 |
| Add cluster topology diagram | Mermaid diagram showing nodes, networking, storage | P1 |

#### Missing Diagrams and Screenshots

| Asset | Priority |
|-------|----------|
| Hero banner (Nexus Cluster branding) | P0 |
| Cluster topology diagram (Proxmox hosts, K3s nodes, networking) | P1 |
| Headlamp dashboard screenshot | P1 |
| Terraform plan output example | P2 |

#### Action Priority

- **P0**: Hero banner, Nexus Platform badge, cross-link section in README, description update
- **P1**: Screenshots, topology diagram, K8s/Terraform version badges
- **P2**: Video walkthrough of cluster provisioning
- **P3**: Helm chart for deploying Nexus Core onto this cluster

---

### 1.3 homelab / Nexus Infra

#### Current State

- **Structure**: Massive repo with 97 top-level service directories (one per self-hosted app). Each contains a `docker-compose.yml` and optional `.env.example`. Has `scripts/` (8 deployment/security scripts), `docs/` (SECURITY_RULEBOOK), `assets/` (hero banner SVG). Root-level docs: ARCHITECTURE.md (348 lines), BEGINNER-GUIDE.md, CONTRIBUTING.md, SECURITY.md, CHANGELOG.md, DEPLOYMENT.md, MIGRATION-GUIDE.md, QUICK-DEPLOY.md, QUICKSTART.md, HARDWARE-CALCULATOR.md, REFACTORING-SUMMARY.md.
- **README**: Already polished. Has SVG hero banner, 4 badges (Platform, Services 90+, Security First, License MIT, GitHub link). Quick links section. Service catalog. Beginner's journey. One-click deployment scripts.
- **License**: MIT (SmartMur, 2024).
- **Missing**: No reference to Nexus ecosystem, no cross-links to claude-superpowers, several docs overlap (QUICKSTART vs QUICK-DEPLOY vs BEGINNER-GUIDE), no screenshots of running services.

#### Role in Ecosystem

Layer 0 + Layer 1. The physical Docker Compose infrastructure that Nexus Core monitors, manages, and auto-remediates via the infra-fixer skill, container watchdog, and deploy workflow. Houses 90+ service definitions spanning monitoring, security, networking, development, and media.

#### Rename Recommendation

**Keep `homelab` as the GitHub repo slug.**

Rationale: "homelab" is one of the highest-traffic search terms in the self-hosted community. Renaming would be catastrophic for discoverability. The r/homelab subreddit has 1.5M+ subscribers. Brand as "Nexus Infra" only in README header and ecosystem cross-references.

#### Positioning Rewrite

**GitHub repo description:**
```
Nexus Infra — 90+ production-grade, security-hardened Docker Compose stacks for self-hosted services. Monitoring, networking, security, dev tools. One-click deploy.
```

#### README Intro Rewrite

Keep the existing hero banner and badge structure (it is already well-done). Add ecosystem context:

```markdown
> Part of the **Nexus Platform** — managed and monitored by
> [Nexus Core](https://github.com/smartmur/claude-superpowers).
> Nexus Core's container watchdog, infra-fixer skill, and deploy workflow
> orchestrate these stacks automatically.
```

Insert this block immediately after the existing badge row.

#### Badges

Existing badges are strong. Add:

| Badge | Purpose | Priority |
|-------|---------|----------|
| Nexus Platform | Ecosystem membership | P0 |
| Docker Compose | Deployment method clarity | P1 |

#### Folder Restructuring

| Change | Rationale | Priority |
|--------|-----------|----------|
| Consolidate QUICKSTART.md + QUICK-DEPLOY.md + BEGINNER-GUIDE.md | Three overlapping "getting started" docs create confusion. Merge into a single `docs/GETTING_STARTED.md` with sections for beginners, quick deploy, and advanced. Keep the most comprehensive content. | P1 |
| Move `projects/home_media/` to a top-level pointer or remove | `home_media` is a separate repo. Having a nested copy/reference creates confusion about the canonical location. Replace with a symlink doc or cross-reference. | P1 |
| Add `stacks/` category subdirectories | Consider grouping the 97 service directories into categories: `monitoring/`, `security/`, `networking/`, `media/`, `development/`, `productivity/`. This makes the repo browsable instead of overwhelming. | P2 |
| Add `examples/.env.complete` | A single annotated example showing all possible env vars across all stacks. Helps new users understand the full configuration surface. | P2 |

#### Documentation Improvements

| Doc | Action | Priority |
|-----|--------|----------|
| Add "Part of Nexus Platform" section | Cross-link to core repo | P0 |
| Add "Managed by Nexus Core" section | Explain how infra-fixer and container watchdog interact with these stacks | P1 |
| Consolidate getting-started docs (3 overlapping files) | Merge into single flow with beginner/intermediate/advanced paths | P1 |
| Add per-service screenshots | Top 10 most popular services should have a screenshot in their directory | P2 |

#### Missing Diagrams and Screenshots

| Asset | Priority |
|-------|----------|
| Network topology diagram (VLANs, hosts, services) | P1 |
| Service dependency map (what depends on what) | P1 |
| Grafana dashboard screenshot | P1 |
| Portainer/Dockhand screenshot | P2 |
| Per-service screenshots (Grafana, Authentik, Homepage, Immich) | P2 |

#### Action Priority

- **P0**: Nexus Platform badge and cross-link, description update
- **P1**: Doc consolidation, service screenshots, dependency diagram, "Managed by Nexus" section
- **P2**: Category subdirectories, complete .env example, individual service screenshots
- **P3**: Auto-generated service catalog from docker-compose files, interactive docs site

---

### 1.4 home_media / Nexus Media

#### Current State

- **Structure**: 4 service subdirectories (`dockhand/`, `ent/`, `tails/`, `termix/`), plus root-level docs (README, DEPLOYMENT, COMMANDS, QUICKREF, SECURITY, SETUP, INDEX, CHECKLIST) and a health check script. Has `.env.example` and `.github/` with workflows.
- **README**: Functional but unstyled. Plain markdown header, service list, quick start section. No badges, no hero banner, no screenshots. Links to 5 documentation files.
- **License**: **MISSING.** No LICENSE file. This must be fixed before public launch.
- **Docs**: Heavy on procedural docs (7 files), light on architecture. INDEX.md provides good navigation. SECURITY.md covers Tailscale-only access. Several GitHub-meta docs (GITHUB_PUSH_CHECKLIST, GITHUB_READY, GITHUB_SETUP) that are internal process docs, not user-facing.
- **Missing**: LICENSE, hero banner, badges, screenshots, CONTRIBUTING.md, no reference to Nexus ecosystem.

#### Role in Ecosystem

Layer 0 specialized. The media automation stack (Radarr, Sonarr, Prowlarr, qBittorrent, Jellyfin, Plex, etc.) running as Docker Compose. Nexus Core monitors these containers via infra-fixer and triggers actions via file watchers (new downloads). Operationally distinct from the general infrastructure repo because media has its own acquisition/transcoding/streaming domain.

#### Rename Recommendation

**Rename to `nexus-media`.**

Rationale: Unlike `homelab` and `k3s-cluster`, "home_media" is not a high-value search term. The underscore in the name is also non-standard for GitHub repos (hyphens are the convention). Renaming to `nexus-media` improves branding consistency and loses no discoverability. GitHub will auto-redirect the old URL.

#### Positioning Rewrite

**GitHub repo description:**
```
Nexus Media — self-hosted media platform. Automated acquisition (*arr suite), transcoding, streaming (Jellyfin/Plex), and secure remote access via Tailscale.
```

#### README Intro Rewrite

```markdown
<p align="center">
  <img src="assets/nexus-media-banner.svg" alt="Nexus Media" width="100%" />
</p>

# Nexus Media

Self-hosted media platform with automated acquisition, transcoding, and streaming.
Deploy Radarr, Sonarr, Prowlarr, qBittorrent, Jellyfin, and Plex as a single
Docker Compose stack with Tailscale-secured remote access.

Part of the **Nexus Platform** — monitored and managed by
[Nexus Core](https://github.com/smartmur/claude-superpowers).

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Docker%20Compose-0ea5e9)](#)
[![Nexus](https://img.shields.io/badge/Nexus-Media-8B5CF6)](#)
```

#### Badges

| Badge | Purpose | Priority |
|-------|---------|----------|
| License (MIT) | **Must add LICENSE file first** | P0 |
| Platform (Docker Compose) | Deployment clarity | P0 |
| Nexus Platform | Ecosystem membership | P0 |
| Services count | Feature depth | P1 |

#### Folder Restructuring

| Change | Rationale | Priority |
|--------|-----------|----------|
| Add `LICENSE` (MIT) | **Critical blocker.** No license = legally proprietary. | P0 |
| Remove `GITHUB_PUSH_CHECKLIST.md`, `GITHUB_READY.md`, `GITHUB_SETUP.md` | Internal process docs that should not be in the public repo. Move to a local notes directory or delete. | P0 |
| Remove `DOCUMENTATION_SUMMARY.txt` | Auto-generated meta-doc. Not user-facing. | P0 |
| Add `assets/` with hero banner | Visual consistency | P0 |
| Add `CONTRIBUTING.md` | Contributor onboarding | P1 |
| Rename service dirs to lowercase with hyphens | `ent/`, `tails/`, `termix/` are unclear names. Add README.md to each explaining what they are. | P1 |
| Add `docker-compose.yml` at root | If not present, add a unified compose file or a `compose/` directory that ties all services together. | P1 |

#### Documentation Improvements

| Doc | Action | Priority |
|-----|--------|----------|
| Add LICENSE (MIT) | Legal requirement for public repo | P0 |
| Remove internal GitHub-meta docs (3 files) | Not user-facing | P0 |
| Add "Part of Nexus Platform" section | Cross-link to core repo | P0 |
| Add CONTRIBUTING.md | Standard OSS file | P1 |
| Consolidate DEPLOYMENT + SETUP | Overlap between these two docs | P1 |

#### Missing Diagrams and Screenshots

| Asset | Priority |
|-------|----------|
| Hero banner | P0 |
| Jellyfin/Plex UI screenshot | P1 |
| Service architecture diagram (how services connect) | P1 |
| Jellyseerr request flow screenshot | P2 |

#### Action Priority

- **P0**: LICENSE file, rename to `nexus-media`, remove internal docs, hero banner, Nexus cross-link, description update
- **P1**: CONTRIBUTING.md, service screenshots, architecture diagram, doc consolidation
- **P2**: Service directory READMEs, health check improvements
- **P3**: Auto-generated service status page

---

### 1.5 dotfiles / Nexus Bootstrap

#### Current State

- **Structure**: Well-organized with `assets/` (hero banner, favicon, terminal preview SVG), `config/`, `docs/`, `scripts/`, `zsh/`. Has `bootstrap.sh` and `install.sh` entry points. Makefile for common ops. Pre-commit config.
- **README**: Polished. Hero banner (favicon + SVG), 5 badges (macOS, Shell, License, GitHub, pre-commit), terminal preview image. Clean overview, installation section, links to 6 docs.
- **Docs**: CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, ROADMAP.md, SUPPORT.md, CHANGELOG.md, `docs/GETTING_STARTED.md`, `docs/SECURITY_RULEBOOK.md`. This is the most complete doc set of any repo.
- **License**: MIT (SmartMur, 2026).
- **Missing**: No reference to Nexus ecosystem, macOS-only (no Linux support), no cross-links.

#### Role in Ecosystem

The bootstrapping layer. Before any Nexus component runs, the operator's development environment needs to be provisioned: shell, Git, SSH, editor, security tooling. This repo handles that. Includes the `security_scrub.py` tool that other repos depend on for credential scanning.

#### Rename Recommendation

**Keep `dotfiles` as the GitHub repo slug.**

Rationale: "dotfiles" is a well-established GitHub convention. Developers search for "dotfiles" when looking for shell configurations. The repo already has good README branding. Brand as "Nexus Bootstrap" only in ecosystem cross-references.

#### Positioning Rewrite

**GitHub repo description:**
```
Nexus Bootstrap — reproducible macOS terminal environment. Zsh, Homebrew, iTerm2, SSH hardening, security tooling, pre-commit hooks. One-command setup.
```

#### README Intro Rewrite

Keep the existing hero banner and badges (they are already polished). Add:

```markdown
> Part of the **Nexus Platform** — the first step in provisioning a
> [Nexus](https://github.com/smartmur/claude-superpowers) operator environment.
> Sets up shell, Git, SSH keys, security tooling, and development tools
> before installing Nexus Core.
```

#### Badges

Existing badges are complete. Add:

| Badge | Purpose | Priority |
|-------|---------|----------|
| Nexus Platform | Ecosystem membership | P0 |

#### Folder Restructuring

No changes needed. This repo is the best-organized in the ecosystem.

#### Documentation Improvements

| Doc | Action | Priority |
|-----|--------|----------|
| Add "Part of Nexus Platform" section | Cross-link to core repo | P0 |
| Add Linux support section | Currently macOS-only. At minimum document what works on Linux. | P1 |
| Add "What gets installed" summary table | Quick visibility into what the bootstrap touches | P1 |

#### Missing Diagrams and Screenshots

| Asset | Priority |
|-------|----------|
| Real terminal screenshot (not SVG placeholder) | P1 |
| Before/after comparison | P2 |

#### Action Priority

- **P0**: Nexus Platform cross-link, description update
- **P1**: Linux support docs, installation summary table, real terminal screenshot
- **P2**: Before/after comparison, iTerm2 theme showcase
- **P3**: Automated testing of bootstrap on fresh macOS VM

---

### 1.6 claude-code-tresor / Nexus Vault Agent

#### Current State

- **Structure**: Large collection of Claude Code extensions: `agents/` (subagents), `commands/` (slash commands), `skills/`, `subagents/`, `prompts/`, `validation/`, `examples/`, `scripts/`, `standards/`, `documentation/`, `docs/`. Has `commitlint.config.js`, multiple release notes files, and extensive documentation.
- **README**: Well-branded with emoji-heavy formatting. MIT license badge, version badge (v2.7.0), quality score badge (9.7/10), Claude Code compatible badge. Author attribution to Alireza Rezvani (upstream). Detailed feature list and changelog. Smithery integration.
- **License**: MIT (Alireza Rezvani / CasJam Media, 2025). This is a **fork** -- the license belongs to the upstream author.
- **Upstream**: `alirezarezvani/claude-code-tresor`.
- **Missing**: No Nexus ecosystem reference, no documentation of SmartMur-specific changes vs upstream, no rebase/sync strategy documented.

#### Role in Ecosystem

Layer 5 extension. Provides agent orchestration patterns, slash commands, and skill templates that inform and extend Nexus Core's intake pipeline, skill system, and multi-agent dispatch. Serves as both an upstream contribution channel and a distribution platform for Nexus skills.

#### Rename Recommendation

**Keep `claude-code-tresor` as the GitHub repo slug.**

Rationale: As a fork, the name should match upstream for clarity. Renaming a fork signals a hard divergence that discourages upstream contribution. Brand as "Nexus Vault Agent" only in ecosystem docs.

#### Positioning Rewrite

**GitHub repo description:**
```
Fork of claude-code-tresor — Claude Code skills, agents, and commands. Extended with Nexus Platform integration, security hardening, and homelab operations skills.
```

#### README Intro Rewrite

Do not rewrite the upstream README. Instead, add a clearly demarcated section at the top:

```markdown
> **Nexus Platform Fork** — This is a maintained fork of
> [alirezarezvani/claude-code-tresor](https://github.com/alirezarezvani/claude-code-tresor)
> with security hardening and Nexus Platform integration.
> See [NEXUS-CHANGES.md](NEXUS-CHANGES.md) for what we changed and why.
```

#### Badges

Add to existing badge row:

| Badge | Purpose | Priority |
|-------|---------|----------|
| Nexus Platform Extension | Fork relationship clarity | P0 |
| Upstream sync status | Shows how current the fork is vs upstream | P1 |

#### Folder Restructuring

| Change | Rationale | Priority |
|--------|-----------|----------|
| Add `NEXUS-CHANGES.md` | Document every change made from upstream: security fixes, added skills, config changes. Critical for fork maintenance and credibility. | P0 |
| Add `UPSTREAM.md` | Document rebase/sync strategy, upstream version tracking, contribution-back policy. | P1 |

#### Documentation Improvements

| Doc | Action | Priority |
|-----|--------|----------|
| Create NEXUS-CHANGES.md | Diff summary vs upstream | P0 |
| Create UPSTREAM.md | Sync strategy, how to rebase | P1 |
| Document which skills are Nexus-specific vs upstream | Clarity for users | P1 |

#### Missing Diagrams and Screenshots

None urgently needed. The upstream project handles its own visual branding.

#### Action Priority

- **P0**: Nexus fork banner, NEXUS-CHANGES.md, description update
- **P1**: UPSTREAM.md, skill origin documentation
- **P2**: Contribute security fixes back upstream
- **P3**: Publish Nexus-specific skills as standalone packages

---

### 1.7 claude-code-skill-factory / Nexus Skill Factory

#### Current State

- **Structure**: Skill/agent generation toolkit with `generated-skills/`, `generated-agents/`, `generated-commands/`, `generated-hooks/`, `generated-prompts/`, `claude-skills-examples/`, `documentation/`. Has `CLAUDE.md` for Claude Code context.
- **README**: Functional but emoji-heavy. Three "quick start" paths (interactive builder, slash commands, ready-made skills). Feature list organized by generators (skills, agents, prompts, hooks, commands).
- **License**: MIT (Reza Rezvani / CasJam Media, 2025). **Fork** -- license belongs to upstream.
- **Upstream**: Different author from tresor but same organization (CasJam Media / Builder Methods).
- **Missing**: No Nexus ecosystem reference, no fork-specific documentation, no integration guide for Nexus Core's skill system.

#### Role in Ecosystem

Layer 3 extension. A skill creation factory that can generate skills, agents, and commands compatible with Nexus Core's skill registry and SkillHub. The generated artifacts feed directly into `claw skill sync` and the skills directory.

#### Rename Recommendation

**Keep `claude-code-skill-factory` as the GitHub repo slug.**

Rationale: Same as tresor -- fork naming should match upstream for clarity.

#### Positioning Rewrite

**GitHub repo description:**
```
Fork of claude-code-skill-factory — skill, agent, and prompt generators for Claude Code. Configured for Nexus Platform skill registry integration.
```

#### README Intro Rewrite

Add a Nexus context block at the top:

```markdown
> **Nexus Platform Fork** — This fork is configured for
> [Nexus Core](https://github.com/smartmur/claude-superpowers) skill registry
> integration. Generated skills are compatible with `claw skill sync` and
> the Nexus SkillHub. See [NEXUS-CHANGES.md](NEXUS-CHANGES.md) for modifications.
```

#### Badges

| Badge | Purpose | Priority |
|-------|---------|----------|
| Nexus Platform Extension | Fork clarity | P0 |

#### Folder Restructuring

| Change | Rationale | Priority |
|--------|-----------|----------|
| Add `NEXUS-CHANGES.md` | Document modifications from upstream | P0 |
| Add integration examples | Show how generated skills work with `claw skill sync` | P1 |

#### Documentation Improvements

| Doc | Action | Priority |
|-----|--------|----------|
| Create NEXUS-CHANGES.md | Fork diff documentation | P0 |
| Add Nexus integration guide | How to use factory output with Nexus Core | P1 |

#### Missing Diagrams and Screenshots

| Asset | Priority |
|-------|----------|
| Workflow diagram: factory -> skill.yaml -> SkillHub -> Nexus Core | P1 |

#### Action Priority

- **P0**: Nexus fork banner, NEXUS-CHANGES.md, description update
- **P1**: Integration guide, workflow diagram
- **P2**: Automate skill.yaml generation for Nexus compatibility
- **P3**: Merge factory capabilities into Nexus Core's skill-create command

---

### 1.8 agent-os / Nexus Agent OS

#### Current State

- **Structure**: Lightweight repo with `commands/agent-os/` (5 slash commands: discover-standards, index-standards, inject-standards, plan-product, shape-spec), `profiles/default/global/` (tech-stack.md), `scripts/common-functions.sh`, `config.yml`.
- **README**: Clean, professional. Hero image (1200x675 OG image). Clear value proposition: "Agents that build the way you would." Links to external docs at buildermethods.com. Concise feature list.
- **License**: MIT (CasJam Media LLC, 2025). **Fork.**
- **Upstream**: Builder Methods / CasJam Media.
- **Missing**: No Nexus ecosystem reference, no documentation of SmartMur-specific changes, small repo with minimal content.

#### Role in Ecosystem

Layer 5 conceptual reference. Provides agent runtime patterns (standards discovery, spec shaping, standard injection) that inform Nexus Core's intake pipeline design and role router. Not deeply integrated -- more of an architectural reference than a production dependency.

#### Rename Recommendation

**Keep `agent-os` as the GitHub repo slug.**

Rationale: Fork naming convention. The repo is small and serves as an evaluation fork. No rename needed.

#### Positioning Rewrite

**GitHub repo description:**
```
Fork of agent-os — standards-driven agent framework. Evaluated for Nexus Platform agent orchestration patterns.
```

#### README Intro Rewrite

Add a minimal Nexus context block:

```markdown
> **Nexus Platform Evaluation Fork** — Patterns from this project inform
> [Nexus Core](https://github.com/smartmur/claude-superpowers)'s intake pipeline
> and role-based agent dispatch. See the Nexus
> [architecture docs](https://github.com/smartmur/claude-superpowers/blob/main/docs/reference/architecture.md)
> for how these concepts are implemented in production.
```

#### Badges

| Badge | Purpose | Priority |
|-------|---------|----------|
| Nexus Platform Extension | Ecosystem membership | P1 |

#### Folder Restructuring

No changes needed. Repo is small and well-organized.

#### Documentation Improvements

| Doc | Action | Priority |
|-----|--------|----------|
| Add brief NEXUS-CHANGES.md | Even if changes are minimal, document what was done | P1 |

#### Missing Diagrams and Screenshots

None needed for an evaluation fork.

#### Action Priority

- **P0**: Description update
- **P1**: Nexus context block, NEXUS-CHANGES.md
- **P2**: Evaluate whether to archive or maintain
- **P3**: Extract useful patterns into Nexus Core and archive this fork

---

### 1.9 Lighthouse-AI

#### Current State

- **Not cloned locally.** Based on Phase 1 analysis: a fork of an AI-powered code analysis tool. Evaluated for integration into Nexus Core's QA Guardian skill. No active integration.
- **License**: Unknown (fork -- check upstream).
- **Missing**: Everything Nexus-related.

#### Role in Ecosystem

Labs tier. Evaluated for QA Guardian integration but not actively used. The QA Guardian skill in Nexus Core was built independently and covers the code quality scanning use case with 12 checks across 4 categories.

#### Rename Recommendation

**Do not rename. Archive.**

Rationale: No active integration with Nexus. The QA Guardian skill in Nexus Core supersedes the need for this fork. Archiving removes maintenance burden and declutters the org profile.

#### Positioning Rewrite

If not archived:
```
[ARCHIVED] Lighthouse-AI — AI-powered code analysis. Evaluated for Nexus QA Guardian. Superseded by native implementation.
```

#### Action Priority

- **P0**: Archive the repo (GitHub Settings > Archive). Add `[ARCHIVED]` prefix to description.
- No further action needed.

---

### 1.10 Smoke

#### Current State

- **Not cloned locally.** Based on Phase 1 analysis: a fork of a testing framework. Evaluated for use in Nexus Core's CI pipeline. No active integration.
- **License**: Unknown (fork -- check upstream).
- **Missing**: Everything Nexus-related.

#### Role in Ecosystem

Labs tier. Evaluated but not integrated. Nexus Core uses pytest (982 tests) with ruff linting. No need for an additional testing framework.

#### Rename Recommendation

**Do not rename. Archive.**

Rationale: Same as Lighthouse-AI. No integration, no active maintenance, clutters the org profile. The 982-test pytest suite in Nexus Core is the testing story.

#### Positioning Rewrite

If not archived:
```
[ARCHIVED] Smoke — testing framework. Evaluated for Nexus CI pipeline. Using pytest instead.
```

#### Action Priority

- **P0**: Archive the repo. Add `[ARCHIVED]` prefix to description.
- No further action needed.

---

### 1.11 design-os

#### Current State

- **Cloned locally.** A React/Vite/TypeScript design system tool. Full web application with `src/`, `public/`, Vite config, ESLint config, component definitions. Has `agents.md` and `claude.md` for AI-assisted development. Nice OG hero image (1280x640).
- **License**: MIT (CasJam Media LLC, 2025). Fork of Builder Methods project.
- **README**: Well-written. Clear problem statement, process description, external docs link.

#### Role in Ecosystem

**None.** This is a product design tool for building UI specs. It has zero integration with any Nexus component. It was forked for evaluation and has no connection to AI operations, infrastructure management, or any Nexus use case.

#### Rename Recommendation

**Archive immediately.**

Rationale: No ecosystem role. No integration path. Clutters the org. Every unrelated fork on the org page dilutes the Nexus brand and confuses visitors about what SmartMur builds.

#### Action Priority

- **P0**: Archive the repo. Add `[ARCHIVED]` prefix to description.
- No further action needed.

---

## 2. Merge and Archive Decisions

### Archive (3 repos)

| Repo | Action | Rationale |
|------|--------|-----------|
| `Lighthouse-AI` | **Archive** | Superseded by QA Guardian in Nexus Core. No integration. |
| `Smoke` | **Archive** | Superseded by pytest suite (982 tests). No integration. |
| `design-os` | **Archive** | Zero ecosystem relevance. Product design tool, not AI ops. |

Archiving removes these from active org browsing while preserving history. GitHub shows archived repos grayed out and at the bottom of the repo list. This immediately makes the org page cleaner and more focused.

### Merge Candidates (0 repos)

No merges recommended at this time. Each remaining repo serves a distinct purpose:

- `claude-superpowers` = platform runtime (cannot merge infra configs into it)
- `k3s-cluster` = Kubernetes IaC (operationally distinct from Docker Compose stacks)
- `homelab` = Docker Compose service definitions (too large and domain-specific for Core)
- `home_media` = Media stack (distinct operational domain)
- `dotfiles` = Environment bootstrap (pre-Core, different lifecycle)
- `claude-code-tresor` = Fork (must stay separate for upstream tracking)
- `claude-code-skill-factory` = Fork (must stay separate for upstream tracking)
- `agent-os` = Fork (must stay separate for upstream tracking)

The `home_media` repo could theoretically merge into `homelab` as a subdirectory, but keeping it separate is justified because:
1. Media has a distinct user persona (media enthusiast vs infrastructure operator)
2. Different release cadence (media services update frequently, infra less so)
3. Security boundary (media acquisition has different trust requirements than core infra)
4. The `homelab` repo already has a `projects/home_media/` reference, suggesting awareness of the relationship

### Future Merge Consideration

| Scenario | Timeline | Condition |
|----------|----------|-----------|
| Merge `agent-os` into `claude-superpowers` | Q2 2026 | If useful patterns are fully absorbed into intake pipeline |
| Merge `claude-code-skill-factory` into `claude-superpowers` | Q3 2026 | If `claw skill create` fully subsumes factory capabilities |
| Deprecate `claude-code-tresor` fork | Q4 2026 | If all useful skills are extracted and published natively |

---

## 3. Cross-Linking Strategy

### Principle: Every repo links back to Core, Core links to every repo.

The cross-linking strategy creates an internal network that (a) helps users navigate the ecosystem, (b) signals to GitHub's recommendation engine that these repos are related, and (c) establishes Nexus Core as the authoritative center.

### Standard "Part of Nexus" Section

Every non-Core repo must include this section (adapted per repo):

```markdown
---

## Part of the Nexus Platform

This repository is part of the **Nexus — Sovereign AI Operations Platform**.

| Repo | Role |
|------|------|
| [**Nexus Core**](https://github.com/smartmur/claude-superpowers) | AI operations runtime: skills, cron, messaging, SSH, browser, workflows, vault |
| [**Nexus Cluster**](https://github.com/smartmur/k3s-cluster) | K3s on Proxmox: Terraform + Ansible + GitOps |
| [**Nexus Infra**](https://github.com/smartmur/homelab) | 90+ Docker Compose stacks for self-hosted services |
| [**Nexus Media**](https://github.com/smartmur/nexus-media) | Media platform: *arr suite + Jellyfin/Plex |
| [**Nexus Bootstrap**](https://github.com/smartmur/dotfiles) | Developer environment provisioning |

> Your infrastructure, your AI, your rules.
```

### Core README Ecosystem Section

`claude-superpowers` README must include a full ecosystem map:

```markdown
## The Nexus Ecosystem

Nexus Core is the brain of a larger platform:

| Layer | Repo | Description |
|-------|------|-------------|
| **Core** | You are here | AI operations runtime |
| **Kubernetes** | [k3s-cluster](https://github.com/smartmur/k3s-cluster) | K3s reference architecture on Proxmox |
| **Infrastructure** | [homelab](https://github.com/smartmur/homelab) | 90+ Docker Compose service stacks |
| **Media** | [nexus-media](https://github.com/smartmur/nexus-media) | Self-hosted media platform |
| **Bootstrap** | [dotfiles](https://github.com/smartmur/dotfiles) | Operator environment setup |
| **Extensions** | [claude-code-tresor](https://github.com/smartmur/claude-code-tresor) | Claude Code skill collection (fork) |
| **Extensions** | [claude-code-skill-factory](https://github.com/smartmur/claude-code-skill-factory) | Skill generator (fork) |
```

### Fork Cross-Links

Each fork repo should link to:
1. Upstream repo (attribution)
2. Nexus Core (ecosystem context)
3. Specific Nexus Core module it extends (e.g., skill registry, intake pipeline)

### Linking Rules

1. **Every README links to Nexus Core** -- no exceptions.
2. **Nexus Core links to every active (non-archived) repo** in an ecosystem table.
3. **Module repos link to adjacent modules** they interact with (e.g., homelab links to k3s-cluster because they share the same hosts).
4. **Fork repos link to upstream** for attribution and to Nexus Core for context.
5. **No dead links.** Validate all cross-repo links before launch. Use the renamed URL for home_media after rename.

---

## 4. Topic Tags

### Tag Strategy

GitHub topics drive discoverability. Each repo gets:
- **2-3 ecosystem tags** (consistent across all repos)
- **3-5 technology tags** (repo-specific)
- **1-2 category tags** (what kind of repo this is)

### Per-Repo Tags

| Repo | Tags |
|------|------|
| `claude-superpowers` | `nexus-platform`, `self-hosted`, `ai-ops`, `claude-code`, `automation`, `homelab`, `devops`, `python`, `fastapi`, `mcp`, `sovereign-ai`, `skills`, `workflow-engine`, `ssh`, `browser-automation` |
| `k3s-cluster` | `nexus-platform`, `self-hosted`, `k3s`, `kubernetes`, `proxmox`, `terraform`, `ansible`, `homelab`, `infrastructure-as-code`, `gitops` |
| `homelab` | `nexus-platform`, `self-hosted`, `docker-compose`, `homelab`, `self-hosting`, `docker`, `monitoring`, `grafana`, `security`, `reverse-proxy` |
| `nexus-media` (renamed) | `nexus-platform`, `self-hosted`, `media-server`, `plex`, `jellyfin`, `sonarr`, `radarr`, `docker-compose`, `homelab` |
| `dotfiles` | `nexus-platform`, `dotfiles`, `macos`, `zsh`, `terminal`, `shell`, `homebrew`, `iterm2`, `developer-tools` |
| `claude-code-tresor` | `nexus-platform`, `claude-code`, `ai-agents`, `skills`, `slash-commands`, `automation`, `developer-tools` |
| `claude-code-skill-factory` | `nexus-platform`, `claude-code`, `skill-generator`, `ai-agents`, `code-generation`, `developer-tools` |
| `agent-os` | `nexus-platform`, `ai-agents`, `standards`, `developer-tools`, `claude-code` |

### Mandatory Tags (all repos)

- `nexus-platform` -- ecosystem identifier, unique to SmartMur
- `self-hosted` -- primary discovery category (high-traffic GitHub topic)

---

## 5. Pinned Repos

GitHub allows 6 pinned repos on an organization profile. These are the first things visitors see.

### Recommended Pin Order

| # | Repo | Rationale |
|---|------|-----------|
| 1 | `claude-superpowers` | The flagship. The product. Must be first. |
| 2 | `homelab` | Most broadly appealing. 90+ services attract the self-hosted crowd. Already has the best README of any repo in the org. |
| 3 | `k3s-cluster` | Strong search term. K3s + Proxmox is a popular combo. Reference architecture appeal. |
| 4 | `nexus-media` (renamed) | Media servers are one of the top reasons people build homelabs. Mass appeal. |
| 5 | `dotfiles` | Well-polished, broadly useful beyond the Nexus ecosystem. Attracts a different audience (developers, not just homelab operators). |
| 6 | `claude-code-tresor` | Shows ecosystem breadth. Claude Code users will recognize this. Large upstream community. |

### Why NOT to pin

- `claude-code-skill-factory`: Similar to tresor, lower standalone appeal
- `agent-os`: Small, evaluation-stage, does not showcase the platform well
- Archived repos: Never pin archived repos

---

## 6. Execution Roadmap

### P0 — Pre-Launch Blockers (must complete before any public announcement)

| # | Action | Repo | Effort | Owner |
|---|--------|------|--------|-------|
| 1 | Add MIT LICENSE file | `claude-superpowers` | 5 min | Admin |
| 2 | Add MIT LICENSE file | `home_media` | 5 min | Admin |
| 3 | Remove "Private project. All rights reserved." from README | `claude-superpowers` | 1 min | Admin |
| 4 | Add CONTRIBUTING.md | `claude-superpowers` | 30 min | Dev |
| 5 | Add SECURITY.md (root-level) | `claude-superpowers` | 20 min | Dev |
| 6 | Add CHANGELOG.md | `claude-superpowers` | 30 min | Dev |
| 7 | Create hero banner SVG | `claude-superpowers` | 1 hr | Design |
| 8 | Create social preview image (1280x640) | `claude-superpowers` | 30 min | Design |
| 9 | Rewrite README with Nexus branding | `claude-superpowers` | 2 hr | Dev |
| 10 | Record terminal demo GIF (claw status/skill/cron) | `claude-superpowers` | 30 min | Dev |
| 11 | Take dashboard screenshot | `claude-superpowers` | 10 min | Dev |
| 12 | Move `to-do.md` out of public root | `claude-superpowers` | 5 min | Dev |
| 13 | Remove internal GitHub-meta docs (3 files) | `home_media` | 5 min | Admin |
| 14 | Rename `home_media` to `nexus-media` | GitHub Settings | 5 min | Admin |
| 15 | Archive `Lighthouse-AI` | GitHub Settings | 2 min | Admin |
| 16 | Archive `Smoke` | GitHub Settings | 2 min | Admin |
| 17 | Archive `design-os` | GitHub Settings | 2 min | Admin |
| 18 | Update GitHub org bio to Nexus description | GitHub Settings | 5 min | Admin |
| 19 | Pin 6 repos in recommended order | GitHub Settings | 5 min | Admin |
| 20 | Add GitHub topics to all 7 active repos | GitHub Settings | 20 min | Admin |
| 21 | Update repo descriptions for all 7 active repos | GitHub Settings | 15 min | Admin |

**Total P0 effort**: ~6.5 hours (can be parallelized to ~3 hours)

### P1 — Launch Week (first 7 days after public)

| # | Action | Repo | Effort |
|---|--------|------|--------|
| 1 | Add "Part of Nexus Platform" section to all module READMEs | k3s-cluster, homelab, dotfiles, nexus-media | 2 hr |
| 2 | Add Nexus fork banner to all extension READMEs | tresor, skill-factory, agent-os | 1 hr |
| 3 | Create NEXUS-CHANGES.md for all forks | tresor, skill-factory, agent-os | 2 hr |
| 4 | Add ecosystem table to Nexus Core README | claude-superpowers | 30 min |
| 5 | Create hero banners for module repos | k3s-cluster, nexus-media | 2 hr |
| 6 | Add CODE_OF_CONDUCT.md | claude-superpowers | 15 min |
| 7 | Add `.github/ISSUE_TEMPLATE/` (bug report + feature request) | claude-superpowers | 30 min |
| 8 | Add `.github/PULL_REQUEST_TEMPLATE.md` | claude-superpowers | 15 min |
| 9 | Add CI badge, test badge, license badge to README | claude-superpowers | 15 min |
| 10 | Create MkDocs config and deploy to GitHub Pages | claude-superpowers | 3 hr |
| 11 | Add example workflows demonstrating compound integration | claude-superpowers | 1 hr |
| 12 | Add CONTRIBUTING.md | nexus-media | 30 min |

**Total P1 effort**: ~13 hours

### P2 — Month 1

| # | Action | Repo | Effort |
|---|--------|------|--------|
| 1 | Consolidate overlapping getting-started docs (3 files) | homelab | 2 hr |
| 2 | Take dashboard, Grafana, Telegram bot screenshots | claude-superpowers | 1 hr |
| 3 | Create architecture diagram (Mermaid or PNG) | claude-superpowers | 2 hr |
| 4 | Create cluster topology diagram | k3s-cluster | 1 hr |
| 5 | Create service dependency diagram | homelab | 2 hr |
| 6 | Add per-service screenshots (top 10) | homelab | 3 hr |
| 7 | Add Jellyfin/Plex screenshots | nexus-media | 1 hr |
| 8 | Generate OpenAPI spec and host as HTML | claude-superpowers | 2 hr |
| 9 | Add Linux support documentation | dotfiles | 1 hr |
| 10 | Category subdirectories for 97 service dirs | homelab | 4 hr |
| 11 | Rename `deploy/` to `contrib/systemd/` | claude-superpowers | 15 min |
| 12 | Add `.github/FUNDING.yml` | claude-superpowers | 10 min |
| 13 | Contribute security fixes back upstream | tresor | 2 hr |
| 14 | Add integration examples to skill-factory | skill-factory | 1 hr |
| 15 | Document UPSTREAM.md sync strategy for all forks | tresor, skill-factory, agent-os | 1 hr |

**Total P2 effort**: ~23 hours

### P3 — Quarter 1

| # | Action | Repo | Effort |
|---|--------|------|--------|
| 1 | Record video walkthrough of full platform | claude-superpowers | 4 hr |
| 2 | Record cluster provisioning video | k3s-cluster | 2 hr |
| 3 | Create interactive docs with live examples | claude-superpowers | 8 hr |
| 4 | Auto-generate service catalog from compose files | homelab | 4 hr |
| 5 | Helm chart for deploying Nexus Core to K3s | k3s-cluster + claude-superpowers | 8 hr |
| 6 | Evaluate merging agent-os patterns into Core | claude-superpowers + agent-os | 4 hr |
| 7 | Evaluate absorbing skill-factory into Core | claude-superpowers + skill-factory | 4 hr |
| 8 | Build automated cross-repo link checker CI | claude-superpowers | 2 hr |
| 9 | Add translated README sections (Spanish, Portuguese) | claude-superpowers | 3 hr |
| 10 | Create org-level README.md (GitHub org profile) | SmartMur org | 2 hr |

**Total P3 effort**: ~41 hours

---

## Summary: Post-Reorg Ecosystem State

After completing P0 and P1, the SmartMur GitHub organization will look like this:

### Active Repos (7)

```
PINNED:
  1. claude-superpowers    "Nexus Core — self-hosted AI operations platform..."
  2. homelab               "Nexus Infra — 90+ Docker Compose stacks..."
  3. k3s-cluster           "Nexus Cluster — k3s on Proxmox..."
  4. nexus-media           "Nexus Media — self-hosted media platform..."
  5. dotfiles              "Nexus Bootstrap — reproducible macOS terminal..."
  6. claude-code-tresor    "Fork of claude-code-tresor — extended with Nexus..."

NOT PINNED:
  7. claude-code-skill-factory  "Fork of claude-code-skill-factory — configured for Nexus..."
  8. agent-os                   "Fork of agent-os — evaluated for Nexus agent patterns..."
```

### Archived Repos (3)

```
  9.  Lighthouse-AI    [ARCHIVED] — superseded by QA Guardian
  10. Smoke            [ARCHIVED] — using pytest instead
  11. design-os        [ARCHIVED] — no ecosystem relevance
```

### Visual Consistency

Every active repo will have:
- Nexus Platform badge
- Cross-link to Nexus Core
- "Part of the Nexus Platform" section (or "Nexus Platform Fork" for forks)
- Consistent badge style (green for status, blue for tech, purple for Nexus)
- MIT license
- Professional README with hero banner (Core and modules) or fork banner (extensions)

### Network Effect

With 7 active repos all linking to each other and tagged with `nexus-platform` + `self-hosted`:
- GitHub topic page for `nexus-platform` will show the full ecosystem
- GitHub topic page for `self-hosted` will show 5 repos (Core, Infra, Cluster, Media, Bootstrap)
- Any star on any repo feeds discoverability for the entire ecosystem
- Cross-links create an internal PageRank effect that surfaces related repos in GitHub's "Related repos" sidebar

### Branding Clarity

Visitors will immediately understand:
- **What SmartMur builds**: A sovereign AI operations platform called Nexus
- **What the core product is**: claude-superpowers (Nexus Core)
- **What the supporting repos do**: Infrastructure substrate, media platform, developer bootstrap
- **What the forks are**: Curated extensions, not random bookmarks
- **What is not maintained**: Archived repos, clearly grayed out

---

*Document generated by Claude Code ecosystem analysis.*
*All recommendations based on actual repo contents, current README quality, competitive positioning, and GitHub discoverability patterns.*
*Companion documents: [Phase 1 — Identity](phase1-identity.md), [Phase 2 — Architecture](phase2-architecture.md), [Phase 5 — Star Strategy](phase5-star-strategy.md), [Phase 6 — Competitive Analysis](phase6-competitive.md)*
