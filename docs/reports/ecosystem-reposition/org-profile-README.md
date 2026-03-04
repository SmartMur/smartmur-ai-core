# SmartMur GitHub Organization Profile README

> This README is written for `SmartMur/.github/profile/README.md` — the org-level profile that appears at `github.com/smartmur`. Since we cannot push to the `.github` repo directly from this environment, it is staged here for manual import.

---

```markdown
<!-- ============================================================
     HERO BANNER

     Placeholder: Replace with actual banner URL when available
     Asset: nexus-banner.svg (1200x400, dark theme recommended)

     <p align="center">
       <img src="https://raw.githubusercontent.com/SmartMur/.github/main/assets/nexus-banner.svg" alt="Nexus -- Sovereign AI Operations Platform" width="100%" />
     </p>
     ============================================================ -->

<h1 align="center">Nexus</h1>

<p align="center">
  <strong>Sovereign AI-powered infrastructure automation</strong><br/>
  Your infrastructure, your AI, your rules.
</p>

<p align="center">
  <a href="https://github.com/SmartMur/claude-superpowers"><img src="https://img.shields.io/badge/Nexus_Core-Production-22c55e?style=flat-square" alt="Nexus Core Status" /></a>
  <a href="https://github.com/SmartMur/claude-superpowers"><img src="https://img.shields.io/badge/tests-982_passing-brightgreen?style=flat-square" alt="Test Suite" /></a>
  <a href="https://github.com/SmartMur/claude-superpowers"><img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square" alt="Python Version" /></a>
  <a href="https://github.com/SmartMur/claude-superpowers/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License" /></a>
  <a href="https://github.com/SmartMur/claude-superpowers"><img src="https://img.shields.io/badge/docker--compose-ready-blue?style=flat-square" alt="Docker Support" /></a>
</p>

---

## The Ecosystem

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

### Projects at a Glance

| Tier | Repo | Role | Status |
|------|------|------|--------|
| **Core** | [**Nexus Core**](https://github.com/SmartMur/claude-superpowers) | AI operations runtime: skills, scheduling, messaging, SSH, browser automation, workflows, memory, vault, dashboard | ![tests](https://img.shields.io/badge/982_tests-passing-brightgreen?style=flat-square) |
| **Module** | [**Nexus Infra**](https://github.com/SmartMur/homelab) | 90+ self-hosted service blueprints with security hardening | ![production](https://img.shields.io/badge/production-live-green?style=flat-square) |
| **Module** | [**Nexus Cluster**](https://github.com/SmartMur/k3s-cluster) | Kubernetes reference architecture: Ansible + Terraform + GitOps on Proxmox | ![ready](https://img.shields.io/badge/ready-to_deploy-blue?style=flat-square) |
| **Module** | [**Nexus Media**](https://github.com/SmartMur/home_media) | Media automation stack: acquisition, transcoding, streaming (Plex/Jellyfin + *arr) | ![production](https://img.shields.io/badge/production-live-green?style=flat-square) |
| **Module** | [**Nexus Bootstrap**](https://github.com/SmartMur/dotfiles) | Developer environment bootstrap: shell, Git, SSH, security tooling | ![maintained](https://img.shields.io/badge/maintained-blue?style=flat-square) |
| **Extension** | [claude-code-tresor](https://github.com/SmartMur/claude-code-tresor) | Agent orchestration with secure credential handling | |
| **Extension** | [claude-code-skill-factory](https://github.com/SmartMur/claude-code-skill-factory) | Skill creation framework for Claude Code agents | |
| **Extension** | [agent-os](https://github.com/SmartMur/agent-os) | Agent operating system: runtime, memory, tool access | |

---

## Why Nexus?

### The Problem

Running AI-powered operations on your own hardware today requires stitching together a dozen disconnected tools:

- A cron scheduler here
- An SSH wrapper there
- A messaging bot somewhere else
- Secrets in `.env` files
- No unified memory
- No coordination layer
- Vendor lock-in and telemetry

### The Solution

Nexus integrates **eight subsystems** into one tested, cohesive platform:

| Subsystem | What It Does |
|-----------|-------------|
| **Skill System** | Registry, loader, auto-install, SkillHub sync. 14 built-in skills. Sandboxed execution. |
| **Cron Engine** | APScheduler + SQLite. Four job types: shell, claude, webhook, skill. Cron expressions, intervals, one-time jobs. |
| **Messaging** | Telegram, Slack, Discord, email, iMessage. Notification profiles. Inbound triggers. |
| **SSH Fabric** | Paramiko connection pool. Multi-host execution. Host groups. Home Assistant bridge. |
| **Browser Automation** | Playwright. Persistent sessions. Navigate, screenshot, extract, fill forms. |
| **Workflow Engine** | YAML pipelines. Shell/claude/skill/http/approval-gate steps. Conditions, rollback, notifications. |
| **Memory Store** | SQLite. Categories: fact, preference, project_context, conversation_summary. Auto-context injection. 90-day decay. |
| **Encrypted Vault** | age encryption. Rotation policies. Audit logging. Sandboxed injection into skills. |

### Why This Matters

No single competing project covers all eight. Zapier, n8n, and OpenClaw each handle subsets. But the **compound integration** — where a single workflow chains SSH, Claude reasoning, browser screenshots, memory storage, and messaging — is the point.

Example: A morning infrastructure check that:
1. SSHes into Proxmox and lists VMs
2. Claude analyzes which ones are stuck
3. Screenshots the web dashboard
4. Stores findings in memory
5. Sends Telegram alerts
6. Pauses for human approval
7. Restarts VMs if approved

All in one YAML file. All coordinated. All local.

### Philosophy

We believe infrastructure operators deserve AI tools that:

1. **Run on their hardware** — zero external service dependencies for core functionality
2. **Respect their data** — no telemetry, no cloud lock-in, no "upgrade to Enterprise"
3. **Answer to them alone** — fully transparent, auditable, portable

Every repo in this organization follows three principles:

- **Local-first**: Zero external service dependencies for core functionality.
- **Security-default**: Encrypted vault, pre-commit hooks, secret scrubbing, sandboxed execution.
- **Reference architecture**: Generalizable blueprints you can adopt, not personal configs.

---

## Quick Links

- **[Nexus Core Docs](https://github.com/SmartMur/claude-superpowers/tree/main/docs)** — Architecture, API reference, skill catalog
- **[Contributing Guide](https://github.com/SmartMur/claude-superpowers/blob/main/CONTRIBUTING.md)** — How to contribute skills and workflows
- **[Security Policy](https://github.com/SmartMur/claude-superpowers/blob/main/SECURITY.md)** — Vulnerability disclosure
- **[Discussions](https://github.com/SmartMur/claude-superpowers/discussions)** — Ask questions, share ideas
- **[Issues](https://github.com/SmartMur/claude-superpowers/issues)** — Report bugs, request features

---

## Getting Started

### Install Nexus Core

```bash
git clone https://github.com/SmartMur/claude-superpowers.git
cd claude-superpowers
pip install -e ".[dev]"
claw status
```

### Run the Full Stack

```bash
docker compose up -d
# Starts: Redis, message gateway, dashboard, browser engine, Telegram bot
# Dashboard: http://localhost:8200
# API: http://localhost:8000
```

### Deploy Nexus Modules

Each module is independent and can be deployed separately:

- **Nexus Infra** (homelab): `docker compose up` in the homelab directory
- **Nexus Cluster** (k3s-cluster): `terraform apply` + `ansible-playbook site.yml`
- **Nexus Media** (home_media): `docker compose -f docker-compose.media.yml up`
- **Nexus Bootstrap** (dotfiles): `./install.sh`

See each repo's README for detailed setup.

---

## Manifesto

We are building **sovereignty**, not features.

Your infrastructure should not depend on a company's continued goodwill, a SaaS platform's uptime, or a cloud provider's pricing. It should not phone home. It should not require a subscription tier for basic operations.

Nexus is built for operators who:
- Run Proxmox, Kubernetes, or bare metal
- Use Claude Code and value AI augmentation
- Want to schedule jobs, collect alerts, orchestrate tasks, remember context
- Refuse to let their infrastructure data leave their network
- Expect security and transparency as defaults, not afterthoughts

This is how AI automation should work.

---

<p align="center">
  <sub>Built by operators, for operators. Sovereignty is not a feature — it is the architecture.</sub>
</p>
```

---

## Implementation Notes

### For Manual Import to `.github` Repo

1. Copy the markdown block (everything between the backticks) above.
2. Create or update the file `SmartMur/.github/profile/README.md` in your `.github` repository.
3. Commit and push.
4. Verify at `https://github.com/smartmur`.

### Recommended Assets

Create these files in `SmartMur/.github/assets/` (or reference external CDN):

- **`nexus-banner.svg`** — 1200×400px, dark theme, featuring Nexus branding + tagline
- **`nexus-core-logo.png`** — 256×256px, Core tier identifier
- **`nexus-module-logo.png`** — 256×256px, Module tier identifier
- **`nexus-extension-logo.png`** — 256×256px, Extension tier identifier

### Customization Options

1. **Hero Banner**: Replace placeholder comment with actual image URL once assets are created.
2. **Badge URLs**: Update links to point to your actual deployment dashboard if hosted.
3. **Call-to-Action**: Add links to a homepage, launch blog post, or feature video if desired.
4. **Testimonials Section** (optional): Add quotes from early adopters or use cases.

---

## File Location

**Output**: `/home/ray/claude-superpowers/docs/reports/ecosystem-reposition/org-profile-README.md`

**Import destination**: `SmartMur/.github/profile/README.md`

Done!
