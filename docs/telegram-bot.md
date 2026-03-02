# Telegram Bot — Architecture & Usage Guide

The Telegram bot provides a two-way interface between Telegram and Claude AI, with command routing, skill execution, conversation history, and real-time progress reporting.

---

## Architecture

### Package Structure

```
msg_gateway/telegram/
├── __init__.py       # Package init
├── api.py            # Shared Bot API client (retry + backoff)
├── types.py          # Typed dataclasses for Telegram updates
├── auth.py           # Chat ID allowlist authorization
├── session.py        # Per-chat conversation history (Redis/in-memory)
├── concurrency.py    # Per-chat semaphore + global job queue
├── commands.py       # /start, /help, /status, /skills, /run, /mode, /history, /reset, /cancel
├── callbacks.py      # Inline keyboard callback handler
├── keyboards.py      # InlineKeyboardMarkup builder helpers
├── formatting.py     # MarkdownV2 escaping + smart chunking
└── poller.py         # Main polling loop wiring all components
```

### Message Flow

```
Telegram → Poller → parse_update() → AuthGate
  → callback_query? → CallbackHandler
  → /command?       → CommandRouter
  → trigger match?  → TriggerManager (existing)
  → else            → SessionManager.add(user)
                    → ConcurrencyCheck
    → mode=chat:  Claude CLI with history context
    → mode=skill: Intake pipeline with progress callback
    → smart_chunk() → SessionManager.add(assistant) → send
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | (required) | Bot API token from @BotFather |
| `TELEGRAM_DEFAULT_CHAT_ID` | — | Default chat for outbound notifications |
| `ALLOWED_CHAT_IDS` | — | Comma-separated allowlist (**required for security**) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for session persistence |
| `TELEGRAM_SESSION_TTL` | `3600` | Conversation history TTL (seconds) |
| `TELEGRAM_MAX_HISTORY` | `20` | Max messages per chat session |
| `TELEGRAM_MAX_PER_CHAT` | `2` | Max concurrent jobs per chat |
| `TELEGRAM_MAX_GLOBAL` | `5` | Max concurrent jobs globally |
| `TELEGRAM_QUEUE_OVERFLOW` | `10` | Max queued jobs before rejecting |

### Security

The bot uses a **secure-by-default** authorization model:

- If `ALLOWED_CHAT_IDS` is not set, **all messages are rejected**
- Set it to a comma-separated list of chat IDs that should be allowed
- Find your chat ID by messaging the bot and checking logs

---

## Commands

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

Commands are registered with Telegram via `setMyCommands` on startup, providing autocomplete in the Telegram client.

---

## Modes

### Chat Mode (default)
Messages are sent to Claude CLI with conversation history as context. The bot maintains a sliding window of the last 20 messages (configurable) per chat.

### Skill Mode
Messages are routed through the intake pipeline. The bot:
1. Extracts requirements from the message
2. Maps to available skills
3. Executes with progress callbacks
4. Reports results back to the chat

Switch modes with `/mode chat` or `/mode skill`, or use the inline keyboard from `/mode`.

---

## Components

### TelegramApi (`api.py`)
Shared HTTP client for all Telegram Bot API calls. Features:
- **Retry with exponential backoff** on HTTP 429/500/502/503/504
- **Rate limit handling** via `Retry-After` header
- Convenience methods: `send_message`, `get_updates`, `answer_callback_query`, `set_my_commands`
- Fire-and-forget mode for non-critical calls (typing indicators)

### AuthGate (`auth.py`)
Authorization gate that checks incoming chat IDs against an allowlist:
- Secure by default — rejects all if no allowlist configured
- Logs unauthorized attempts (once per chat ID to avoid spam)
- Runtime `add()`/`remove()` for dynamic allowlist management

### SessionManager (`session.py`)
Per-chat conversation history:
- **Redis** storage when available (sliding window via `LTRIM`, TTL via `EXPIRE`)
- **In-memory dict** fallback when Redis is unavailable
- Configurable max history (default: 20 messages) and TTL (default: 1 hour)
- `format_context()` method produces context string for Claude

### ConcurrencyGate (`concurrency.py`)
Thread-safe concurrency control:
- Per-chat semaphore (default: 2 concurrent jobs)
- Global semaphore (default: 5 total)
- Queue overflow protection (default: reject after 10 queued)
- `try_acquire()` / `release()` API for bracket-style usage

### Formatting (`formatting.py`)
- `escape_markdown_v2()`: Escapes special characters while preserving code blocks
- `smart_chunk()`: Splits long messages at paragraph/line/sentence boundaries without breaking code blocks

### Keyboards (`keyboards.py`)
Builder helpers for Telegram inline keyboards:
- `button_grid()`: N-column grid from (label, data) tuples
- `confirm_keyboard()`: Yes/Cancel confirmation flow
- `skill_list_keyboard()`: Skill selection keyboard
- `mode_keyboard()`: Chat/skill mode selector

---

## Running the Bot

### Direct
```bash
cd /home/ray/claude-superpowers
python -m telegram-bot.entrypoint
```

### Via Docker Compose
```bash
docker compose up telegram-bot
```

### Via systemd (Linux)
```bash
# Install service
sudo cp deploy/telegram-bot.service /etc/systemd/system/
sudo systemctl enable --now telegram-bot
```

---

## Sending Notifications

### From CLI
```bash
claw msg send telegram "$TELEGRAM_DEFAULT_CHAT_ID" "[STATUS] Task completed"
```

### From Python
```python
from superpowers.channels.telegram import TelegramChannel
ch = TelegramChannel(bot_token="...")
ch.send("CHAT_ID", "Hello from Python!")
```

### From Intake Pipeline
```python
from superpowers.intake import run_intake

def on_progress(msg):
    print(f"Progress: {msg}")

run_intake("scan network", execute=True, progress_callback=on_progress)
```

---

## Testing

```bash
pytest tests/test_telegram_*.py -v
```

Test files:
- `test_telegram_api.py` — API client retry/error handling
- `test_telegram_types.py` — Update parsing
- `test_telegram_auth.py` — Authorization gate
- `test_telegram_formatting.py` — Escaping and chunking
- `test_telegram_session.py` — Conversation history
- `test_telegram_concurrency.py` — Concurrency control
- `test_telegram_commands.py` — Command routing
- `test_telegram_callbacks.py` — Callback handling
- `test_telegram_keyboards.py` — Keyboard builders

---

## Troubleshooting

### Bot not responding
1. Check `TELEGRAM_BOT_TOKEN` is set correctly
2. Check `ALLOWED_CHAT_IDS` includes your chat ID
3. Check logs: `journalctl -u telegram-bot -f`

### "Unauthorized" messages in logs
Your chat ID is not in `ALLOWED_CHAT_IDS`. Add it to `.env`:
```
ALLOWED_CHAT_IDS=123456789,987654321
```

### Messages getting truncated
The bot uses smart chunking to split messages at 4000 chars. If code blocks are being broken, check `formatting.py` logic.

### Redis connection errors
The bot falls back to in-memory session storage if Redis is unavailable. This means session history won't persist across bot restarts.
