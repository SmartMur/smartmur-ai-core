# Messaging — Phase 3

Multi-channel messaging for cron jobs, skills, and the CLI.

## Supported Channels

| Channel  | Adapter         | Credentials                          |
|----------|-----------------|--------------------------------------|
| Slack    | `slack_sdk`     | `SLACK_BOT_TOKEN`                    |
| Telegram | `urllib` stdlib  | `TELEGRAM_BOT_TOKEN`                 |
| Discord  | `urllib` stdlib  | `DISCORD_BOT_TOKEN`                  |
| Email    | `smtplib` stdlib | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `SMTP_PORT`, `SMTP_FROM` |

## Quick Start

```bash
# 1. Add credentials to .env
echo 'SLACK_BOT_TOKEN=xoxb-...' >> .env

# 2. Check which channels are configured
claw msg channels

# 3. Test connectivity
claw msg test slack

# 4. Send a message
claw msg send slack "#alerts" "deploy complete"
```

## CLI Reference

```
claw msg channels              # List channels + credential status
claw msg test <channel>        # Verify credentials work
claw msg send <ch> <target> <msg>  # Send to a specific channel
claw msg profiles              # List notification profiles
claw msg notify <profile> <msg>    # Fan-out to all profile targets
```

## Notification Profiles

Profiles map a name to one or more channel+target pairs. Create `~/.claude-superpowers/profiles.yaml`:

```yaml
critical:
  - channel: slack
    target: "#alerts"
  - channel: telegram
    target: "123456789"

info:
  - channel: slack
    target: "#general"

daily-digest:
  - channel: email
    target: admin@example.com
  - channel: slack
    target: "#daily"
```

Usage:
```bash
claw msg notify critical "PVE1 is down"
```

## Cron Integration

Route cron job output to a channel or profile:

```bash
# Direct channel routing
claw cron add backup-alert "daily at 09:00" --type shell \
  --command "/usr/local/bin/backup.sh" --output "slack:#alerts"

# Profile routing
claw cron add health-check "every 30m" --type skill \
  --command heartbeat --output critical
```

Output format: `--output <channel>:<target>` (direct) or `--output <profile>` (profile name).

When `output_channel` is set on a job, the cron engine:
1. Always writes output to the log file (default behavior)
2. Additionally sends a formatted message to the specified channel/profile
3. Messaging failures are silently caught — they never break job execution

## Architecture

```
superpowers/channels/
├── base.py       # Channel, ChannelType, SendResult, ChannelError
├── registry.py   # ChannelRegistry — factory with lazy instantiation
├── slack.py      # SlackChannel (slack_sdk.WebClient)
├── telegram.py   # TelegramChannel (urllib → Bot API)
├── discord.py    # DiscordChannel (urllib → REST API v10)
└── email.py      # EmailChannel (smtplib + STARTTLS)

superpowers/profiles.py   # ProfileManager — YAML-based profile dispatch
superpowers/cli_msg.py    # Click commands: send, test, channels, profiles, notify
```

## FastAPI Gateway (optional)

For Docker-based deployments, the `msg_gateway/` service provides an HTTP API:

```bash
docker compose up -d
curl localhost:8100/health
curl -X POST localhost:8100/send \
  -H "Content-Type: application/json" \
  -d '{"channel": "slack", "target": "#test", "message": "hello"}'
```

The gateway also includes a Redis pub/sub consumer for async message dispatch.
