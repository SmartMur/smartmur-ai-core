# Phase 1: Ecosystem Identity & Strategic Repositioning

> SmartMur GitHub Organization -- Strategic Architecture Document
> Date: 2026-03-03
> Status: Phase 1 Complete

---

## 1. Category Definition

**Category: Sovereign AI Infrastructure**

This is not a homelab. This is not a collection of scripts. This is not another "awesome self-hosted" list.

What the SmartMur ecosystem actually represents is a **complete, self-hosted AI operations platform** -- a vertically integrated stack where AI agents manage infrastructure, infrastructure serves AI agents, and a human operator retains full sovereignty over both.

The repos collectively solve a problem that no single open-source project addresses today: **How does an individual or small team run AI-powered operations autonomously, on their own hardware, without surrendering control to cloud platforms?**

The competitive landscape breaks down like this:

| Category | Examples | What they miss |
|----------|----------|----------------|
| AI agent frameworks | LangChain, CrewAI, AutoGen | No infrastructure awareness, no hardware control, no deployment story |
| Self-hosted platforms | Coolify, Portainer, Yacht | No AI integration, no autonomous operations |
| Homelab automation | Ansible playbooks, Terraform configs | No AI, no messaging, no real-time response |
| AI coding assistants | Claude Code, Cursor, Copilot | No persistent autonomy, no infrastructure management, no multi-channel |
| DevOps platforms | Backstage, Rancher | Enterprise-focused, cloud-native, no AI-first design |

The SmartMur ecosystem sits at the **intersection of all five** -- and that intersection is an unclaimed category. The correct name for it is **Sovereign AI Infrastructure**: AI that runs on your hardware, manages your systems, and answers to you alone.

---

## 2. Ecosystem Name

### **NEXUS**

Full name: **Nexus -- Sovereign AI Operations Platform**

Why "Nexus":

- **Literal meaning**: the central point where things connect. This ecosystem is the nexus between AI agents, infrastructure, messaging, security, and automation.
- **Not a cute acronym**. Not a forced portmanteau. A real word that communicates authority and centrality.
- **Domain-neutral**: works for homelab operators, small teams, indie hackers, security researchers, and solo DevOps engineers.
- **Scalable branding**: "Nexus Core" (the main platform), "Nexus Cluster" (the K8s layer), "Nexus Media" (the media stack) -- sub-brands emerge naturally.
- **Search-friendly**: "nexus self-hosted AI" is an uncontested search term. "nexus sovereign infrastructure" has zero competition.

The GitHub org description, repo names, and README headers should all reference "Nexus" as the platform identity. "SmartMur" remains the org/author name -- Nexus is the product.

Alternative candidates considered and rejected:

| Name | Reason for rejection |
|------|---------------------|
| Forge | Overused (GitHub, Puppet, SourceForge) |
| Bastion | Too military, too narrow (implies security only) |
| Sentinel | Implies monitoring, not operations |
| Cortex | Already taken by Weaveworks/Grafana |
| Hive | Implies swarm/cluster only |
| Armory | Too security-narrow |
| Citadel | Overused in infra projects |

---

## 3. One-Line Tagline

> **Your infrastructure, your AI, your rules.**

Backup options ranked:

1. "Your infrastructure, your AI, your rules." -- ownership, sovereignty, defiance
2. "AI operations that run on your hardware, answer to you, and never phone home." -- specificity, trust
3. "The self-hosted AI operations platform." -- clarity, SEO
4. "Sovereign AI for sovereign infrastructure." -- bold, political-tech resonance

Use #1 for headers and social. Use #3 for GitHub org description. Use #2 for README sub-headers where you need to expand.

---

## 4. Elevator Pitch

**Nexus is a self-hosted AI operations platform that turns your infrastructure into an autonomous, intelligent system -- without surrendering control to any cloud provider.** It combines an AI agent runtime (skills, memory, multi-model routing), a full DevOps toolkit (SSH fabric, browser automation, workflow engine, cron scheduler), and multi-channel messaging (Telegram, Slack, Discord, email) into a single, cohesive platform that runs entirely on your own hardware. Think of it as what would happen if Backstage, n8n, and Claude Code had a self-hosted child that refused to phone home.

---

## 5. GitHub Org Description

**For the GitHub org bio (160 chars max):**

```
Nexus — self-hosted AI operations platform. Skills, workflows, messaging, browser automation, SSH fabric, encrypted vault. Your infra, your AI, your rules.
```

**For the org README (pinned):**

```
Sovereign AI Operations Platform

Run AI agents on your own hardware. Manage infrastructure autonomously.
Multi-channel messaging. Browser automation. SSH fabric. Encrypted vault.
Zero cloud dependencies. 982 tests. Production-ready.
```

---

## 6. Strategic Reframing

### The Problem: "Homelab Projects" Framing

Right now, the SmartMur org reads as "a person's homelab scripts and some forks." This framing:

- Caps credibility at "hobbyist"
- Attracts zero contributors (nobody contributes to someone's personal scripts)
- Gets zero stars (nobody stars a homelab repo unless they need the exact same hardware)
- Has zero discoverability (GitHub does not surface "homelab" repos in trending or recommendations)

### The Repositioning: Reference Architecture Platform

Every repo must be reframed from "my personal config" to "a reference implementation you can adopt." The shift:

| Before (hobbyist) | After (platform) |
|-------------------|-------------------|
| "My homelab Docker stacks" | "Production-grade self-hosted service blueprints with security hardening" |
| "My K3s cluster setup" | "Opinionated K3s reference architecture: Ansible provisioning + Terraform state + GitOps" |
| "My dotfiles" | "Developer environment bootstrap: shell, Git, SSH, editor, and security tooling" |
| "My media server" | "Self-hosted media platform: automated acquisition, transcoding, streaming, and remote access" |
| "Some forks I use" | "Curated extensions to the AI agent ecosystem -- battle-tested in production" |

### The Three-Layer Narrative

Position the ecosystem as three concentric layers:

```
+----------------------------------------------------------+
|                    LAYER 3: EXTENSIONS                    |
|  Lighthouse-AI, Smoke, design-os, claude-code-tresor,    |
|  claude-code-skill-factory, agent-os                     |
|  "Community tools we use, harden, and contribute back"   |
+----------------------------------------------------------+
|                    LAYER 2: INFRASTRUCTURE                |
|  k3s-cluster, homelab, home_media, dotfiles              |
|  "The physical and virtual substrate Nexus runs on"      |
+----------------------------------------------------------+
|                    LAYER 1: NEXUS CORE                    |
|  claude-superpowers                                      |
|  "The AI operations brain that orchestrates everything"  |
+----------------------------------------------------------+
```

This layering tells a story: Nexus Core is the brain. The infrastructure repos are the body. The extensions are the nervous system reaching into the broader AI ecosystem. Together, they form a complete, sovereign AI operations platform.

### Discoverability Tactics

1. **Add GitHub Topics to every repo**: `self-hosted`, `ai-ops`, `homelab`, `automation`, `sovereign-ai`, `claude`, `infrastructure-as-code`, `devops`, plus repo-specific topics.
2. **Pin 6 repos** (GitHub max) in this order: `claude-superpowers`, `k3s-cluster`, `homelab`, `home_media`, `claude-code-tresor`, `agent-os`.
3. **Consistent README structure** across all repos: Nexus branding header, architecture diagram, quickstart, "Part of the Nexus Platform" badge/section.
4. **Cross-link aggressively**: every repo README should reference the ecosystem. Every README should link back to claude-superpowers as the core.
5. **Create a `nexus-platform` meta-repo** (or use the org README) with the full ecosystem map, getting-started guide, and architecture overview.

---

## 7. Repo Classification: Core / Modules / Extensions / Labs

### Tier 1: Core (the platform itself)

| Repo | Nexus Name | Role | Priority |
|------|-----------|------|----------|
| `claude-superpowers` | **Nexus Core** | AI operations runtime: skills, cron, messaging, SSH, browser, workflows, memory, vault, dashboard, MCP server, intake pipeline. 982 tests, 70 API endpoints, 43 MCP tools, 14 skills. | Highest. This is the product. |

**Action**: Rename repo description to "Nexus Core -- self-hosted AI operations platform." Add comprehensive GitHub Topics. This is the flagship -- every other repo exists to serve or extend it.

---

### Tier 2: Modules (infrastructure substrate, tightly coupled to Core)

These repos represent the physical and virtual infrastructure that Nexus Core manages. They are not generic templates -- they are the reference implementations for the environments Nexus operates in.

| Repo | Nexus Name | Role | Classification Rationale |
|------|-----------|------|--------------------------|
| `k3s-cluster` | **Nexus Cluster** | Kubernetes reference architecture: Ansible provisioning, Terraform state management, GitOps-ready K3s deployment on Proxmox. | Nexus Core's SSH fabric and workflow engine orchestrate this cluster. The cluster runs workloads that Nexus schedules. Tight bidirectional dependency. |
| `homelab` | **Nexus Infra** | Self-hosted service blueprints: 40+ Docker Compose stacks for monitoring (Grafana, Prometheus, Loki), security (CrowdSec, Authentik), networking (Headscale, Cloudflared), and development tools. | Nexus Core's container watchdog, infra-fixer skill, and deploy workflow directly manage these stacks. This is the body Nexus inhabits. |
| `home_media` | **Nexus Media** | Media platform stack: automated acquisition (*arr suite), transcoding, streaming (Plex/Jellyfin), and secure remote access (Tailscale). | Managed by Nexus Core's Docker monitoring and cron-driven health checks. Separate repo because it has a distinct operational domain (media vs. infrastructure). |
| `dotfiles` | **Nexus Bootstrap** | Developer environment provisioning: shell configuration, Git setup, SSH hardening, editor config, security tooling (pre-commit hooks, security_scrub.py). | The starting point. Before Nexus Core runs, this repo provisions the operator's environment. Includes the security tooling that all other repos depend on. |

**Action for all Modules**: Add "Part of the Nexus Platform" section to each README. Add cross-links to Nexus Core. Ensure each has a consistent GitHub Topics set. Rewrite descriptions to emphasize "reference architecture" not "my personal config."

---

### Tier 3: Extensions (AI ecosystem integrations, loosely coupled)

These are forks of community projects that extend the Nexus platform's AI capabilities. They are maintained with upstream compatibility but hardened and configured for Nexus integration.

| Repo | Nexus Name | Role | Upstream | Integration Point |
|------|-----------|------|----------|-------------------|
| `claude-code-tresor` | **Nexus Vault Agent** | Claude Code agent orchestration with secure credential handling. | [@anthropics](https://github.com/anthropics) community | Extends Nexus Core's vault and agent dispatch. Provides patterns for multi-agent orchestration that inform Nexus Core's intake pipeline. |
| `claude-code-skill-factory` | **Nexus Skill Factory** | Skill creation and management framework for Claude Code agents. | Community | Directly feeds Nexus Core's skill registry. Skills created here can be imported into the `/skills/` directory and managed by `claw skill sync`. |
| `agent-os` | **Nexus Agent OS** | Agent operating system -- runtime environment patterns for autonomous AI agents. | Community | Architectural reference for how Nexus Core manages agent lifecycle, memory, and tool access. |

**Action for all Extensions**: Add "Nexus Platform Extension" badge. Document what was changed from upstream and why. Maintain clear upstream tracking (rebase strategy, not merge). Contribute security fixes back upstream.

---

### Tier 4: Labs (experimental, research, not production-path)

These repos are forks used for research, evaluation, or one-off contributions. They are not part of the production Nexus stack and should be clearly labeled as experimental.

| Repo | Status | Notes |
|------|--------|-------|
| `Lighthouse-AI` | **Lab / Evaluation** | AI-powered code analysis. Evaluated for integration into Nexus Core's QA Guardian skill. May graduate to Extension if actively used. |
| `Smoke` | **Lab / Evaluation** | Testing framework. Evaluated for use in Nexus Core's CI pipeline. Not currently integrated. |
| `design-os` | **Lab / Archived** | Design system OS. Forked for reference. No active integration with Nexus. Candidate for archival. |

**Action for Labs**: Add `[LAB]` prefix to repo descriptions. Consider archiving `design-os` if there is no active use case. Do not invest in READMEs or branding for these -- they are research artifacts.

---

## Summary: The Nexus Ecosystem Map

```
THE NEXUS PLATFORM — Sovereign AI Operations
=============================================

                         +-----------------------+
                         |     NEXUS CORE        |
                         | claude-superpowers    |
                         |                       |
                         | AI Runtime / Skills   |
                         | Cron / Workflows      |
                         | Messaging Gateway     |
                         | SSH Fabric / Browser   |
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
   |k3s-cluster | |homelab     |  |home_media        | |dotfiles       |
   |            | |            |  |                  | |               |
   |K3s+Ansible | |40+ Docker  |  |Plex/Jellyfin    | |Shell/Git/SSH  |
   |+Terraform  | |stacks      |  |*arr suite       | |Security tools |
   +------------+ +------------+  +------------------+ +---------------+

            extends / integrates / feeds back into
                                     |
            +------------+-----------+-----------+
            |            |                       |
   +--------+------+ +--+-------------+ +-------+---------+
   |NEXUS          | |NEXUS           | |NEXUS            |
   |VAULT AGENT    | |SKILL FACTORY   | |AGENT OS         |
   |claude-code-   | |claude-code-    | |agent-os         |
   | tresor        | | skill-factory  | |                 |
   |Agent orch.    | |Skill creation  | |Agent runtime    |
   +---------------+ +----------------+ +-----------------+

   +---------------------------------------------------+
   | LABS: Lighthouse-AI | Smoke | design-os           |
   | (evaluation / research / archived)                |
   +---------------------------------------------------+
```

---

## Strategic Principles Going Forward

1. **Nexus Core is the product. Everything else is a module, extension, or lab.** Never dilute the core by splitting features into separate repos. The monorepo approach for Core is correct -- it keeps the 982-test suite unified and the developer experience coherent.

2. **Every repo must justify its existence relative to Nexus.** If a repo does not serve, extend, or support Nexus Core, it should be archived or moved to a personal account. The org is a platform, not a bookmarks folder.

3. **Reference architecture, not personal config.** Every committed file should be generalizable. Hardcoded IPs, personal paths, and machine-specific configs belong in `.env` files and `examples/` directories, never in committed code. (The GitHub security audit already flagged violations of this principle.)

4. **Security is the brand differentiator.** The security audit and hardening work (branch protection across 10 repos, script injection fixes, credential externalization) is not just maintenance -- it is the core value proposition. "Sovereign" means nothing if the platform is not hardened. Lead with security in all messaging.

5. **Stars come from README quality, not code quality.** Harsh truth: most GitHub users never read the code. They read the README, look at the architecture diagram, count the stars, and decide in 30 seconds. Every repo needs a README that sells the platform in those 30 seconds.

6. **Cross-linking creates network effects.** Every repo linking to every other repo creates internal PageRank. GitHub's recommendation engine surfaces repos that are part of connected ecosystems. A single repo with 50 stars gets less visibility than 6 repos with 10 stars each that all reference each other.

7. **Fork management is a signal of professionalism.** Unmaintained forks signal "I starred this and forgot." Active forks with security hardening, upstream contribution, and integration documentation signal "we evaluated this, hardened it, and integrated it into our platform." Every fork in the Extensions tier needs this treatment. Every fork in Labs that cannot justify its existence should be removed.

---

## Immediate Next Steps (Phase 2 Preparation)

| # | Action | Owner | Effort |
|---|--------|-------|--------|
| 1 | Update GitHub org bio to Nexus description | Admin | 5 min |
| 2 | Pin 6 repos in recommended order | Admin | 5 min |
| 3 | Add GitHub Topics to all 10 repos | Admin | 30 min |
| 4 | Rewrite claude-superpowers README header with Nexus branding | Dev | 1 hr |
| 5 | Add "Part of the Nexus Platform" section to k3s-cluster, homelab, home_media, dotfiles READMEs | Dev | 2 hr |
| 6 | Archive or label Labs repos | Admin | 15 min |
| 7 | Create Phase 2 doc: Visual Identity (logo concepts, color palette, badge designs) | Design | 2 hr |
| 8 | Create Phase 3 doc: Content Strategy (blog posts, social, launch plan) | Strategy | 3 hr |

---

*Document generated by Claude Code ecosystem analysis.*
*All recommendations are based on actual repo contents, competitive positioning, and GitHub discoverability patterns.*
