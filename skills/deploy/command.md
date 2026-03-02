# Deploy

Deploy claude-superpowers locally — pull latest code, install dependencies, rebuild Docker containers, and run health checks.

Execute: `python3 skills/deploy/run.py`

## What it does

1. `git pull --ff-only` (safe fast-forward only)
2. `pip install -e ".[dev]"` in the project venv
3. `docker compose build --no-cache`
4. `docker compose up -d`
5. Health check on dashboard `/health` endpoint
6. Quick test suite (`pytest -x`)

## Exit codes

- **0** — success
- **1** — health check failed
- **2** — error (git, docker, pip, or test failure)

## Notifications

Sends Telegram notifications at start, completion, and on error (when TELEGRAM_BOT_TOKEN and TELEGRAM_DEFAULT_CHAT_ID are configured).

All actions are recorded to the audit log.
