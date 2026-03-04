# GitHub Security Audit — smartmur (2026-03-02)

**Status: ALL 4 agents completed. Full audit across 10 repos.**

---

## CRITICAL FINDINGS (fix immediately)

### Across ALL repos
- **No branch protection on ANY repo** — all 10 repos have unprotected default branches

### k3s-cluster (3 critical)
1. `pull_request_target` + write permissions in `dependabot-automerge.yml` — privilege escalation vector
2. `curl -sfL https://get.k3s.io | sh` in `ansible/playbook-k3s.yml` — remote code execution risk
3. `StrictHostKeyChecking=no` in `scripts/00-create-proxmox-template.sh` — MITM attack vector

### homelab (13 critical)
1. Branch protection DISABLED on `main` + auto-merge Dependabot = zero human review path
2. `pull_request_target` + write permissions in `dependabot-automerge.yml`
3. Hardcoded credentials in 6 docker-compose files: Keycloak (`SUPERsecret`), Guacamole (`root_pass`), Code-Server (`password`), Gitea (`gitea`), Frigate (`password`), CrowdSec (placeholder API key)
4. `chmod 666 /var/run/docker.sock` in Docker Swarm scripts — full host compromise
5. `iptables -F` + `INPUT ACCEPT` in swarm scripts — firewall completely disabled
6. `StrictHostKeyChecking no` in swarm scripts
7. `curl | sh` pattern in K3S deploy script

### Forked repos (5 critical)
1. **Script injection in `smart-sync.yml`** (claude-code-tresor + skill-factory) — `github.event` data interpolated into bash with write permissions
2. **Script injection in `pr-into-dev.yml`** (skill-factory) — `github.head_ref` directly in bash = shell injection via branch name
3. **Script injection in `claude-code-review.yml`** (skill-factory) — PR titles/labels in shell commands
4. **`pull_request_target` + write** in `pr-decline.yml` (design-os + agent-os)
5. Combined `contents: write` + `id-token: write` + unpinned actions in tresor/skill-factory

---

## WARNING FINDINGS (fix soon)

### Systematic across all repos
- Zero SHA-pinned GitHub Actions anywhere (all use mutable tags like @v4, @v6)
- `|| true` suppresses security scan failures in homelab CI
- Missing `SECURITY.md` in homelab
- Missing explicit `permissions` blocks in CI workflows
- No concurrency control in most CI workflows
- `id-token: write` over-granted in tresor/skill-factory (6+ workflows)
- `CLAUDE_CODE_OAUTH_TOKEN` passed to unpinned third-party actions

### homelab-specific warnings
- Grafana running as root (`user: "0"`)
- Docker socket mounted in Authentik, Komodo, Telegraf
- Chrome remote debugging bound to `0.0.0.0:9222` (Hoarder)
- Monitoring ports (Prometheus 9090, InfluxDB 8086, Loki 3100) exposed without auth
- No `set -euo pipefail` in shell scripts
- Unquoted variables throughout shell scripts
- Hardcoded IPs everywhere

### k3s-cluster warnings
- Hardcoded dev path `/Users/dre/Desktop/LABing/Projects/Notify`
- Kubeconfig written with mode 644 (should be 600)
- Hardcoded IPs in scripts/ansible

---

## POSITIVE FINDINGS

### k3s-cluster (above average security)
- Comprehensive `.gitignore` (one of the best seen)
- Custom `security_scrub.py` pre-commit hook
- `detect-private-key` pre-commit hook
- Dependabot for github-actions + terraform
- Branch protection enabled with required status checks
- No secrets exposed in repo
- All shell scripts use `set -euo pipefail`

### homelab (mixed)
- Strong `.gitignore`, gitleaks config, pre-commit hooks
- `.env.example` templates for some services
- Some services use proper env var substitution with `${VAR:?required}`
- `no-new-privileges:true` in several containers

### Forked repos
- No committed secrets in any fork
- `.env.example` files all contain placeholders only

---

## PRIORITY FIX ORDER

### P0 — Today
1. Enable branch protection on ALL 10 repos (most impactful single fix)
2. Fix script injection in smart-sync.yml, pr-into-dev.yml, claude-code-review.yml
3. Remove `chmod 666 /var/run/docker.sock` from homelab swarm scripts
4. Remove `iptables -F` + `INPUT ACCEPT` from swarm scripts

### P1 — This week
5. Pin all GitHub Actions to SHA hashes across all repos
6. Replace `pull_request_target` with `pull_request` or add proper guards
7. Externalize hardcoded credentials in homelab docker-compose files to .env
8. Fix `StrictHostKeyChecking=no` → `accept-new` everywhere
9. Remove `|| true` from security scan steps
10. Add `permissions: contents: read` to all CI workflows

### P2 — Next week
11. Add SECURITY.md to homelab
12. Expand Dependabot to cover Docker images
13. Add shellcheck to CI for shell-based repos
14. Restrict exposed monitoring ports to localhost
15. Quote all shell variables, add `set -euo pipefail`

---

## dotfiles (Grade: B+)
- CRITICAL: `pull_request_target` + write in `dependabot-automerge.yml`
- WARNING: Actions pinned by tag not SHA, no permissions block in ci.yml, curl|sh for Homebrew
- GOOD: Excellent .gitignore, security_scrub.py, SECURITY.md, detect-private-key hook, clean shell configs

## home_media (Grade: D+)
- CRITICAL: **No .gitignore file at all** — nothing prevents .env commits
- CRITICAL: **No CI/CD workflows** — zero automated testing/scanning
- CRITICAL: Docker socket mounted in tsdproxy + dockhand (host root equiv)
- CRITICAL: Termix (web terminal) + Dockhand (Docker UI) have zero authentication
- WARNING: All images use `:latest` tags, no health checks, no resource limits, ports bound to 0.0.0.0
- GOOD: Tailscale-only architecture, secrets externalized to .env, read-only media mounts

---

## FIX STATUS (all pushed)

| Repo | Commit | Branch | Fixes Applied |
|------|--------|--------|---------------|
| home_media | `db1d631` | master | .gitignore, CI workflows, dependabot |
| homelab | `490eddc` | main | docker.sock chmod removed, iptables -F removed, SSH StrictHostKeyChecking→accept-new, CI hardened, SECURITY.md added |
| k3s-cluster | `cb402f4` | main | Actions SHA-pinned, StrictHostKeyChecking→accept-new, CI permissions+concurrency |
| dotfiles | `c942ebd` | main | Automerge fetch-metadata guard, Actions SHA-pinned, CI permissions |
| design-os | `6fbfdf1` | main | pull_request_target→pull_request, input validation, Actions SHA-pinned |
| agent-os | `ab75fa0` | main | pull_request_target→pull_request, input validation, Actions SHA-pinned |
| claude-code-tresor | `ee6032e` | main | Script injection fixed (5 workflows: smart-sync, claude-code-review, main-branch-guard, release-orchestrator, ci-quality-gate), Actions SHA-pinned (9 workflows) |
| claude-code-skill-factory | `d5440d9` | dev | Script injection fixed (7 workflows: smart-sync, pr-into-dev, claude-code-review, dev-to-main, release-orchestrator, ci-quality-gate, ci-commit-branch-guard), Actions SHA-pinned (17 workflows) |

### Additional fixes (wave 2)
| Repo | Commit | Fixes |
|------|--------|-------|
| homelab | `688198d` | Externalized creds in 6 compose files (Keycloak, Guacamole, Code-Server, Gitea, Frigate, CrowdSec) + .env.example files |
| homelab | `d19e600` | Restricted Prometheus/InfluxDB/Loki/Headscale metrics to 127.0.0.1 |
| homelab | `7dbfa8b` | Added Docker image Dependabot |
| home_media | `fd7bf00` | Expanded Docker Dependabot to cover all compose dirs |
| k3s-cluster | `8e5fa71` | Added Docker image Dependabot |

### Branch protection (wave 3)
- [x] **10 repos protected**: homelab, k3s-cluster, home_media, claude-code-skill-factory, claude-code-tresor, agent-os, design-os, dotfiles, Lighthouse-AI, Smoke
- [ ] **6 private repos blocked**: claude-superpowers, hommie, zabbix_enchancement, vmware-audit, TrainingWheels, MurzDev_env — GitHub Free doesn't support branch protection on private repos (requires Pro)

---

*Audit performed by Claude Code with 4 parallel research agents*
*Fixes applied by 6 parallel fix agents across 2 sessions*
*Completed: 2026-03-02*
