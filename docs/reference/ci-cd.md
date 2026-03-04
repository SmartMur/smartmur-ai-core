# CI/CD Pipeline

This document describes the CI/CD pipeline for claude-superpowers.

## Pipeline Overview

```
Push/PR to main       Tag v*              Manual / Post-release
      |                  |                        |
  [CI Pipeline]    [Release Pipeline]      [Deploy Pipeline]
      |                  |                        |
  lint + test      test -> docker build      SSH -> server
                   -> GitHub release         git pull + rebuild
                                             health check + notify
```

## Workflows

### CI (`ci.yml`)

Triggered on every push to `main` and on pull requests targeting `main`.

**Jobs:**

- **lint** -- Runs `ruff check .` and `ruff format --check .` to enforce code quality and consistent formatting.
- **test** -- Matrix build across Python 3.12 and 3.13. Runs the full test suite with known exclusions (telegram concurrency hang, vault tests requiring `age-keygen`). Uploads JUnit XML results as artifacts on failure.
- **security** -- Runs `detect-secrets` to scan for accidentally committed secrets. Runs ruff security rules (`S` category) as a best-effort check.

**Best practices applied:**
- Dependency caching via `actions/setup-python` with `cache: 'pip'`
- Concurrency control: cancels in-progress runs on the same branch
- Matrix `fail-fast: false` so all Python versions run even if one fails
- Test artifacts uploaded on failure for debugging

### Release (`release.yml`)

Triggered when a version tag is pushed (e.g., `v1.0.0`).

**Jobs:**

- **test** -- Same test suite as CI (gate before release).
- **docker** -- Builds and pushes Docker images for all services (msg-gateway, dashboard, telegram-bot) to GitHub Container Registry (`ghcr.io`). Tags images with both the version number and `latest`.
- **release** -- Creates a GitHub release with auto-generated release notes.

**Docker images are tagged as:**
```
ghcr.io/<owner>/claude-superpowers/msg-gateway:1.0.0
ghcr.io/<owner>/claude-superpowers/msg-gateway:latest
```

### Deploy (`deploy.yml`)

Triggered manually via `workflow_dispatch` or automatically after a successful release.

**Steps:**
1. Configures SSH using secrets
2. SSHs to the deploy target
3. Runs `git pull --ff-only`
4. Installs Python dependencies
5. Builds and restarts Docker containers
6. Runs a health check against the dashboard
7. Sends Telegram notification on success or failure

## Required GitHub Secrets

| Secret | Description | Used in |
|--------|-------------|---------|
| `DEPLOY_HOST` | IP or hostname of the Docker server | deploy.yml |
| `DEPLOY_USER` | SSH username on the server | deploy.yml |
| `DEPLOY_SSH_KEY` | Private SSH key (ed25519 recommended) | deploy.yml |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications | deploy.yml |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for notifications | deploy.yml |
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions | release.yml |

## Setting Up the Repository

1. Create a GitHub repository and push the code:
   ```bash
   git remote add origin git@github.com:<owner>/claude-superpowers.git
   git push -u origin main
   ```

2. Add secrets in the repo settings (Settings > Secrets and variables > Actions):
   - `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (optional, for notifications)

3. Create a deployment environment named `production` (Settings > Environments) if you want approval gates.

4. Push a tag to trigger a release:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

## Local Deploy via `/deploy` Skill

For deployments from the local machine (without GitHub Actions), use the deploy skill:

```bash
# Via the claw CLI
python3 skills/deploy/run.py

# Or via Claude Code slash command
/deploy
```

The deploy skill performs:
1. `git pull --ff-only` (safe pull only, no merge commits)
2. `pip install -e ".[dev]"` in the venv
3. `docker compose build --no-cache`
4. `docker compose up -d`
5. Health check (curl dashboard /health)
6. Quick test suite (pytest -x, stops on first failure)

**Exit codes:**
- `0` -- success
- `1` -- health check failed
- `2` -- error (git, docker, pip, or test failure)

All steps are logged to the audit trail and Telegram notifications are sent (when configured).

## Best Practices Followed

- **No `shell=True`** in Python subprocess calls
- **Fast-forward only** git pulls prevent accidental merge commits
- **Concurrency controls** prevent parallel deploys or duplicate CI runs
- **Secrets never logged** -- SSH keys cleaned up after use
- **Graceful degradation** -- Telegram notifications are best-effort (never block deploy)
- **Immutable tags** -- Docker images tagged with version + latest
- **Build cache** -- GitHub Actions cache for pip and Docker layers
- **Matrix testing** -- Multiple Python versions tested before release
- **Artifact retention** -- Test results saved for 7 days on failure
