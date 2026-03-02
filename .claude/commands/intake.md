# Intake

Mandatory request bootstrap: clear context, read/plan requirements, dispatch multi-agent skills.

## Usage

### Plan + dispatch only (default)
```bash
claw intake run "$ARGUMENTS"
```

### Plan + dispatch + execute in parallel
```bash
claw intake run "$ARGUMENTS" --execute
```

### Clear context only
```bash
claw intake clear
```

### Inspect current session
```bash
claw intake show
```

### Flush queued Telegram updates
```bash
claw intake flush-telegram
claw intake flush-telegram --telegram-chat "<chat_id>"
```

## Policy

Run this first for every request.  
If required skills/tools are missing, intake auto-installs/builds them from templates before execution.
If Telegram chat id is unavailable, updates are queued and can be flushed later.
