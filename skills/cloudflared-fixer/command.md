# Cloudflared Fixer

Monitor and auto-fix the cloudflared tunnel container. Detects crash loops, diagnoses errors, and applies automatic recovery.

## Usage

```
/cloudflared-fixer
```

## What it monitors

- Container status (running, stopped, crash-looping)
- Restart count and exit codes
- Log patterns: invalid token, network errors, DNS failures, cert issues
- Tunnel token validity (detects placeholder tokens)

## Auto-fix capabilities

- **Crash loop:** Stops container to prevent CPU waste, alerts operator
- **Network errors:** Waits and restarts once for transient failures
- **Container down:** Attempts `docker compose up -d` if no blocking issues
- **Bad token:** Stops container, documents issue, requires user to provide real token

## Output

- Console: status, issues, and actions taken
- Telegram: alerts for crash loops, down status, degraded health
- Audit log: all actions logged to ~/.claude-superpowers/audit.log
- Status: saved to ~/.claude-superpowers/cloudflared-monitor/status.json
- Incidents: appended to ~/.claude-superpowers/cloudflared-monitor/incident-log.jsonl

## Exit Codes

- 0: healthy
- 1: issue detected
- 2: monitor execution error
