# Discord Bot Bootstrap

This project bootstraps Discord server branding and channel/category structure from
`config.yaml`, and generates a local admin credential for bot-side control (`ray`).

## What It Creates

- Server branding:
  - Name
  - Description
  - Icon (if `icon_path` exists)
- Roles:
  - `Admin`, `Moderator`, `Member`
- Categories/channels:
  - `START HERE`, `COMMUNITY`, `PROJECTS`, `SUPPORT`, `OPERATIONS`, `VOICE`
- Local bot admin credential:
  - Username: `ray`
  - Strong generated password
  - Password hash stored in `admin_credentials.json`

## Important Constraint

Discord bots cannot create real Discord user accounts.  
The `ray` admin here is a local bot/admin credential plus a mapped Discord role.

## Prerequisites

1. Add a real token to `/home/ray/claude-superpowers/.env`:
   - `DISCORD_BOT_TOKEN=...`
2. Invite the bot to your server with permissions:
   - `Manage Server`
   - `Manage Roles`
   - `Manage Channels`
3. Optionally set:
   - `DISCORD_GUILD_ID=<your server id>`

If `guild_id` is empty, the script auto-selects the guild only when the bot belongs
to exactly one server.

## Run

```bash
cd /home/ray/claude-superpowers
.venv/bin/python Projects/discord-bot/bootstrap_discord.py
```

Dry-run:

```bash
.venv/bin/python Projects/discord-bot/bootstrap_discord.py --dry-run
```

Rotate local admin password:

```bash
.venv/bin/python Projects/discord-bot/bootstrap_discord.py --rotate-admin-password
```

## Files

- `config.yaml`: branding + structure config
- `bootstrap_discord.py`: implementation
- `admin_credentials.json`: generated local admin credential hash (gitignored)
- `last_run.json`: last execution summary (gitignored)

