# To-Do Tracker

All user requests are logged here. Updated as work completes.

---

## Active / In Progress

*(none)*

## Backlog

- [ ] **Provide Cloudflare tunnel token** — run `/tunnel-setup set-token <token>` after getting from Cloudflare dashboard

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
- [x] **Set dashboard password** — generated strong password `***REDACTED***`, container recreated, verified auth works, documented in `docs/dashboard.md`
- [x] **Cloudflared tunnel setup skill** — `/tunnel-setup` skill built (status/set-token/start/stop/logs), crash loop stopped (1127 restarts halted), 31 tests, documented in `docs/cloudflared-setup.md`
- [x] **GitHub CI/CD** — enhanced `ci.yml` (matrix 3.12+3.13, lint, security scan, caching), enhanced `release.yml` (Docker build to ghcr.io), new `deploy.yml` (SSH deploy, manual trigger), `/deploy` skill built (15 tests), documented in `docs/ci-cd.md`
- [x] **P3: QA Guardian skill** — 12 checks across security/quality/test-health/efficiency, Telegram reports, audit logging, 38 tests
- [x] **P3: Cloudflared Fixer skill** — crash-loop detection, token validation, auto-fix, Telegram alerts, 30 tests
- [x] **P3: Infra Fixer skill (general)** — monitors ALL 9 Docker projects (40+ containers), auto-fix, 42 tests
- [x] **P3: Full test suite verified** — 982 passed (+156 from baseline 826), zero regressions
- [x] **P0–P2 complete** — 826 tests passing, all 8 phases done, shell hardened, paths migrated
- [x] **GitHub security audit completed** — 10 repos audited, 21+ critical findings, full report at `docs/github-audit-2026-03-02.md`
- [x] **Set up to-do.md tracker** — this file, located at `/home/ray/claude-superpowers/to-do.md`

---

*Location: `/home/ray/claude-superpowers/to-do.md`*
*Updated: 2026-03-02 (all audit findings fixed — only branch protection pending PAT)*
