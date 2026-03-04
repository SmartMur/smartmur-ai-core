# Telegram Reporting Setup

## Goal

Enable automatic progress updates from intake runs to your Telegram bot chat.

## Current Behavior

- `claw intake run ...` sends start + finish updates when a chat ID is available.
- If chat ID is unknown, updates are queued in:
  - `~/.claude-superpowers/runtime/pending_telegram_updates.jsonl`

## One-Time Setup

1. Message your bot (`@SuperBv20_bot`) from the Telegram account/chat you want updates in.
2. Set default target in `.env`:
   - `TELEGRAM_DEFAULT_CHAT_ID=<chat_id>`
3. Flush queued updates:
   - `claw intake flush-telegram`

## Verification

```bash
claw msg test telegram
claw intake run "telegram reporting smoke test"
```

You should receive two bot messages: `Intake started` and `Intake finished`.

