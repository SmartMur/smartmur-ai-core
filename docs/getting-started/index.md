# Getting Started

This guide walks you through installing SmartMur Core, configuring the environment, and running your first commands.

---

## Prerequisites

- **Python 3.12+** (3.12 or 3.13 recommended)
- **Docker** and **Docker Compose** (for full stack: messaging gateway, browser engine, dashboard)
- **age** encryption tool (for vault)
- **Git**

### Install age

=== "Debian/Ubuntu"

    ```bash
    sudo apt update && sudo apt install -y age
    ```

=== "macOS"

    ```bash
    brew install age
    ```

Verify: `age --version && age-keygen --version`

---

## Installation

### From Source (recommended for development)

```bash
git clone https://github.com/SmartMur/claude-superpowers.git
cd claude-superpowers
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verify the CLI is available:

```bash
claw --version
# claude-superpowers 0.1.0
```

### With Docker (full stack)

After installing from source, bring up the Docker services:

```bash
docker compose up -d
```

This starts:

- **Redis** -- session and pubsub backend
- **Message Gateway** -- FastAPI service for Telegram, Slack, Discord, email
- **Dashboard** -- web UI at `http://localhost:8200`
- **Browser Engine** -- Playwright + Chromium at `http://localhost:8300`
- **Telegram Bot** -- inbound message handler

---

## Configuration

Copy the example environment file and edit it:

```bash
cp .env.example .env
$EDITOR .env
```

Key settings:

| Variable | Purpose | Required |
|----------|---------|----------|
| `VAULT_IDENTITY_FILE` | Path to age identity file | Yes (set by `claw vault init`) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot API token | For messaging |
| `TELEGRAM_DEFAULT_CHAT_ID` | Default Telegram chat | For messaging |
| `SLACK_BOT_TOKEN` | Slack bot token | For Slack integration |
| `DISCORD_BOT_TOKEN` | Discord bot token | For Discord integration |
| `REDIS_URL` | Redis connection URL | For full stack |
| `DASHBOARD_USER` | Dashboard login username | For dashboard |
| `DASHBOARD_PASS` | Dashboard login password | For dashboard |
| `HOME_ASSISTANT_URL` | Home Assistant API URL | For smart home |
| `HOME_ASSISTANT_TOKEN` | Home Assistant long-lived token | For smart home |

Or use the interactive setup wizard:

```bash
claw setup run
```

See [Configuration Reference](../reference/CONFIGURATION.md) for all options.

---

## First Steps

### 1. Check system status

```bash
claw status
```

This shows the health of all subsystems: vault, skills, cron, messaging, SSH, browser, watchers, and memory.

### 2. Initialize the vault

```bash
claw vault init
```

Store a credential:

```bash
claw vault set MY_API_KEY sk-example-key
claw vault list
```

### 3. Explore skills

```bash
# List all available skills
claw skill list

# Get details on a specific skill
claw skill info heartbeat

# Run a skill
claw skill run heartbeat
```

### 4. Create your first skill

```bash
claw skill create --name hello-world --description "My first skill" --type bash
```

Edit the generated script and run it:

```bash
claw skill run hello-world
```

### 5. Schedule a job

```bash
# Run heartbeat every 5 minutes
claw cron add --name "heartbeat" --type skill --command heartbeat --schedule "*/5 * * * *"

# List scheduled jobs
claw cron list
```

### 6. Send a message

```bash
# Check available channels
claw msg channels

# Send a test message (requires configured tokens)
claw msg send telegram "Hello from SmartMur Core!"
```

---

## Next Steps

- [CLI Command Reference](../reference/cli.md) -- all `claw` subcommands
- [Skills Reference](../reference/skills.md) -- skill system deep dive
- [Architecture Overview](../architecture/index.md) -- how components connect
- [Deployment Guide](../guides/DEPLOYMENT.md) -- production deployment
- [Security](../reference/SECURITY.md) -- security policy and practices
