# Final Naming Map v1 (Approval Draft)

**Date**: 2026-03-04  
**Org**: `SmartMur`  
**Status**: Draft for approval. No renames executed.

## 1. Naming Standard v1

- Canonical slug format: `smartmur-{domain}-{purpose}`
- Keep exceptions:
  - `.github` (GitHub special repo)
  - Upstream forks where lineage/discoverability matters
  - Archived repos (keep stable, add archive topics)

## 2. Group Model v1

- `Core Platform`
- `AI Automation`
- `Homelab Infrastructure`
- `Homelab Services`
- `Observability & Audit`
- `Developer Experience`
- `Org Meta`
- `Forks (Upstream Tracking)`
- `Archive`

## 3. Repo-by-Repo Naming Map v1

| Current Repo | Proposed Repo | Action | Group | Visibility | Proposed Topics |
|---|---|---|---|---|---|
| `claude-superpowers` | `smartmur-ai-core` | `RENAME` | Core Platform | private | `smartmur`, `domain-ai`, `type-platform`, `ai-automation`, `orchestration`, `python`, `self-hosted`, `homelab-ops` |
| `MurzDev_env` | `smartmur-ai-lab` | `RENAME` | AI Automation | private | `smartmur`, `domain-ai`, `type-lab`, `multi-agent`, `llmops`, `devops`, `security`, `provider-agnostic` |
| `TrainingWheels` | `smartmur-labs-playground` | `RENAME` | AI Automation | private | `smartmur`, `domain-labs`, `type-playground`, `docker`, `self-hosted`, `governance`, `experiments` |
| `claude-superpowers-skillhub` | `smartmur-ai-skillhub` | `RENAME` | AI Automation | private | `smartmur`, `domain-ai`, `type-knowledge`, `skills`, `prompts`, `automation`, `agent-tooling` |
| `homelab` | `smartmur-homelab-platform` | `RENAME` | Homelab Infrastructure | public | `smartmur`, `domain-homelab`, `type-platform`, `docker-compose`, `self-hosted`, `infra-automation`, `security`, `monitoring` |
| `k3s-cluster` | `smartmur-homelab-k3s` | `RENAME` | Homelab Infrastructure | public | `smartmur`, `domain-homelab`, `type-iac`, `k3s`, `kubernetes`, `terraform`, `ansible`, `gitops` |
| `docker-stacks` | `smartmur-homelab-stacks` | `RENAME` | Homelab Infrastructure | private | `smartmur`, `domain-homelab`, `type-stack`, `docker-compose`, `self-hosted`, `service-catalog`, `templates` |
| `nexus-media` | `smartmur-homelab-media` | `RENAME` | Homelab Services | public | `smartmur`, `domain-homelab`, `type-service`, `media-stack`, `arr-stack`, `plex`, `jellyfin`, `self-hosted` |
| `hommie` | `smartmur-network-audit` | `RENAME` | Observability & Audit | private | `smartmur`, `domain-observability`, `type-audit`, `network-audit`, `unifi`, `cisco`, `fastapi`, `timescaledb` |
| `vmware-audit` | `smartmur-vmware-audit` | `RENAME` | Observability & Audit | private | `smartmur`, `domain-observability`, `type-audit`, `vmware`, `inventory`, `compliance`, `python`, `security` |
| `zabbix_enchancement` | `smartmur-zabbix-topology` | `RENAME` | Observability & Audit | private | `smartmur`, `domain-observability`, `type-tool`, `zabbix`, `topology`, `blast-radius`, `network-visualization` |
| `dotfiles` | `smartmur-dev-dotfiles` | `RENAME` | Developer Experience | public | `smartmur`, `domain-devx`, `type-bootstrap`, `dotfiles`, `macos`, `zsh`, `developer-environment`, `tooling` |
| `.github` | `.github` | `KEEP` | Org Meta | public | `smartmur`, `domain-org`, `type-meta`, `community-health`, `org-profile` |
| `claude-code-skill-factory` | `claude-code-skill-factory` | `KEEP (fork)` | Forks (Upstream Tracking) | public | `smartmur`, `domain-forks`, `type-fork`, `upstream-sync`, `skills`, `automation` |
| `claude-code-tresor` | `claude-code-tresor` | `KEEP (fork)` | Forks (Upstream Tracking) | public | `smartmur`, `domain-forks`, `type-fork`, `upstream-sync`, `agents`, `orchestration` |
| `agent-os` | `agent-os` | `KEEP (fork)` | Forks (Upstream Tracking) | public | `smartmur`, `domain-forks`, `type-fork`, `upstream-sync`, `agent-framework` |
| `design-os` (archived) | `design-os` | `KEEP (archived fork)` | Archive | public | `smartmur`, `domain-archive`, `type-archive`, `type-fork` |
| `Lighthouse-AI` (archived) | `Lighthouse-AI` | `KEEP (archived fork)` | Archive | public | `smartmur`, `domain-archive`, `type-archive`, `type-fork`, `local-ai` |
| `Smoke` (archived) | `Smoke` | `KEEP (archived fork)` | Archive | public | `smartmur`, `domain-archive`, `type-archive`, `type-fork`, `security-research` |

## 4. Homelab Service Categories v1 (for `smartmur-homelab-platform`)

Use these as internal service tags in docs/README, project boards, and labels.

- `category-media-arr`: Sonarr, Radarr, Prowlarr, Lidarr, Bazarr, Overseerr, Jellyseerr
- `category-media-runtime`: Plex, Jellyfin, Emby, transcoding/tooling
- `category-download-clients`: qBittorrent, SABnzbd, NZBGet, VPN sidecars
- `category-network-edge`: reverse proxy, DNS, certs, VPN, ingress
- `category-platform-core`: Docker, k3s, storage, backups, host lifecycle
- `category-observability`: Zabbix, Prometheus, Grafana, Loki, alerting
- `category-security`: auth, secrets, SSO, vulnerability scanners, hardening
- `category-automation`: schedulers, bots, maintenance jobs, policy checks
- `category-data-services`: databases, cache, search, stateful service support
- `category-productivity`: dashboards, docs, knowledge, utilities

## 5. Rollout Order (when approved)

1. Rename private repos first (low external blast radius).
2. Update topics/org pinning.
3. Rename public repos one-by-one with README redirect notes.
4. Keep fork names stable unless later decoupled from upstream.
5. Keep archived repos unchanged.

## 6. Approval Prompts

Approve/reject each item below before execution:

1. Standard prefix: `smartmur-`
2. Rename `claude-superpowers` -> `smartmur-ai-core`
3. Rename `homelab` -> `smartmur-homelab-platform`
4. Rename `nexus-media` -> `smartmur-homelab-media`
5. Keep all active forks with current names
6. Keep all archived repos unchanged
