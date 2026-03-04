# To-Do Tracker

All user requests are logged here. Updated as work completes.

---

## Active / In Progress

*(none)*

## Backlog

- [ ] **Provide Cloudflare tunnel token** — run `/tunnel-setup set-token <token>` after getting from Cloudflare dashboard
- [ ] **Full test suite verification** — run after all Wave 1 agents land
- [ ] **Beat Tresor Sprint 1** — agent registry, orchestration commands, report outputs, pack installer
- [ ] **Beat Tresor Sprint 2** — DAG executor, auto agent selection, benchmarks, dashboard monitor

## Completed (Wave 1 — 2026-03-03)

- [x] **SmartMur/.github repository created** — org profile README pushed, `https://github.com/SmartMur/.github` live, profile/README.md contains Nexus ecosystem positioning
- [x] **Shell hardening** — last `shell=True` in `job_runner.py` fixed, entire codebase clean
- [x] **CLI test coverage** — 166 tests across 11 `cli_*.py` modules (was zero)
- [x] **Network-scan skill** — replaced nmap stub with working Python scanner, 36 tests
- [x] **Shared lib.sh** — 251-line shared library, 8 skill scripts refactored to use it
- [x] **Exception specificity** — 45 bare `except Exception` → specific types across 19 files, 1587 tests passing

## Completed

- [x] **GitHub remote set up** — git init, 127 files committed (`3c3cba4`), pushed to `SmartMur/claude-superpowers` (private). `.gitignore` updated. CI/CD ready to trigger on push.
- [x] **Dashboard verified — all 12 skills visible** — fixed wrong default path in skill_registry/skill_creator, added `_template` exclusion, added skills volume mount to docker-compose.yaml

- [x] **Externalized homelab credentials** — 6 compose files (Keycloak, Guacamole, Code-Server, Gitea, Frigate, CrowdSec) → env vars + .env.example files, pushed `688198d`
- [x] **Restricted monitoring ports** — Prometheus/InfluxDB/Loki/Headscale bound to 127.0.0.1, pushed `d19e600`
- [x] **Docker Dependabot added** — homelab (`7dbfa8b`), home_media (`fd7bf00`), k3s-cluster (`8e5fa71`), claude-superpowers (local)
- [x] **Branch protection ENABLED** — 10/16 repos protected via `/github-admin` skill + `gh` CLI. 6 private repos need GitHub Pro.
- [x] **`/github-admin` skill built** — auth, protect, audit, repos commands. 25 tests. `gh` CLI installed at `~/.local/bin/gh`, authed as SmartMur.
- [x] **PUSHED: ALL 8 repos security fixes** — home_media, homelab, k3s-cluster, dotfiles, design-os, agent-os, claude-code-tresor, claude-code-skill-factory
  - `home_media` → `db1d631` (master): .gitignore, CI workflows, dependabot
  - `homelab` → `490eddc` (main): swarm script fixes, CI hardening, SECURITY.md
  - `k3s-cluster` → `cb402f4` (main): SHA pins, SSH fix, CI permissions
  - `dotfiles` → `c942ebd` (main): automerge guard, SHA pinning
  - `design-os` → `6fbfdf1` (main): pull_request_target fix, input validation
  - `agent-os` → `ab75fa0` (main): pull_request_target fix
  - `claude-code-tresor` → `ee6032e` (main): script injection fixes (5 workflows), SHA pinning (9 workflows)
  - `claude-code-skill-factory` → `d5440d9` (dev): script injection fixes (7 workflows), SHA pinning (17 workflows)
- [x] **Set dashboard password** — generated strong password (stored in .env DASHBOARD_PASS), container recreated, verified auth works, documented in `docs/reference/dashboard.md`
- [x] **Cloudflared tunnel setup skill** — `/tunnel-setup` skill built (status/set-token/start/stop/logs), crash loop stopped (1127 restarts halted), 31 tests, documented in `docs/guides/cloudflared-setup.md`
- [x] **GitHub CI/CD** — enhanced `ci.yml` (matrix 3.12+3.13, lint, security scan, caching), enhanced `release.yml` (Docker build to ghcr.io), new `deploy.yml` (SSH deploy, manual trigger), `/deploy` skill built (15 tests), documented in `docs/reference/ci-cd.md`
- [x] **P3: QA Guardian skill** — 12 checks across security/quality/test-health/efficiency, Telegram reports, audit logging, 38 tests
- [x] **P3: Cloudflared Fixer skill** — crash-loop detection, token validation, auto-fix, Telegram alerts, 30 tests
- [x] **P3: Infra Fixer skill (general)** — monitors ALL 9 Docker projects (40+ containers), auto-fix, 42 tests
- [x] **P3: Full test suite verified** — 982 passed (+156 from baseline 826), zero regressions
- [x] **P0–P2 complete** — 826 tests passing, all 8 phases done, shell hardened, paths migrated
- [x] **GitHub security audit completed** — 10 repos audited, 21+ critical findings, full report at `docs/github-audit-2026-03-02.md`
- [x] **Set up to-do.md tracker** — this file, located at `/home/ray/claude-superpowers/to-do.md`

---

Perfect. We’re going to give Claude a **board-level strategic mandate**, not a casual rewrite request.

This master prompt will:

* Unify all directions (security, AI, IaC, SOC, DevOps)
* Force ecosystem thinking
* Create layered architecture
* Reposition as a reference platform
* Optimize for GitHub stars
* Improve messaging
* Create a growth roadmap
* Turn it into something that feels like a movement, not a homelab

You can paste this directly into Claude.

---

# 🔥 MASTER ECOSYSTEM ORGANIZATION PROMPT FOR CLAUDE

You are a senior open-source ecosystem architect, brand strategist, and GitHub growth expert.

You are helping me transform my GitHub organization from a collection of homelab and automation projects into a cohesive, high-credibility, star-worthy open-source ecosystem.

My repositories currently span:

* Security-first homelab architecture
* AI automation (Claude agents, workflows)
* Infrastructure-as-code
* SOC/SIEM stack (Wazuh, Graylog, observability)
* DevOps productivity systems
* Kubernetes / Docker / Proxmox automation

Your mission is to reorganize and reposition everything into a single unified platform narrative.

---

## 🎯 PRIMARY OBJECTIVE

Turn this GitHub organization into:

> A Security-First, AI-Ready, Self-Hosted Infrastructure Reference Architecture

It must feel like:

* A platform
* A system
* A blueprint others can replicate
* A sovereign infrastructure movement
* Not personal scripts
* Not experimental repos

Optimize for:

* Credibility
* Clarity
* Star growth
* Contributor attraction
* Authority in the self-hosted AI space

Assume we want to become a top 1% recognized DevOps / AI automation open-source ecosystem within 18 months.

---

# PHASE 1 — Strategic Repositioning

1. Define the true category this ecosystem belongs in.
2. Propose:

   * Umbrella ecosystem name
   * One-line tagline
   * 2–3 sentence elevator pitch
   * Strong GitHub organization description
3. Reframe this from “homelab projects” into a:

   * Reference architecture
   * Platform
   * Blueprint
   * System

Be opinionated and bold.

---

# PHASE 2 — Architecture Model

Design a layered architecture model that unifies everything.

For example (improve this if needed):

Layer 1: Infrastructure Foundation (Proxmox, K3s, Docker)
Layer 2: Network & Security (Firewalling, segmentation, zero-trust)
Layer 3: Observability & SOC (Wazuh, Graylog, SIEM stack)
Layer 4: AI Automation Layer (Claude agents, orchestration, workflows)
Layer 5: DevOps & GitOps (CI/CD, IaC, automation pipelines)

Deliver:

* A clean layered stack explanation
* A visual architecture diagram in ASCII or structured text
* Clear explanation of how each existing repo fits into the stack

---

# PHASE 3 — Repo Reorganization Strategy

For each repository:

* Define its role in the ecosystem
* Suggest renaming if necessary
* Suggest merging or archiving if redundant
* Rewrite its positioning
* Rewrite README intro (outcome-focused, not tool-focused)
* Suggest badges
* Suggest folder restructuring
* Suggest documentation improvements
* Suggest missing diagrams or screenshots

Convert scattered repos into:

* Core Platform
* Modules
* Extensions
* Experimental Labs

Not random scripts.

---

# PHASE 4 — Messaging Upgrade

Rewrite:

* Organization README (flagship overview)
* Platform overview README template
* Standardized README template for all repos
* Contributor guide outline
* “Why This Exists” philosophy section

Reframe messaging from:

“I built this for my lab”

To:

“This is a sovereign AI-ready infrastructure blueprint for serious builders.”

Tone:

* Confident
* Architectural
* Vision-driven
* Professional
* Minimal fluff

---

# PHASE 5 — Star Optimization Strategy

Explain clearly:

* Why people currently wouldn’t star this
* What psychological triggers cause stars
* What visual elements are missing
* Why diagrams matter
* Why outcome-driven READMEs matter
* Why naming matters

Then provide:

* A 6-month star growth roadmap
* Specific tactical actions
* Documentation improvements
* Demo strategy
* Community strategy
* Social proof strategy

Be concrete and strategic.

---

# PHASE 6 — Authority & Differentiation

Compare this ecosystem against:

* Popular homelab repos
* Self-hosted AI stacks
* DevOps automation toolkits
* Security lab projects

Explain:

* What makes them star-worthy
* What gaps exist
* How we differentiate
* How to position as more advanced or more opinionated

---

# PHASE 7 — Long-Term Vision

Design:

* 12-month roadmap
* Core feature milestones
* Ecosystem expansion ideas
* What would make this “10k star worthy”
* What would make this conference-talk worthy
* What would make this enterprise-relevant

Think platform-level.

---

# CRITICAL CONSTRAINTS

* Treat this as one ecosystem, not separate repos.
* Think system-first.
* Think architecture-first.
* Think movement, not hobby.
* Be brutally honest.
* Deliver clear action steps.

---

# OUTPUT FORMAT

Deliver in clean structured sections:

1. Ecosystem Identity
2. Architecture Model
3. Repo Restructure Plan
4. Messaging Rewrite
5. Star Growth Strategy
6. Competitive Analysis
7. 12-Month Roadmap

No fluff.
High signal.
Strategic depth.

---

🔥 End of prompt.

---

# Why This Works

This forces Claude to:

* Think like a CTO
* Think like a product marketer
* Think like an open-source growth expert
* Think ecosystem, not scripts
* Design a layered platform narrative
* Create a brand
* Create a roadmap

This is how you turn:

“SmartMur GitHub”

Into:

“A Recognized Self-Hosted AI Infrastructure Platform”

---
++++++++++++++++++++++++++++++++++++++++
Next feature enrichment: from 
++++++++++++++++++++++++++++++++++++++++
**2-Sprint “Beat Tresor” Backlog**

**Win criteria by end of Sprint 2**
1. Ship executable parity for Tresor’s orchestration set (security/perf/ops/quality) via `claw` + dashboard + MCP.
2. Add intelligent agent recommendation + dependency-aware parallel execution.
3. Add install/update DX parity for agent/command packs.
4. Add at least 200 new tests across new surfaces.
5. Publish a competitive report with measurable deltas (coverage, latency, reliability, security controls).

**Sprint 1 (2 weeks): Parity + Foundation**
| ID | Priority | Est. | Ticket | Main files | Acceptance criteria |
|---|---|---:|---|---|---|
| SP1-01 | P0 | 12h | Agent registry + CLI (`claw agent list/run/recommend`) | [cli.py](/home/ray/claude-superpowers/superpowers/cli.py), new `superpowers/agent_registry.py`, new `superpowers/cli_agent.py` | Agent manifests load from `subagents/**/agent.md`; list/run works; tests added |
| SP1-02 | P0 | 10h | Tech-stack detection + agent recommendation API | new `superpowers/agent_router.py`, new dashboard router | `GET /api/agents/recommend` returns ranked agents based on repo signals |
| SP1-03 | P0 | 16h | Orchestration command pack (10 commands) | [workflow/engine.py](/home/ray/claude-superpowers/superpowers/workflow/engine.py), `workflows/*.yaml`, CLI wiring | `claw` commands for audit/vuln/compliance/profile/benchmark/deploy-validate/health-check/incident/code-health/debt-analysis all runnable |
| SP1-04 | P0 | 14h | Standard report outputs (JSON + Markdown) for all orchestration runs | new `superpowers/reporting.py` | Every orchestration command emits structured artifact + summary markdown |
| SP1-05 | P1 | 8h | Pack installer/updater (`claw setup install-pack`, `claw setup update-pack`) | [setup_wizard.py](/home/ray/claude-superpowers/superpowers/setup_wizard.py) + new module | One-command install/update with checksum validation and rollback |
| SP1-06 | P1 | 6h | Docs parity for new command/agent surfaces | `docs/reference/*`, `README.md` | Command catalog + agent catalog documented with examples |

**Sprint 2 (2 weeks): Scale + Differentiation**
| ID | Priority | Est. | Ticket | Main files | Acceptance criteria |
|---|---|---:|---|---|---|
| SP2-01 | P0 | 16h | Dependency-aware parallel executor for multi-agent orchestration | new `superpowers/orchestrator.py` | DAG execution with conflict checks; safe parallelization proven by tests |
| SP2-02 | P0 | 14h | Auto agent selection integrated into workflows and jobs | [job_runner.py](/home/ray/claude-superpowers/superpowers/job_runner.py), workflow engine | Orchestrations auto-pick agents by task + repo context; override supported |
| SP2-03 | P0 | 10h | Competitive benchmark harness | new `tests/benchmarks/*`, `docs/reports/*` | Reproducible benchmark script comparing throughput/latency/task completion |
| SP2-04 | P1 | 12h | Dashboard “Orchestrations” monitor (queue, run graph, artifacts) | [dashboard/app.py](/home/ray/claude-superpowers/dashboard/app.py), router + frontend | Live status + artifact links per run |
| SP2-05 | P1 | 10h | Policy engine for orchestration safety | [config.py](/home/ray/claude-superpowers/superpowers/config.py), middleware | Per-command approval/policy rules; path and secret protections enforced |
| SP2-06 | P0 | 12h | Reliability hardening + soak tests | test suite | 24h soak pass; no crash loops; retry/idempotency validated |
| SP2-07 | P1 | 8h | Release packaging + migration notes | docs + release scripts | Tagged release with upgrade instructions and rollback path |

**Execution order (critical path)**
1. SP1-01 → SP1-02 → SP1-03  
2. SP1-03 → SP1-04 → SP2-01  
3. SP2-01 → SP2-02 → SP2-04  
4. SP2-05 + SP2-06 run in parallel after SP2-02 stable

**Definition of “beat Tresor”**
1. Match orchestration breadth with executable commands, not doc-only templates.
2. Provide stronger runtime guarantees (tests, policy controls, soak reliability).
3. Deliver superior operational UX (dashboard monitor + artifacts + MCP integration).


----
*Location: `/home/ray/claude-superpowers/to-do.md`*
*Updated: 2026-03-02 (all audit findings fixed — only branch protection pending PAT)*
