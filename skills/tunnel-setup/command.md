# Tunnel Setup

Cloudflare tunnel setup helper -- validates token, manages container, checks connectivity.

## Usage

```
/tunnel-setup                          # Show status (default)
/tunnel-setup status                   # Show container state, token, health
/tunnel-setup set-token <token>        # Validate + write token + start container
/tunnel-setup start                    # Start cloudflared container
/tunnel-setup stop                     # Stop cloudflared container
/tunnel-setup logs                     # Show last 30 log lines
/tunnel-setup help                     # Show usage
```

## Quick Start

1. Get your tunnel token from https://one.dash.cloudflare.com/ (Zero Trust > Networks > Tunnels)
2. Run: `/tunnel-setup set-token eyJhIjoiYWJj...your-real-token...`
3. Verify: `/tunnel-setup status`

## Token Requirements

- Must be at least 50 characters
- Must be base64-like (alphanumeric, +, /, =, -, _)
- Must not be a placeholder (e.g., "your_tunnel_token_here")

## What Happens

- `set-token`: Validates format, writes to `/home/ray/docker/cloudflared/.env`, starts container, logs to audit, notifies Telegram
- `start`: Validates current token (warns if bad), runs `docker compose up -d`
- `stop`: Runs `docker stop cloudflared-cloudflared-1`
- `status`: Inspects container, reads token, reports health

## Exit Codes

- 0: success / healthy
- 1: issue detected (bad token, container down)
- 2: error (docker not found, write failed, invalid args)

## Integration

- Audit log: all state changes written to `~/.claude-superpowers/audit.log`
- Telegram: notifications on token set, start, stop, errors
- Works with `/cloudflared-fixer` for automated monitoring
