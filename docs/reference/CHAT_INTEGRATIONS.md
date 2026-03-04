# Chat Integrations

Comprehensive guide to configuring, operating, and extending the multi-channel messaging system in claude-superpowers. Covers all five supported channels, the message gateway architecture, notification profiles, inbound triggers, security controls, and the adapter contract for adding new channels.

---

## Table of Contents

1. [Overview](#overview)
2. [Channel Comparison Matrix](#channel-comparison-matrix)
3. [Slack Integration](#slack-integration)
4. [Telegram Integration](#telegram-integration)
5. [Discord Integration](#discord-integration)
6. [Email Integration](#email-integration)
7. [iMessage Integration](#imessage-integration)
8. [Notification Profiles](#notification-profiles)
9. [Inbound Triggers](#inbound-triggers)
10. [Security](#security)
11. [Testing and Debugging](#testing-and-debugging)
12. [Adding a New Channel](#adding-a-new-channel)

---

## Overview

The messaging subsystem has three layers: **channel adapters** for outbound delivery, a **message gateway** for HTTP-based dispatch and inbound webhook processing, and a **Redis pub/sub bus** for asynchronous message routing between services.

### Architecture

```
                    CLI / Skills / Cron / Workflows
                              |
                    +---------+---------+
                    |   claw msg send   |
                    |   claw msg notify |
                    +---------+---------+
                              |
                    +---------+---------+
                    |  ChannelRegistry  |  <-- lazy instantiation per channel
                    +---------+---------+
                              |
          +-------+-----------+-----------+-------+
          |       |           |           |       |
          v       v           v           v       v
      +-------+ +-------+ +-------+ +-------+ +--------+
      | Slack | | Tele- | | Disc- | | Email | | iMsg   |
      |Channel| | gram  | | ord   | |Channel| |Channel |
      |       | |Channel| |Channel| |       | |(macOS) |
      +-------+ +-------+ +-------+ +-------+ +--------+
          |       |           |           |       |
          v       v           v           v       v
      slack_sdk  urllib     urllib     smtplib  osascript
      WebClient  Bot API   REST v10   STARTTLS AppleScript

    +-------------------------------------------------+
    |           Message Gateway (FastAPI)              |
    |   port 8100 — Docker service "msg-gateway"      |
    |                                                  |
    |  POST /send         — outbound dispatch          |
    |  GET  /channels     — list configured channels   |
    |  GET  /health       — channel status             |
    |  POST /webhook/*    — inbound webhook receivers  |
    +-------------------------------------------------+
                              |
                    +---------+---------+
                    |    Redis Pub/Sub  |
                    | outbound:{channel}|
                    +-------------------+
```

### How Messages Flow

**Outbound (sending):**

1. A caller invokes `claw msg send <channel> <target> <message>`, a Python API call, or a POST to the gateway's `/send` endpoint.
2. `ChannelRegistry` lazily instantiates the appropriate adapter from `Settings`.
3. The adapter's `send()` method delivers the message via the channel's native protocol.
4. A `SendResult` dataclass is returned indicating success or failure.

**Outbound via Redis (async):**

1. Any service publishes a JSON message to the `outbound:{channel}` Redis topic.
2. The `MessageBus` subscriber picks it up, resolves the adapter, and calls `send()`.
3. Results are logged but not returned to the publisher (fire-and-forget).

**Inbound (receiving):**

1. Telegram uses long-polling (default) or webhooks (configurable).
2. Slack and Discord use webhook endpoints at `/webhook/slack` and `/webhook/discord`.
3. All inbound messages pass through the `WebhookSignatureMiddleware` for signature validation.
4. Messages are matched against trigger rules. Matches are routed to shell commands, LLM provider calls, or skills. Non-matches on Telegram are routed to the configured chat model for conversational responses.

### Key Source Files

| File | Purpose |
|------|---------|
| `superpowers/channels/base.py` | `Channel`, `ChannelType`, `SendResult`, `ChannelError` base classes |
| `superpowers/channels/registry.py` | `ChannelRegistry` -- factory with lazy instantiation |
| `superpowers/channels/slack.py` | Slack adapter (`slack_sdk.WebClient`) |
| `superpowers/channels/telegram.py` | Telegram outbound adapter (`urllib` + Bot API) |
| `superpowers/channels/discord.py` | Discord adapter (`urllib` + REST API v10) |
| `superpowers/channels/email.py` | Email adapter (`smtplib` + STARTTLS) |
| `superpowers/channels/imessage.py` | iMessage adapter (macOS `osascript`) |
| `superpowers/profiles.py` | `ProfileManager` -- YAML-based notification fan-out |
| `superpowers/cli_msg.py` | Click commands: `send`, `test`, `channels`, `profiles`, `notify` |
| `msg_gateway/app.py` | FastAPI gateway application |
| `msg_gateway/bus.py` | Redis pub/sub consumer (`MessageBus`) |
| `msg_gateway/middleware.py` | Webhook signature validation + rate limiting |
| `msg_gateway/inbound.py` | `TriggerManager`, `TelegramPoller`, `InboundListener` |
| `msg_gateway/models.py` | Pydantic request/response models |
| `msg_gateway/channels/base.py` | `ChannelAdapter` abstract base for inbound adapters |
| `msg_gateway/telegram/` | Full Telegram bot package (16 modules) |
| `telegram-bot/entrypoint.py` | Telegram bot Docker entry point |

---

## Channel Comparison Matrix

| Feature | Slack | Telegram | Discord | Email | iMessage |
|---------|-------|----------|---------|-------|----------|
| **Send messages** | Yes | Yes | Yes | Yes | Yes |
| **Receive messages** | Webhook | Polling + Webhook | Webhook | No | No |
| **Bidirectional AI chat** | No | Yes | No | No | No |
| **Attachments (inbound)** | No | Photos, documents, PDFs | No | No | No |
| **Voice transcription** | No | Yes (whisper.cpp) | No | No | No |
| **Typing indicators** | No | Yes | No | N/A | No |
| **Reactions** | No | Yes (emoji) | No | N/A | No |
| **Inline keyboards** | No | Yes | No | N/A | No |
| **Session history** | No | Yes (Redis/in-memory) | No | No | No |
| **Concurrency control** | No | Yes (per-chat + global) | No | No | No |
| **Webhook signature** | HMAC-SHA256 (v0) | Secret token header | Ed25519 (PyNaCl) | N/A | N/A |
| **Auth mechanism** | Bot token (xoxb-) | Bot token + chat ID allowlist | Bot token | SMTP login | macOS user session |
| **SDK/library** | `slack_sdk` | `urllib` (stdlib) | `urllib` (stdlib) | `smtplib` (stdlib) | `osascript` (subprocess) |
| **External dependency** | `slack_sdk` package | None | None (PyNaCl for webhooks) | None | macOS only |
| **Retry with backoff** | No | Yes (3 retries, exponential) | No | No | No |
| **Rate limit handling** | Via `slack_sdk` | Yes (`Retry-After` header) | No | No | No |
| **Parse mode** | Slack mrkdwn | Markdown / MarkdownV2 | Plain text | Plain text (subject+body) | Plain text |
| **Target format** | Channel name (`#alerts`) | Chat ID (`123456789`) | Channel ID (snowflake) | Email address | Phone/email/contact name |
| **Max message length** | 40,000 chars | 4,096 chars | 2,000 chars | Unlimited | N/A |
| **Docker service** | Via msg-gateway | Dedicated container | Via msg-gateway | Via msg-gateway | N/A (host only) |

---

## Slack Integration

### Setup

1. **Create a Slack App** at [api.slack.com/apps](https://api.slack.com/apps).
2. Under **OAuth & Permissions**, add the following bot token scopes:
   - `chat:write` -- send messages to channels
   - `chat:write.public` -- send to channels without joining first
3. Install the app to your workspace.
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`).

### Configuration

Add to `.env`:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
```

**Optional** (for inbound webhook validation):

```bash
SLACK_SIGNING_SECRET=your-signing-secret-here
```

The signing secret is found under **Basic Information** in your Slack app settings. It is required if you plan to receive inbound webhooks at `/webhook/slack`.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | Yes (for outbound) | `""` | Bot User OAuth Token from Slack app |
| `SLACK_SIGNING_SECRET` | Yes (for inbound) | `""` | HMAC signing secret for webhook validation |

### Sending Messages

**CLI:**

```bash
claw msg send slack "#alerts" "Deployment complete"
claw msg send slack "#general" "Morning health check passed"
```

**Python:**

```python
from superpowers.channels.slack import SlackChannel

ch = SlackChannel(bot_token="xoxb-...")
result = ch.send("#alerts", "Deployment complete")
print(result.ok, result.message)  # True, "ts=1234567890.123456"
```

**HTTP API:**

```bash
curl -X POST http://localhost:8100/send \
  -H "Content-Type: application/json" \
  -d '{"channel": "slack", "target": "#alerts", "message": "deploy complete"}'
```

**Redis pub/sub:**

```bash
redis-cli PUBLISH outbound:slack '{"target": "#alerts", "message": "deploy complete"}'
```

### Target Format

Targets are Slack channel names (e.g., `#alerts`, `#general`) or user IDs (e.g., `U0123ABCDEF`) for direct messages. The channel name must include the `#` prefix for public channels.

### Connection Test

```bash
claw msg test slack
# OK slack -- bot=superpowers-bot, team=my-workspace
```

The test calls `auth.test` to verify the token is valid and returns the bot username and team name.

### Limitations

- **Outbound only** (by default). Inbound support requires configuring the webhook endpoint and signing secret.
- No retry logic in the outbound adapter. Transient failures from the Slack API are surfaced as `SendResult.ok=False`.
- The `slack_sdk` package must be installed separately (`pip install slack_sdk`). If missing, `send()` returns an error rather than raising an exception.
- No threading or rich formatting support -- messages are sent as plain text via `chat.postMessage`.

---

## Telegram Integration

Telegram is the most feature-rich integration, with a full bidirectional bot supporting AI conversations, skill execution, voice transcription, photo/document ingestion, session management, inline keyboards, and concurrency control.

### Setup

1. **Create a bot** with [@BotFather](https://t.me/BotFather) on Telegram:
   - Send `/newbot` and follow the prompts.
   - Copy the HTTP API token.
2. **Find your chat ID**: Send any message to the bot and check the application logs. The bot logs rejected chat IDs, which you can then add to the allowlist.
3. **Configure the allowlist** in `.env`.

### Configuration

Add to `.env`:

```bash
# Required
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ALLOWED_CHAT_IDS=123456789,987654321

# Optional
TELEGRAM_DEFAULT_CHAT_ID=123456789
TELEGRAM_SESSION_TTL=3600
TELEGRAM_MAX_HISTORY=20
TELEGRAM_MAX_PER_CHAT=2
TELEGRAM_MAX_GLOBAL=5
TELEGRAM_QUEUE_OVERFLOW=10
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | `""` | Bot API token from @BotFather |
| `TELEGRAM_DEFAULT_CHAT_ID` | No | `""` | Default chat ID for outbound notifications |
| `ALLOWED_CHAT_IDS` | Yes | `""` | Comma-separated allowlist. **If empty, all messages are rejected.** |
| `TELEGRAM_SESSION_TTL` | No | `3600` | Conversation history TTL in seconds |
| `TELEGRAM_MAX_HISTORY` | No | `20` | Maximum messages retained per chat session |
| `TELEGRAM_MAX_PER_CHAT` | No | `2` | Maximum concurrent jobs per chat |
| `TELEGRAM_MAX_GLOBAL` | No | `5` | Maximum concurrent jobs across all chats |
| `TELEGRAM_QUEUE_OVERFLOW` | No | `10` | Maximum queued jobs before rejecting new requests |
| `TELEGRAM_MODE` | No | `polling` | `polling` or `webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | No | `""` | Secret token for webhook verification |
| `TELEGRAM_WEBHOOK_URL` | No | `""` | Public HTTPS URL for the webhook endpoint |
| `TELEGRAM_ADMIN_CHAT_ID` | No | `""` | Admin chat ID for access request notifications |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis for persistent session storage |

### Polling Mode (Default)

In polling mode, the bot uses Telegram's `getUpdates` long-polling endpoint. This is the simplest setup and requires no public-facing server.

```bash
# Start the bot directly
python -m telegram-bot.entrypoint

# Or via Docker Compose
docker compose up telegram-bot
```

The polling loop:
1. Calls `getUpdates` with a 30-second timeout.
2. Parses each update into typed dataclasses (`Update`, `Message`, `CallbackQuery`).
3. Routes through the authentication gate.
4. Dispatches to the appropriate handler (commands, callbacks, triggers, conversation).

### Webhook Mode

Webhook mode is more efficient for high-traffic bots. It requires a publicly accessible HTTPS endpoint.

```bash
# .env configuration
TELEGRAM_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://bot.example.com/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=a-random-secret-string
```

When `TELEGRAM_MODE=webhook`:
1. The `InboundListener` registers the poller with the FastAPI gateway app instead of starting a polling loop.
2. A `setWebhook` API call tells Telegram where to send updates.
3. The `POST /webhook/telegram` endpoint in the gateway receives updates.
4. The `X-Telegram-Bot-Api-Secret-Token` header is validated against `TELEGRAM_WEBHOOK_SECRET`.
5. Updates are parsed and dispatched through the same pipeline as polling mode.

### Bot Commands

The bot registers commands with Telegram via `setMyCommands` on startup, providing autocomplete in the client.

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with bot introduction |
| `/help` | List all available commands |
| `/status` | Show system status (mode, history, cron) |
| `/skills` | List installed skills with inline keyboard |
| `/run <skill>` | Execute a skill by name |
| `/mode [chat\|skill]` | Switch between chat and skill mode |
| `/history` | Show recent conversation history |
| `/reset` | Clear conversation history |
| `/cancel` | Cancel the currently running job |

### Chat Mode (Default)

Free-form messages are sent to the configured chat provider (from `CHAT_MODEL`, with optional OpenAI fallback) with conversation history as context. The bot maintains a sliding window of the last N messages (configurable, default 20) per chat, stored in Redis (or in-memory fallback).

The conversation flow:
1. User sends a text message.
2. Bot acknowledges with a thumbs-up reaction (fire-and-forget).
3. Message is added to session history.
4. Concurrency gate checks if a slot is available.
5. A background thread sends a "typing" indicator and calls the configured LLM provider.
6. The response is added to session history and chunked for delivery.

### Skill Mode

Messages are routed through the intake pipeline instead of direct LLM chat. The bot:
1. Extracts requirements from the message text.
2. Maps to available skills.
3. Executes with progress callbacks sent to the chat.
4. Reports results.

Switch modes with `/mode chat` or `/mode skill`, or use the inline keyboard from `/mode`.

### Reactions and Typing Indicators

- **Reactions**: The bot sends a thumbs-up emoji reaction on every received message using `setMessageReaction`. This is fire-and-forget -- failures are silently ignored.
- **Typing indicators**: The bot sends a `sendChatAction(typing)` call before starting any long-running operation (LLM call, skill execution, attachment processing).

### Photo and Document Ingestion

The bot handles three types of attachments:

**Photos**: Downloads the largest available size, describes it using the configured LLM provider (base64 image input), and routes the description through the conversation pipeline. Captions are included if present.

**Text documents**: Downloads and reads text-based files (plain text, CSV, HTML, Markdown, JSON, XML). Content is truncated to 10,000 characters.

**PDF documents**: Extracted using `pdftotext` (poppler-utils) or PyPDF2 as fallback. Up to 20 pages, truncated to 10,000 characters.

Supported MIME types for text extraction:
- `text/plain`, `text/csv`, `text/html`, `text/markdown`
- `application/json`, `application/xml`, `text/xml`
- `application/pdf`
- `image/jpeg`, `image/png`, `image/gif`, `image/webp`

Maximum file size: 20 MB (Telegram Bot API limit).

### Voice Transcription

Voice messages are transcribed using whisper.cpp (local, no API key):

1. Bot receives a voice/audio message.
2. Downloads the file via Telegram Bot API (`getFile` + file download).
3. Converts to 16kHz mono WAV using `ffmpeg`.
4. Transcribes using `whisper-cli` with the `ggml-base.en` model.
5. Sends the transcription back to the chat.
6. If the transcription contains speech, routes it to the configured LLM provider for a response.

**Requirements:**
- `ffmpeg` -- audio format conversion
- `whisper-cli` -- whisper.cpp binary (Debian: `apt install whisper.cpp`)
- Model file at `~/.claude-superpowers/models/ggml-base.en.bin`

### Session Management

Conversation history is stored per chat ID with a configurable sliding window and TTL:

| Storage | When Used | Persistence |
|---------|-----------|-------------|
| Redis | When `REDIS_URL` is reachable | Survives bot restarts; TTL-based expiry |
| In-memory dict | Redis unavailable | Lost on restart; manual TTL enforcement |

Redis key format: `tg:session:{chat_id}`

Operations:
- `add(chat_id, role, content)` -- append to history, trim to window size, refresh TTL
- `get(chat_id)` -- retrieve history entries
- `clear(chat_id)` -- delete all history for a chat
- `format_context(chat_id)` -- format as `Human: ... / Assistant: ...` for the active LLM provider

### Chat Verification

When an unknown user sends `/start`:

1. The bot checks if their chat ID is on the allowlist.
2. If not, sends "access request pending" and stores the request.
3. If `TELEGRAM_ADMIN_CHAT_ID` is set, notifies the admin with user details and an `/approve {chat_id}` command.
4. The admin can approve or deny the request, which adds/removes the chat ID from the runtime allowlist.

### Concurrency Control

The `ConcurrencyGate` prevents resource exhaustion:

- **Per-chat semaphore** (default: 2) -- limits concurrent jobs from a single chat.
- **Global semaphore** (default: 5) -- limits total concurrent jobs across all chats.
- **Queue overflow** (default: 10) -- rejects new requests if more than 10 jobs are queued for a single chat.

When a slot is unavailable, the bot replies with "Too many requests -- please wait for current jobs to finish."

### Sending Notifications (Outbound Only)

For one-way notifications from scripts, cron jobs, or skills:

```bash
# CLI
claw msg send telegram "$TELEGRAM_DEFAULT_CHAT_ID" "[STATUS] Task completed"

# Python
from superpowers.channels.telegram import TelegramChannel
ch = TelegramChannel(bot_token="...")
ch.send("123456789", "Hello from Python!", parse_mode="Markdown")
```

The outbound adapter supports:
- `parse_mode` parameter (default: `Markdown`, also supports `MarkdownV2`, `HTML`)
- `reply_markup` parameter for inline keyboards
- Automatic retry with exponential backoff (3 retries on HTTP 429/500/502/503/504)
- `Retry-After` header handling for rate limit responses

### Telegram Package Structure

```
msg_gateway/telegram/
  __init__.py
  api.py            # Shared Bot API client (retry + backoff)
  types.py          # Typed dataclasses: Update, Message, CallbackQuery, User, Chat, Voice, PhotoSize, Document
  auth.py           # Chat ID allowlist authorization (fail-closed)
  session.py        # Per-chat conversation history (Redis/in-memory)
  concurrency.py    # Per-chat semaphore + global job queue
  commands.py       # /start, /help, /status, /skills, /run, /mode, /history, /reset, /cancel
  callbacks.py      # Inline keyboard callback handler (skill:, mode:, confirm:, cancel:)
  keyboards.py      # InlineKeyboardMarkup builder helpers
  formatting.py     # MarkdownV2 escaping + smart chunking (respects code blocks)
  attachments.py    # Photo/document download, image description, PDF text extraction
  verification.py   # /start verification handshake + access request queue
  webhook.py        # Webhook update receiver + secret validation
  poller.py         # Main polling loop wiring all components
```

---

## Discord Integration

### Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create an application and add a bot user.
3. Copy the bot token.
4. Invite the bot to your server with the `Send Messages` permission.

### Configuration

Add to `.env`:

```bash
DISCORD_BOT_TOKEN=your-bot-token-here
```

**Optional** (for inbound webhook validation):

```bash
DISCORD_PUBLIC_KEY=your-application-public-key-hex
```

The public key is found on the application's **General Information** page. It is required for Discord webhook signature validation using Ed25519.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Yes (for outbound) | `""` | Bot token from Discord Developer Portal |
| `DISCORD_PUBLIC_KEY` | Yes (for inbound) | `""` | Application public key for Ed25519 webhook verification |

### Sending Messages

**CLI:**

```bash
claw msg send discord "1234567890123456789" "Deploy complete"
```

**Python:**

```python
from superpowers.channels.discord import DiscordChannel

ch = DiscordChannel(bot_token="...")
result = ch.send("1234567890123456789", "Hello from the bot!")
print(result.ok, result.message)  # True, "id=1234567890"
```

### Target Format

Targets are Discord channel IDs (numeric snowflake IDs, e.g., `1234567890123456789`). To find a channel ID, enable Developer Mode in Discord settings, then right-click a channel and select "Copy ID."

### Connection Test

```bash
claw msg test discord
# OK discord -- bot=SuperpowersBot#1234
```

The test calls `GET /users/@me` to verify the token.

### Limitations

- **Outbound only** (by default). Inbound support requires configuring the webhook endpoint and public key.
- No retry logic on transient HTTP errors.
- Messages are sent as plain text via `POST /channels/{id}/messages`. No embeds or rich formatting.
- Ed25519 webhook verification requires the `PyNaCl` library (`pip install PyNaCl`). Without it, webhook validation fails closed.
- Maximum message length is 2,000 characters. No automatic chunking is applied.

---

## Email Integration

### Setup

1. Obtain SMTP credentials from your email provider.
2. For Gmail, create an App Password (regular passwords are blocked for SMTP).
3. For self-hosted mail servers, use your standard SMTP credentials.

### Configuration

Add to `.env`:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_USER=user@gmail.com
SMTP_PASS=your-app-password
SMTP_PORT=587
SMTP_FROM=user@gmail.com
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | Yes | `""` | SMTP server hostname |
| `SMTP_USER` | Yes | `""` | SMTP login username |
| `SMTP_PASS` | Yes | `""` | SMTP login password or app-specific password |
| `SMTP_PORT` | No | `587` | SMTP port (587 for STARTTLS, 465 for implicit TLS) |
| `SMTP_FROM` | No | Value of `SMTP_USER` | `From:` address for outbound emails |

### Sending Messages

**CLI:**

```bash
claw msg send email "admin@example.com" "Alert: Backup Failed\nThe nightly backup job exited with code 1."
```

**Python:**

```python
from superpowers.channels.email import EmailChannel

ch = EmailChannel(
    host="smtp.gmail.com",
    user="user@gmail.com",
    password="app-password",
    port=587,
)
result = ch.send("admin@example.com", "Subject line\nBody content here")
```

### Message Format

The message string is split on the first newline:
- Everything before the first `\n` becomes the **Subject**.
- Everything after becomes the **Body** (plain text).
- If there is no newline, the entire message becomes the body and the subject defaults to "Claude Superpowers notification".

### Connection Test

```bash
claw msg test email
# OK email -- host=smtp.gmail.com:587, user=user@gmail.com
```

The test performs an EHLO, STARTTLS, and login to verify credentials without sending a message.

### Limitations

- **Outbound only**. No IMAP polling for inbound email is implemented.
- Plain text only -- no HTML formatting or attachments.
- STARTTLS is always used (port 587). Implicit SSL (port 465) is not currently supported by the adapter, though the standard library's `smtplib` supports it.
- No retry on transient SMTP errors.
- Connection timeout is 15 seconds for sends, 10 seconds for tests.

---

## iMessage Integration

### Setup

iMessage requires macOS. The adapter uses AppleScript to control the Messages.app, so:

1. The host must be running macOS.
2. Messages.app must be signed in to your iMessage/Apple ID account.
3. The user running claude-superpowers must have permission to run `osascript`.

No environment variables are required. The iMessage channel is automatically available when the platform is `darwin`.

### Configuration

No configuration is needed beyond being on macOS with Messages.app signed in. The `ChannelRegistry.available()` method checks `sys.platform == "darwin"` and includes `imessage` when true.

### Sending Messages

**CLI:**

```bash
claw msg send imessage "+15551234567" "Server backup complete"
claw msg send imessage "user@icloud.com" "Hello from superpowers"
```

**Python:**

```python
from superpowers.channels.imessage import IMessageChannel

ch = IMessageChannel()
result = ch.send("+15551234567", "Hello from Python!")
```

### Target Format

Targets are iMessage-addressable identifiers:
- Phone numbers (e.g., `+15551234567`)
- Email addresses registered with iMessage (e.g., `user@icloud.com`)
- Contact names as recognized by Messages.app

### Connection Test

```bash
claw msg test imessage
# OK imessage -- Messages.app running=true
```

The test checks whether the Messages.app process is running via AppleScript and System Events.

### Limitations

- **macOS only**. Returns an error on Linux and other platforms.
- **Outbound only**. No mechanism to receive iMessages.
- **No Docker support**. Must run on the host macOS system, not inside a container.
- Character escaping for special characters in messages and targets uses basic backslash escaping. Complex Unicode or AppleScript injection is not fully guarded.
- `osascript` timeout is 30 seconds.
- No retry logic.

---

## Notification Profiles

Profiles are named groups of channel+target pairs that allow skills, cron jobs, and workflows to reference a logical destination (e.g., `critical`) instead of hardcoding specific channels.

### Configuration

Create or edit `~/.claude-superpowers/profiles.yaml`:

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

devops:
  - channel: telegram
    target: "123456789"
  - channel: discord
    target: "1234567890123456789"
```

### Profile Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| `channel` | string | One of: `slack`, `telegram`, `discord`, `email`, `imessage` |
| `target` | string | Channel-specific target identifier |

### Usage

**CLI:**

```bash
# Fan out to all targets in a profile
claw msg notify critical "PVE1 is down -- backup failed"

# List all configured profiles
claw msg profiles
```

**Python:**

```python
from superpowers.channels.registry import ChannelRegistry
from superpowers.profiles import ProfileManager

registry = ChannelRegistry()
pm = ProfileManager(registry)
results = pm.send("critical", "PVE1 is down")
for r in results:
    print(f"{r.channel}:{r.target} -- {'OK' if r.ok else r.error}")
```

### Cron Integration

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

When `output` is set on a job, the cron engine:
1. Always writes output to the log file (default behavior).
2. Additionally sends a formatted message to the specified channel/profile.
3. Messaging failures are silently caught -- they never break job execution.

### Workflow Integration

Workflows reference notification profiles in their YAML definition:

```yaml
name: deploy
description: "Pull, test, deploy, verify"
notify_profile: critical

steps:
  - name: deploy-container
    type: shell
    command: "docker compose up -d"
```

When the workflow completes (or fails), the `notify_profile` receives a summary message.

---

## Inbound Triggers

Inbound triggers allow messages matching specific patterns to automatically execute commands. This turns chat channels into remote control interfaces.

### Configuration

Create `~/.claude-superpowers/triggers.yaml`:

```yaml
- pattern: "!scan network"
  action: skill
  command: network-scan
  reply: true

- pattern: "!health"
  action: shell
  command: "/usr/local/bin/health-check.sh"
  reply: true

- pattern: "!ask (.+)"
  action: claude
  command: "$1"
  reply: true

- pattern: "!deploy"
  action: shell
  command: "claw workflow run deploy"
  reply: true
```

### Trigger Rule Fields

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `pattern` | Yes | -- | string (regex) | Regular expression matched against incoming message text (case-insensitive) |
| `action` | No | `shell` | enum | `shell`, `claude`, or `skill` |
| `command` | Yes | -- | string | Command to execute when the pattern matches |
| `reply` | No | `true` | boolean | Whether to send the output back to the originating channel |

### Action Types

| Action | Behavior |
|--------|----------|
| `shell` | Runs command via `subprocess.run()` with `TRIGGER_MESSAGE` env var set to the full message text. 120-second timeout. |
| `claude` | Runs the configured chat LLM provider with the command prompt. |
| `skill` | Loads and runs the named skill via `SkillRegistry` + `SkillLoader`. |

### How Triggers Are Evaluated

1. The `TriggerManager` loads rules from `~/.claude-superpowers/triggers.yaml` on startup.
2. For each inbound message, `match(text)` iterates through rules and returns the first matching rule.
3. If a rule matches, `execute(rule, message_text)` runs the action.
4. If `reply` is true, the output (stdout + stderr) is sent back to the originating chat, truncated to 4,000 characters.
5. If no rule matches on Telegram, the message is routed to the configured chat provider for a conversational response.

### Currently Supported Channels for Inbound Triggers

| Channel | Trigger Support | Implementation |
|---------|----------------|----------------|
| Telegram | Yes | `TelegramPoller` in `msg_gateway/inbound.py` and `msg_gateway/telegram/poller.py` |
| Slack | Stub | Webhook endpoint exists at `/webhook/slack`; trigger routing not yet implemented |
| Discord | Stub | Webhook endpoint exists at `/webhook/discord`; trigger routing not yet implemented |
| Email | No | No IMAP polling implemented |
| iMessage | No | macOS outbound only |

---

## Security

### Authentication Summary

| Channel | Outbound Auth | Inbound Auth |
|---------|--------------|--------------|
| Slack | Bot token (`SLACK_BOT_TOKEN`) | HMAC-SHA256 signing (`SLACK_SIGNING_SECRET`) |
| Telegram | Bot token (`TELEGRAM_BOT_TOKEN`) | Chat ID allowlist (`ALLOWED_CHAT_IDS`) + webhook secret (`TELEGRAM_WEBHOOK_SECRET`) |
| Discord | Bot token (`DISCORD_BOT_TOKEN`) | Ed25519 signature (`DISCORD_PUBLIC_KEY`) |
| Email | SMTP credentials (`SMTP_USER`/`SMTP_PASS`) | N/A |
| iMessage | macOS user session | N/A |

### Webhook Signature Validation

All inbound webhook requests pass through `WebhookSignatureMiddleware` in `msg_gateway/middleware.py`. The middleware is **fail-closed** -- if the corresponding secret/key is not configured, requests are rejected (not allowed through).

**Telegram:**
- Validates the `X-Telegram-Bot-Api-Secret-Token` header against `TELEGRAM_WEBHOOK_SECRET`.
- Uses constant-time comparison (`hmac.compare_digest`).

**Slack:**
- Validates using Slack's v0 signing scheme.
- Computes `HMAC-SHA256("v0:{timestamp}:{body}")` using `SLACK_SIGNING_SECRET`.
- Checks the `X-Slack-Signature` header.
- Rejects requests with timestamps older than 5 minutes (replay protection).

**Discord:**
- Validates Ed25519 signatures using PyNaCl.
- Checks `X-Signature-Ed25519` and `X-Signature-Timestamp` headers against `DISCORD_PUBLIC_KEY`.
- If PyNaCl is not installed, requests are rejected (fail-closed).

**Disabling validation** (not recommended):

```bash
WEBHOOK_REQUIRE_SIGNATURE=false
```

### Telegram Chat ID Allowlist

The Telegram bot uses a secure-by-default authorization model:

- If `ALLOWED_CHAT_IDS` is empty or not set, **all messages are rejected**.
- Unauthorized attempts are logged once per chat ID (to prevent log spam).
- The allowlist is enforced at the `AuthGate` level before any message processing.
- Runtime modification is supported via `AuthGate.add()` / `AuthGate.remove()`.
- The chat verification handshake (`ChatVerification`) allows unknown users to request access, which an admin can approve via `TELEGRAM_ADMIN_CHAT_ID`.

### Rate Limiting

Both the message gateway and dashboard enforce per-IP rate limiting via token-bucket middleware.

| Setting | Default | Description |
|---------|---------|-------------|
| `RATE_LIMIT_PER_IP` | `60` | Max requests per minute per IP address |
| `RATE_LIMIT_PER_USER` | `120` | Max requests per minute per authenticated user |

Behavior:
- Returns `429 Too Many Requests` with `Retry-After: 60` header when exceeded.
- Health endpoints (`/health`, `/api/health`) are exempt.
- Token buckets refill continuously (not in fixed windows).
- Stale buckets are cleaned up after 10 minutes of inactivity.

### Concurrency Controls (Telegram)

The Telegram bot has its own concurrency limits separate from HTTP rate limiting:

| Control | Default | Purpose |
|---------|---------|---------|
| Per-chat semaphore | 2 | Prevents a single user from monopolizing the bot |
| Global semaphore | 5 | Prevents total resource exhaustion |
| Queue overflow | 10 | Rejects requests when too many are queued for a chat |

### Network Security

- The message gateway (`msg-gateway`, port 8100) has no authentication on the `/send` endpoint. Anyone who can reach port 8100 can send messages through configured channels. **Restrict access to localhost or use network-level controls.**
- The gateway should run behind a reverse proxy with TLS for production deployments.
- Redis should be bound to localhost or isolated within a Docker network.
- Webhook endpoints require HTTPS when receiving from external services (Telegram, Slack, Discord all require or strongly recommend HTTPS).

### Credential Storage

| Credential | Where Stored | Notes |
|------------|-------------|-------|
| Bot tokens | `.env` file | Can also be stored in the encrypted vault for additional security |
| Webhook secrets | `.env` file | Used only at runtime; not needed by adapters |
| SMTP passwords | `.env` file | App-specific passwords recommended for Gmail |
| Chat ID allowlist | `.env` file | Plain text; no encryption needed (not a secret) |

### TLS / HTTPS

The messaging services serve over HTTP by default. For production:

1. Set `ENVIRONMENT=production` (auto-enables `FORCE_HTTPS`).
2. Use a TLS-terminating reverse proxy (nginx, Caddy, or Cloudflare Tunnel).
3. Set `FORCE_HTTPS=true` explicitly if not using the `ENVIRONMENT` variable.

Webhook endpoints from Telegram, Slack, and Discord all expect to POST to HTTPS URLs. Use Cloudflare Tunnel or a similar tool to expose local services securely. See `docs/guides/cloudflared-setup.md` for Cloudflare Tunnel configuration.

---

## Testing and Debugging

### Testing Each Channel

**Slack:**

```bash
# Verify credentials
claw msg test slack

# Send a test message
claw msg send slack "#test-channel" "Hello from superpowers"
```

**Telegram:**

```bash
# Verify credentials
claw msg test telegram

# Send a test message
claw msg send telegram "$TELEGRAM_DEFAULT_CHAT_ID" "Hello from superpowers"

# Start the bot in foreground (see logs in terminal)
python -m telegram-bot.entrypoint
```

**Discord:**

```bash
# Verify credentials
claw msg test discord

# Send a test message (use a channel ID, not name)
claw msg send discord "1234567890123456789" "Hello from superpowers"
```

**Email:**

```bash
# Verify SMTP credentials
claw msg test email

# Send a test email
claw msg send email "you@example.com" "Test Subject\nThis is the body."
```

**iMessage (macOS only):**

```bash
# Check Messages.app status
claw msg test imessage

# Send a test message
claw msg send imessage "+15551234567" "Test from superpowers"
```

### Testing the Gateway

```bash
# Check health
curl http://localhost:8100/health

# List configured channels
curl http://localhost:8100/channels

# Send via API
curl -X POST http://localhost:8100/send \
  -H "Content-Type: application/json" \
  -d '{"channel": "slack", "target": "#test", "message": "hello"}'
```

### Testing Profiles

```bash
# List profiles
claw msg profiles

# Test notification fan-out
claw msg notify info "Test notification from profiles"
```

### Automated Test Suite

```bash
# Run all messaging tests
PYTHONPATH=. pytest tests/test_channels*.py tests/test_telegram_*.py tests/test_msg_*.py -v

# Telegram-specific tests
PYTHONPATH=. pytest tests/test_telegram_api.py tests/test_telegram_types.py \
  tests/test_telegram_auth.py tests/test_telegram_formatting.py \
  tests/test_telegram_session.py tests/test_telegram_commands.py \
  tests/test_telegram_callbacks.py tests/test_telegram_keyboards.py -v

# Skip the hanging concurrency test
PYTHONPATH=. pytest tests/ --ignore=tests/test_telegram_concurrency.py -v
```

**Known test issues:**
- `test_telegram_concurrency.py` may hang. Always use `--ignore` for this file.
- Some tests may require `PYTHONPATH=.` so `msg_gateway` and `dashboard` packages resolve.

### Common Issues

**"Unknown channel" error:**

The channel's credentials are not configured in `.env`. Run `claw msg channels` to see which channels have credentials set.

**Telegram bot not responding:**

1. Check `TELEGRAM_BOT_TOKEN` is correct.
2. Check `ALLOWED_CHAT_IDS` includes your chat ID.
3. Check logs: `docker compose logs telegram-bot` or `journalctl -u telegram-bot -f`.
4. Verify no other process is polling the same bot token (only one poller per token is allowed).

**"Unauthorized" in Telegram logs:**

Your chat ID is not in `ALLOWED_CHAT_IDS`. The logs will show the rejected chat ID. Add it to `.env` and restart the bot.

**Messages getting truncated (Telegram):**

The bot uses smart chunking at 4,000 characters (below Telegram's 4,096 limit). Long messages are split at paragraph, line, or sentence boundaries. Code blocks are preserved across splits when possible.

**Slack "not_in_channel" error:**

The bot needs to be invited to the channel, or add the `chat:write.public` scope to post without joining.

**Redis connection errors:**

The Telegram bot falls back to in-memory session storage if Redis is unavailable. Session history will not persist across restarts. Check `REDIS_URL` and ensure Redis is running.

**Email "Authentication failed":**

Gmail requires an App Password when 2FA is enabled. Regular account passwords are blocked for SMTP. Create an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

### Log Locations

| Component | Log Location |
|-----------|-------------|
| Telegram bot (Docker) | `docker compose logs telegram-bot` |
| Telegram bot (systemd) | `journalctl -u telegram-bot -f` |
| Message gateway (Docker) | `docker compose logs msg-gateway` |
| Audit log (messaging events) | `~/.claude-superpowers/audit.log` |
| Cron daemon logs | `~/.claude-superpowers/logs/` |

Audit log entries for messaging use the `msg.*` action pattern:

```bash
claw audit search "msg"
```

---

## Adding a New Channel

To add a new channel adapter, implement both the outbound interface (for sending) and optionally the inbound interface (for receiving).

### Step 1: Create the Outbound Adapter

Create `superpowers/channels/myservice.py`:

```python
"""MyService channel adapter."""

from __future__ import annotations

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult


class MyServiceChannel(Channel):
    channel_type = ChannelType.myservice  # Add to ChannelType enum first

    def __init__(self, api_key: str):
        if not api_key:
            raise ChannelError("MyService API key is required")
        self._key = api_key

    def send(self, target: str, message: str) -> SendResult:
        """Send a message to the target.

        Parameters:
            target: Service-specific target identifier
            message: Message text to send

        Returns:
            SendResult with ok=True on success, ok=False with error on failure
        """
        try:
            # Implement sending logic here
            # Always return SendResult, never raise exceptions to callers
            return SendResult(
                ok=True, channel="myservice", target=target,
                message="id=12345",
            )
        except Exception as exc:
            return SendResult(
                ok=False, channel="myservice", target=target,
                error=f"Unexpected error: {exc}",
            )

    def test_connection(self) -> SendResult:
        """Verify credentials without sending a message."""
        try:
            # Implement credential verification
            return SendResult(
                ok=True, channel="myservice", target="",
                message="connected as bot-name",
            )
        except Exception as exc:
            return SendResult(
                ok=False, channel="myservice", target="",
                error=str(exc),
            )
```

### Step 2: Register in the Enum and Factory

**Add to `superpowers/channels/base.py`:**

```python
class ChannelType(StrEnum):
    slack = "slack"
    telegram = "telegram"
    discord = "discord"
    email = "email"
    imessage = "imessage"
    myservice = "myservice"  # Add this
```

**Add to `superpowers/channels/registry.py`:**

In `ChannelRegistry.available()`:

```python
if s.myservice_api_key:
    names.append("myservice")
```

In `ChannelRegistry._create()`:

```python
elif name == ChannelType.myservice.value:
    from superpowers.channels.myservice import MyServiceChannel
    return MyServiceChannel(api_key=s.myservice_api_key)
```

### Step 3: Add Settings

In `superpowers/config.py`, add the new field to the `Settings` dataclass and `load()` method:

```python
@dataclass
class Settings:
    # ... existing fields ...
    myservice_api_key: str = ""

    @classmethod
    def load(cls, ...):
        return cls(
            # ... existing fields ...
            myservice_api_key=_env("MYSERVICE_API_KEY"),
        )
```

Add to `.env.example`:

```bash
MYSERVICE_API_KEY=
```

### Step 4: (Optional) Add Inbound Webhook Support

If the channel supports inbound messages via webhooks:

1. **Add a webhook route** in `msg_gateway/app.py`:

```python
@app.post("/webhook/myservice")
async def myservice_webhook(request: Request):
    # Parse and dispatch
    pass
```

2. **Add signature verification** in `msg_gateway/middleware.py`:

```python
def _verify_myservice(request: Request, body: bytes) -> bool:
    secret = os.environ.get("MYSERVICE_WEBHOOK_SECRET", "")
    if not secret:
        return False
    # Implement verification
    return True

_WEBHOOK_VERIFIERS["/webhook/myservice"] = _verify_myservice
```

3. **(Optional) Implement the ChannelAdapter interface** in `msg_gateway/channels/`:

```python
from msg_gateway.channels.base import ChannelAdapter, Message

class MyServiceAdapter(ChannelAdapter):
    @property
    def name(self) -> str:
        return "myservice"

    async def receive(self, request) -> Message:
        # Parse inbound webhook payload
        ...

    async def acknowledge(self, message: Message) -> None:
        # Send read receipt or reaction
        ...

    async def start_processing_indicator(self, message: Message) -> None:
        # Show typing indicator
        ...

    async def send_response(self, message: Message, response: str) -> None:
        # Send reply
        ...
```

### Step 5: Add Tests

Create `tests/test_channels_myservice.py` with tests for:
- Constructor validation (missing credentials raise `ChannelError`)
- `send()` success and failure cases
- `test_connection()` success and failure cases
- Import error handling (if the adapter depends on an optional package)

### Step 6: Update Documentation

Add the new channel to:
- This file (`docs/reference/CHAT_INTEGRATIONS.md`) -- channel comparison matrix, dedicated section
- `docs/reference/CONFIGURATION.md` -- environment variables table
- `README.md` -- feature summary if notable

### Interface Contract Summary

| Method | Signature | Behavior |
|--------|-----------|----------|
| `__init__` | `(credentials...)` | Validate credentials; raise `ChannelError` if missing |
| `send` | `(target, message) -> SendResult` | Deliver message; never raise, always return `SendResult` |
| `test_connection` | `() -> SendResult` | Verify credentials work; never raise, always return `SendResult` |

Key rules:
- `send()` and `test_connection()` must **never raise exceptions**. All errors are captured in `SendResult.error`.
- Optional dependencies (external SDKs) are imported lazily inside methods. If missing, return `SendResult(ok=False, error="package not installed")`.
- All adapters are instantiated lazily by `ChannelRegistry` -- they are only created when first requested.
- Credentials are validated in `__init__` (raise `ChannelError` for missing required values).

---

## Quick Reference

### CLI Commands

```bash
claw msg channels                        # List channels + credential status
claw msg test <channel>                  # Verify credentials work
claw msg send <ch> <target> <msg>        # Send to a specific channel
claw msg profiles                        # List notification profiles
claw msg notify <profile> <msg>          # Fan-out to all profile targets
```

### Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| `redis` | 6379 | Session storage, message pub/sub bus |
| `msg-gateway` | 8100 | HTTP API for sending + webhook receivers |
| `telegram-bot` | -- | Telegram polling service (no exposed port) |

### Gateway API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Channel configuration status (unauthenticated) |
| `GET` | `/channels` | List of configured channel names |
| `POST` | `/send` | Send a message: `{channel, target, message}` |
| `POST` | `/webhook/telegram` | Telegram webhook receiver |
| `POST` | `/webhook/slack` | Slack webhook receiver |
| `POST` | `/webhook/discord` | Discord webhook receiver |

### Required Packages

| Package | Channel | Required For |
|---------|---------|-------------|
| `slack_sdk` | Slack | Outbound messaging |
| `PyNaCl` | Discord | Inbound webhook signature verification |
| `pyyaml` | All | Profile and trigger YAML parsing |
| `redis` | Telegram bot | Session persistence (falls back to in-memory) |
| `whisper.cpp` | Telegram | Voice message transcription (system binary) |
| `ffmpeg` | Telegram | Audio format conversion for voice messages |
| `pdftotext` | Telegram | PDF text extraction (poppler-utils) |
