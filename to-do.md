# To-Do Tracker

All user requests are logged here. Updated as work completes.

---

## Active / In Progress

### Q1 Launch
- [x] **Install scripts** — `install.sh` + `install-docker.sh` for one-command setup
- [x] **MkDocs Material documentation site** — builds clean, full reference docs
- [x] **Ollama/multi-LLM provider integration** — ProviderRegistry with Claude/Ollama/OpenAI fallback chain
- [x] **Star-optimized README rewrite** — SmartMur Core format, comparison tables, architecture diagram
- [x] **Demo/recording scripts** — scripted demo scenarios for terminal recording
- [x] **GitHub issue/PR templates + good first issues** — `.github/ISSUE_TEMPLATE/`, PR template, starter issues created
- [x] **Repo rename to smartmur-ai-core** — already renamed on GitHub remote
- [x] **GitHub Pages deployment** — deployed via `mkdocs gh-deploy --force` to gh-pages branch
- [x] **Terminal GIF recording** — demo.cast + demo.svg created via asciinema + svg-term-cli (GIF needs `agg`/cargo)
- [x] **Dashboard screenshots** — 12 PNGs captured: login, dashboard, all subsections
- [x] **Topic tags per naming map** — all 22 SmartMur repos tagged per naming map v1

## Backlog

- [ ] **Provide Cloudflare tunnel token** — run `/tunnel-setup set-token <token>` after getting from Cloudflare dashboard

## Completed (Beat Tresor — 2026-03-04)

- [x] **Beat Tresor Sprint 2** — DAG executor, auto agent selection, policy engine, benchmarks, soak tests, dashboard orchestrations monitor, release packaging — 2303 tests passing
- [x] **Beat Tresor Sprint 1** — agent registry (45 tests), orchestrator (62 tests), reporting (50 tests), pack manager (44 tests) — commit `dafd741`
- [x] **Sprint 2 validation run (tmux)** — session `overnight-agents-20260304-023817`; 169 passed (DAG, policy, dashboard orchestrations)
- [x] **Full test suite verification** — 2303 passed (local run)

## Completed (Infrastructure — 2026-03-04)

- [x] **Private repos security baseline hardening** — all private SmartMur repos: LICENSE, SECURITY.md, CONTRIBUTING.md, dependabot, workflow coverage, 0 open alerts
- [x] **Macbook->VM project sync cron** — `/home/ray/bin/macbook_projects_sync.sh` pulls from Mac every 15 min
- [x] **ChatGPT fallback when Claude is unavailable** — provider aliasing, fallback wiring for `claw agent run` + Telegram/inbound

## Completed (Wave 1 — 2026-03-03)

- [x] **Shell hardening** — last `shell=True` in `job_runner.py` fixed, entire codebase clean
- [x] **CLI test coverage** — 166 tests across 11 `cli_*.py` modules
- [x] **Network-scan skill** — replaced nmap stub with working Python scanner, 36 tests
- [x] **Shared lib.sh** — 251-line shared library, 8 skill scripts refactored
- [x] **Exception specificity** — 45 bare `except Exception` fixed across 19 files

## Completed (Earlier)

- [x] **GitHub remote set up** — pushed to `SmartMur/claude-superpowers` (now `smartmur-ai-core`)
- [x] **Dashboard verified — all 12 skills visible**
- [x] **Externalized homelab credentials** — 6 compose files updated
- [x] **Restricted monitoring ports** — bound to 127.0.0.1
- [x] **Docker Dependabot added** — homelab, home_media, k3s-cluster, claude-superpowers
- [x] **Branch protection ENABLED** — 10/16 repos via `/github-admin` skill
- [x] **PUSHED: ALL 8 repos security fixes**
- [x] **Set dashboard password** — strong password in .env
- [x] **Cloudflared tunnel setup skill** — `/tunnel-setup`, crash loop stopped, 31 tests
- [x] **GitHub CI/CD** — ci.yml, release.yml, deploy.yml
- [x] **P3 skills** — QA Guardian, Cloudflared Fixer, Infra Fixer
- [x] **P0-P2 complete** — all 8 phases done
- [x] **GitHub security audit** — 10 repos, 21+ findings
- [x] **Ecosystem repositioning** — all 7 phases + 5 execution waves complete
- [x] **SmartMur/.github org profile** — created and pushed

---
*Location: `/home/ray/claude-superpowers/to-do.md`*
*Updated: 2026-03-06 (Q1 launch items tracked, Sprint 2 done, repo renamed)*
