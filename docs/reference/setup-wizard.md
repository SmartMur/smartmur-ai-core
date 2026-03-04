# Setup Wizard

## Overview

The setup wizard handles first-run configuration and environment bootstrapping for claude-superpowers. It checks prerequisites, creates the `.env` file from the shipped template, initializes the encrypted vault, sets up data directories, and optionally configures Telegram bot integration.

The wizard supports both interactive mode (prompts for each value) and non-interactive mode (uses defaults or values passed programmatically). Run it once after cloning the repo, or re-run individual steps as needed.

## Prerequisites

The wizard checks for the following tools:

| Tool | Required | Purpose |
|------|----------|---------|
| `python` (>= 3.12) | Yes | Runtime |
| `docker` | Yes | Container orchestration |
| `docker compose` | Yes | Service stack management |
| `redis-cli` | No | Message bus and caching |
| `age` | No | File encryption (vault) |
| `age-keygen` | No | Vault key generation |

Required tools must be present for the project to function. Optional tools enable additional features -- the wizard continues even if they are missing.

## Wizard Steps

When run in full (`claw setup run`), the wizard executes five steps in order:

1. **Prerequisite check** -- Verifies required and optional tools are installed. Warns about missing required tools but does not abort.
2. **Data directories** -- Creates the directory tree under `~/.claude-superpowers/` (cron output, logs, browser profiles, etc.).
3. **`.env` file** -- If `.env` does not already exist, creates it from `.env.example`. In interactive mode, prompts for each variable with the example value as default. Permissions are set to `0600`.
4. **Vault initialization** -- If the vault file does not already exist and `age-keygen` is available, generates an identity key and initializes the encrypted vault at `~/.claude-superpowers/vault.enc`.
5. **Telegram setup (optional)** -- Validates a Telegram Bot API token via the `getMe` endpoint, optionally sets a webhook URL, and records allowed chat IDs. Skipped in non-interactive mode unless a token is provided.

Steps that have already been completed (`.env` exists, vault exists) are detected and skipped with a status message.

## CLI Reference

All commands are under `claw setup`.

### `claw setup run`

Run the full setup wizard.

```bash
claw setup run
claw setup run --non-interactive
```

| Flag | Description |
|------|-------------|
| `--non-interactive` | Skip all prompts; use default values from `.env.example` |

### `claw setup check`

Check prerequisites only, without modifying anything.

```bash
claw setup check
```

```
         Prerequisite Check
+----------------+----------+----------+
| Tool           | Status   | Required |
+----------------+----------+----------+
| python         | found    | yes      |
| docker         | found    | yes      |
| docker-compose | found    | yes      |
| redis-cli      | found    | optional |
| age            | missing  | optional |
| age-keygen     | missing  | optional |
+----------------+----------+----------+
```

### `claw setup env`

Create the `.env` file from `.env.example`.

```bash
claw setup env
claw setup env --non-interactive
```

In interactive mode, you are prompted for each variable. Press Enter to accept the default. In non-interactive mode, all defaults are used as-is.

### `claw setup vault`

Initialize the encrypted vault.

```bash
claw setup vault
```

Requires `age-keygen` on PATH. Creates the identity file and vault store under `~/.claude-superpowers/`. If the vault already exists, this is a no-op.

### `claw setup telegram`

Configure Telegram bot integration.

```bash
claw setup telegram
claw setup telegram --token "123456:ABC-DEF..." --chat-ids "12345,67890"
claw setup telegram --token "123456:ABC-DEF..." --webhook-url "https://bot.example.com/webhook"
```

| Flag | Description |
|------|-------------|
| `--token` | Telegram Bot API token from BotFather |
| `--webhook-url` | Public HTTPS URL for webhook mode (optional) |
| `--chat-ids` | Comma-separated allowlist of chat IDs |

Without flags, the command prints setup instructions and prompts interactively.

## Configuration Variables

The `.env` file created by the wizard contains these groups:

| Group | Variables | Notes |
|-------|-----------|-------|
| LLM | `ANTHROPIC_API_KEY` | API key for Anthropic (optional if using CLI only) |
| Messaging | `SLACK_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_DEFAULT_CHAT_ID`, `DISCORD_BOT_TOKEN`, `SMTP_*` | Channel adapter credentials |
| Dashboard | `DASHBOARD_USER`, `DASHBOARD_PASS`, `DASHBOARD_SECRET` | Web dashboard authentication |
| Infrastructure | `REDIS_URL` | Redis connection string |
| Vault | `VAULT_IDENTITY_FILE` | Path to the age identity key |
| Telegram Bot | `ALLOWED_CHAT_IDS`, `TELEGRAM_SESSION_TTL`, `TELEGRAM_MAX_HISTORY`, `TELEGRAM_MODE`, `TELEGRAM_WEBHOOK_*` | Bot behavior and security |
| Home Automation | `HOME_ASSISTANT_URL`, `HOME_ASSISTANT_TOKEN` | Home Assistant REST API |

See `.env.example` for the full list with inline comments.

## Python API

### SetupWizard

```python
from superpowers.setup_wizard import SetupWizard

# Interactive mode
wizard = SetupWizard()
summary = wizard.run()

# Non-interactive with pre-filled values
wizard = SetupWizard(
    non_interactive=True,
    values={
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF...",
        "REDIS_URL": "redis://redis:6379/0",
    },
)
summary = wizard.run()
```

### Individual Steps

```python
wizard = SetupWizard()

# Check prerequisites
results = wizard.check_prereqs()
# {"python": True, "docker": True, "age": False, ...}

# Create .env
env_path = wizard.create_env()

# Initialize vault
ok = wizard.init_vault()

# Configure Telegram
tg = wizard.setup_telegram(bot_token="123456:ABC-DEF...")
# {"valid": True, "bot_info": {...}, "webhook_set": False, "config": {...}}

# Create data directories
wizard.ensure_dirs()
```

## Examples

### First-Time Setup on a Fresh Server

```bash
cd /home/ray/claude-superpowers
claw setup run
```

Follow the prompts to fill in your Slack token, Telegram token, Redis URL, and dashboard credentials. The wizard creates `.env`, initializes the vault, and validates your Telegram bot.

### Non-Interactive Setup in CI

```bash
claw setup run --non-interactive
```

All values default to what is in `.env.example`. Override specific variables by editing `.env.example` beforehand or by running individual subcommands:

```bash
claw setup env --non-interactive
claw setup vault
```

### Reconfigure Telegram After Initial Setup

```bash
claw setup telegram --token "NEW_TOKEN" --chat-ids "12345,67890"
```

This validates the new token and prints the bot username. Update `.env` with the returned config values.

## Troubleshooting

**"Missing required tools: docker"** -- Install Docker and ensure the `docker` binary is on your PATH. The wizard warns but does not abort, so other steps still complete.

**".env.example not found"** -- The wizard expects `.env.example` in the project root. If it was deleted, restore it from git: `git checkout -- .env.example`.

**"Vault initialization skipped (age-keygen not found)"** -- Install `age` (`apt install age` on Debian/Ubuntu, `brew install age` on macOS) and re-run `claw setup vault`.

**Telegram token invalid** -- Verify the token with BotFather. The wizard calls the Telegram `getMe` API to validate. Network issues or an incorrect token both result in a "skipped or token invalid" message.

## Modules

| Module | Path | Purpose |
|--------|------|---------|
| `setup_wizard` | `superpowers/setup_wizard.py` | Wizard orchestration: prereq checks, `.env` creation, vault init, Telegram setup |
| `cli_setup` | `superpowers/cli_setup.py` | Click commands for `claw setup` |
