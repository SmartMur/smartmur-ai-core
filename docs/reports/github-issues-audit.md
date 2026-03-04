# SmartMur GitHub Audit Report

**Date**: 2026-03-04
**Scope**: All 19 repositories under the SmartMur account
**Tool**: `gh` CLI (authenticated)

---

## Repository Inventory

| # | Repository | Type | Archived | Private | Default Branch | Issues Enabled |
|---|-----------|------|----------|---------|----------------|----------------|
| 1 | claude-superpowers | owned | no | **yes** | main | yes |
| 2 | claude-superpowers-skillhub | owned | no | **yes** | master | yes |
| 3 | docker-stacks | owned | no | **yes** | master | yes |
| 4 | dotfiles | owned | no | no | main | yes |
| 5 | homelab | owned | no | no | main | yes |
| 6 | hommie | owned | no | **yes** | main | yes |
| 7 | k3s-cluster | owned | no | no | main | yes |
| 8 | MurzDev_env | owned | no | **yes** | main | yes |
| 9 | nexus-media | owned | no | no | master | yes |
| 10 | TrainingWheels | owned | no | **yes** | main | yes |
| 11 | vmware-audit | owned | no | **yes** | main | yes |
| 12 | zabbix_enchancement | owned | no | **yes** | main | yes |
| 13 | .github | owned | no | no | main | yes |
| 14 | agent-os | fork | no | no | main | **no** |
| 15 | claude-code-tresor | fork | no | no | main | **no** |
| 16 | claude-code-skill-factory | fork | no | no | dev | **no** |
| 17 | design-os | fork | **yes** | no | main | **no** |
| 18 | Lighthouse-AI | fork | **yes** | no | main | **no** |
| 19 | Smoke | fork | **yes** | no | main | **no** |

---

## Open Pull Requests (16 total, all Dependabot)

### CRITICAL: Docker Base Image Bumps (4 PRs)

These bump Python from 3.12-slim to **3.14-slim** -- a two-major-version jump. Test thoroughly before merging.

| Repo | PR# | Title | Created |
|------|-----|-------|---------|
| claude-superpowers | #10 | Bump python from 3.12-slim to 3.14-slim in /telegram-bot | 2026-03-04 |
| claude-superpowers | #9 | Bump python from 3.12-slim to 3.14-slim in /msg_gateway | 2026-03-04 |
| claude-superpowers | #8 | Bump python from 3.12-slim to 3.14-slim in /dashboard | 2026-03-04 |
| claude-superpowers | #7 | Bump python from 3.12-slim to 3.14-slim in /browser_engine | 2026-03-04 |

**Recommendation**: Do NOT auto-merge. Python 3.14 may have breaking changes. Pin to 3.13-slim instead, or test all 4 services against 3.14 first.

### HIGH: GitHub Actions Version Bumps (10 PRs)

These are safe to merge but should be batched per repo:

| Repo | PR# | Title | Created |
|------|-----|-------|---------|
| claude-superpowers | #6 | Bump actions/checkout from 4 to 6 | 2026-03-02 |
| claude-superpowers | #5 | Bump actions/setup-python from 5 to 6 | 2026-03-02 |
| claude-superpowers | #4 | Bump actions/upload-artifact from 4 to 7 | 2026-03-02 |
| homelab | #5 | Bump actions/checkout from 4.2.2 to 6.0.2 | 2026-03-02 |
| homelab | #4 | Bump dependabot/fetch-metadata from 2.2.0 to 2.5.0 | 2026-03-02 |
| homelab | #3 | Bump actions/setup-python from 5.6.0 to 6.2.0 | 2026-03-02 |
| k3s-cluster | #5 | Bump dependabot/fetch-metadata from 2.2.0 to 2.5.0 | 2026-03-02 |
| k3s-cluster | #4 | Bump actions/checkout from 4.2.2 to 6.0.2 | 2026-03-02 |
| k3s-cluster | #3 | Bump hashicorp/setup-terraform from 3.1.2 to 4.0.0 | 2026-03-02 |
| k3s-cluster | #2 | Bump actions/setup-python from 5.6.0 to 6.2.0 | 2026-03-02 |

### MEDIUM: Security Tool Bumps (2 PRs)

| Repo | PR# | Title | Created |
|------|-----|-------|---------|
| nexus-media | #2 | Bump actions/checkout from 4.2.2 to 6.0.2 | 2026-03-02 |
| nexus-media | #1 | Bump gitleaks/gitleaks-action from 2.3.6 to 2.3.9 | 2026-03-02 |

### LOW: Stale PRs on MurzDev_env (2 PRs, 10 days old)

| Repo | PR# | Title | Created |
|------|-----|-------|---------|
| MurzDev_env | #5 | Bump actions/setup-python from 5 to 6 | 2026-02-22 |
| MurzDev_env | #4 | Bump actions/checkout from 4 to 6 | 2026-02-22 |

---

## Open Issues

**None.** No actual GitHub Issues are open on any repository. The `open_issues_count` returned by the GitHub API includes open PRs, which accounts for all non-zero counts.

---

## Dependabot Security Alerts

**No active Dependabot vulnerability alerts** were found on any repository where alerts are enabled.

| Status | Repos |
|--------|-------|
| Alerts enabled, none found | claude-superpowers, homelab, k3s-cluster, nexus-media, dotfiles, docker-stacks, hommie, MurzDev_env, TrainingWheels, vmware-audit, zabbix_enchancement, claude-superpowers-skillhub, .github |
| Alerts disabled | claude-code-tresor, claude-code-skill-factory, agent-os |
| Archived (N/A) | design-os, Lighthouse-AI, Smoke |

**Action needed**: Enable Dependabot alerts on `claude-code-tresor`, `claude-code-skill-factory`, and `agent-os` (all forks -- alerts must be enabled manually on forks).

---

## Code Scanning Alerts

**No code scanning results** were found on any repository.

| Status | Repos |
|--------|-------|
| Not enabled | claude-superpowers (private, requires GitHub Advanced Security or public visibility) |
| No analysis found | homelab, k3s-cluster, nexus-media, dotfiles, claude-code-tresor, claude-code-skill-factory, agent-os, design-os, Lighthouse-AI, Smoke |

**Recommendation**: Enable CodeQL scanning via GitHub Actions on at least: `claude-superpowers`, `homelab`, `k3s-cluster`, `nexus-media`.

---

## Secret Scanning Alerts

**No active secret scanning alerts** found on any repository.

| Status | Repos |
|--------|-------|
| Disabled | claude-superpowers (private, free tier limitation) |
| Enabled, no alerts | homelab, k3s-cluster, nexus-media, dotfiles, claude-code-tresor, claude-code-skill-factory, agent-os |

---

## Branch Protection

| Repo | Branch | PR Reviews Required | Dismiss Stale Reviews | Status Checks |
|------|--------|--------------------|-----------------------|---------------|
| homelab | main | 1 approval | yes | none |
| k3s-cluster | main | 1 approval | yes | none |
| nexus-media | master | 1 approval | yes | none |
| dotfiles | main | 1 approval | yes | none |
| claude-superpowers | main | **N/A** (private repo, free tier) | -- | -- |
| All other repos | -- | **NONE** | -- | -- |

**Gaps**: Branch protection is not available on private repos under the free GitHub plan. Public repos without protection (agent-os, claude-code-tresor, claude-code-skill-factory, .github) should have rules added.

---

## Summary by Severity

### CRITICAL (action required immediately)
1. **4 Python 3.14 Docker base image PRs** on claude-superpowers -- do NOT auto-merge; test or pin to 3.13-slim first.

### HIGH (action required this week)
2. **10 GitHub Actions version bump PRs** across claude-superpowers, homelab, k3s-cluster -- safe to merge after CI passes. Batch per repo.
3. **Dependabot alerts disabled on 3 forked repos** (agent-os, claude-code-tresor, claude-code-skill-factory) -- enable manually.

### MEDIUM (address soon)
4. **No code scanning enabled** on any repo -- add CodeQL GitHub Actions workflow to key repos.
5. **2 nexus-media PRs** (checkout + gitleaks bump) -- merge after review.
6. **2 stale MurzDev_env PRs** (10 days old) -- merge or close.
7. **Secret scanning disabled** on private claude-superpowers repo (free tier limitation).

### LOW (nice to have)
8. **Issues disabled** on forked repos (agent-os, claude-code-tresor, claude-code-skill-factory) -- enable if using for issue tracking.
9. **No required status checks** on any repo's branch protection -- add CI as a required check on repos with workflows.
10. **Branch protection unavailable** on private repos (free plan) -- consider upgrading or making repos public if appropriate.

---

## Recommended Actions

1. **Merge GitHub Actions PRs** (10 PRs across 4 repos) -- batch merge per repo after verifying CI passes.
2. **Do NOT merge Python 3.14 PRs** -- pin Dockerfiles to `python:3.13-slim` and close these PRs, or test thoroughly first.
3. **Enable Dependabot alerts** on forked repos: `agent-os`, `claude-code-tresor`, `claude-code-skill-factory`.
4. **Add CodeQL workflow** to `claude-superpowers`, `homelab`, `k3s-cluster`, `nexus-media`.
5. **Add required status checks** to branch protection on repos with CI workflows.
6. **Merge stale MurzDev_env PRs** (#4, #5) or close if repo is inactive.
7. **Merge nexus-media PRs** (#1, #2) -- gitleaks version bump is a security tool update.

---

*Generated by Claude Code audit on 2026-03-04*
