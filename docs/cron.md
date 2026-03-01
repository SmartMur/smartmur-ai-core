# Cron / Scheduler

## Overview

The cron subsystem is an APScheduler-based daemon that runs scheduled jobs in the background as a macOS launchd service. It supports shell commands, headless Claude sessions, HTTP webhooks, and registered skills -- all manageable through `claw cron` and `claw daemon` CLI commands.

Jobs persist across restarts via a `jobs.json` manifest backed by a SQLite job store. Output from each execution is captured to structured log files under `~/.claude-superpowers/cron/output/`.

## Schedule Formats

Three schedule formats are supported:

| Format | Example | Description |
|--------|---------|-------------|
| Cron expression | `"0 */6 * * *"` | Standard 5-field cron syntax |
| Interval string | `"every 6h"` | Human-readable interval (`s`, `m`, `h`, `d`) |
| Daily-at pattern | `"daily at 09:00"` | Run once per day at a specific time |

Cron expressions follow the standard `minute hour day month weekday` format. Interval strings accept any combination: `every 30m`, `every 2h30m`, `every 1d`.

## Job Types

### shell

Runs a command via subprocess. The command inherits the daemon's environment plus any vault-injected secrets.

```yaml
type: shell
command: "nmap -sn 192.168.30.0/24 -oG -"
```

### claude

Launches a headless Claude Code session with `claude -p`. Useful for AI-driven analysis, summarization, or decision-making on a schedule.

```yaml
type: claude
prompt: "Read the last 24h of /var/log/system.log and summarize any warnings or errors."
```

### webhook

Sends an HTTP POST request to a URL with an optional JSON body. Useful for triggering external services or sending notifications.

```yaml
type: webhook
url: "https://hooks.slack.com/services/T00/B00/xxx"
body:
  text: "Scheduled health check passed."
```

### skill

Invokes a registered skill by name. The skill runs through the same loader pipeline as `claw skill run`.

```yaml
type: skill
skill: network-scan
args: "--subnet 192.168.30.0/24"
```

## Output Routing

Every job execution writes output to a structured log path:

```
~/.claude-superpowers/cron/output/{job-id}/{timestamp}.log
```

Example:

```
~/.claude-superpowers/cron/output/network-scan-6h/2026-03-01T090000.log
```

Each log file contains stdout, stderr, exit code, and execution duration. Logs are retained indefinitely by default. Use `claw cron logs --prune 30d` to clean up old output.

Future Phase 3 (Messaging Gateway) will add output routing to Slack, Telegram, Discord, and email channels.

## CLI Reference

### `claw cron list`

List all registered jobs with their schedule, type, and enabled/disabled status.

```bash
claw cron list
```

```
ID                  TYPE    SCHEDULE         ENABLED  LAST RUN
network-scan-6h     shell   every 6h         yes      2026-03-01 06:00
daily-backup-check  shell   daily at 09:00   yes      2026-03-01 09:00
slack-notify        webhook 0 8 * * 1-5      yes      2026-02-28 08:00
daily-summary       claude  daily at 18:00   no       --
```

### `claw cron add`

Add a new scheduled job.

```bash
claw cron add <id> --type <type> --schedule <schedule> [options]
```

Options:

| Flag | Description |
|------|-------------|
| `--type` | Job type: `shell`, `claude`, `webhook`, `skill` |
| `--schedule` | Schedule expression (cron, interval, or daily-at) |
| `--command` | Shell command (for `shell` type) |
| `--prompt` | Claude prompt (for `claude` type) |
| `--url` | Webhook URL (for `webhook` type) |
| `--body` | JSON body string (for `webhook` type) |
| `--skill` | Skill name (for `skill` type) |
| `--args` | Arguments passed to skill (for `skill` type) |
| `--enabled/--disabled` | Start enabled or disabled (default: enabled) |

### `claw cron remove`

Remove a job by ID. Stops the job if it is currently scheduled.

```bash
claw cron remove <id>
```

### `claw cron enable`

Enable a previously disabled job.

```bash
claw cron enable <id>
```

### `claw cron disable`

Disable a job without removing it. The job remains in `jobs.json` but will not execute.

```bash
claw cron disable <id>
```

### `claw cron logs`

View execution logs for a job.

```bash
claw cron logs <id>              # Show recent logs
claw cron logs <id> --tail 50    # Last 50 lines
claw cron logs <id> --follow     # Stream new output
claw cron logs --prune 30d       # Delete logs older than 30 days
```

### `claw cron run`

Execute a job immediately, outside its schedule. Useful for testing.

```bash
claw cron run <id>
```

### `claw cron status`

Show the daemon status and next scheduled run time for each job.

```bash
claw cron status
```

```
Daemon: running (pid 42019)
Uptime: 3d 14h 22m

ID                  NEXT RUN              STATUS
network-scan-6h     2026-03-01 12:00:00   waiting
daily-backup-check  2026-03-02 09:00:00   waiting
slack-notify        2026-03-03 08:00:00   waiting
daily-summary       --                    disabled
```

## Examples

### Schedule a network scan every 6 hours

```bash
claw cron add network-scan-6h \
  --type skill \
  --skill network-scan \
  --schedule "every 6h"
```

### Daily backup verification at 9am

```bash
claw cron add daily-backup-check \
  --type shell \
  --command "ssh ray@192.168.30.117 'zpool status && zfs list -t snapshot -o name,used,creation | tail -5'" \
  --schedule "daily at 09:00"
```

### Webhook notification on weekday mornings

```bash
claw cron add slack-notify \
  --type webhook \
  --url "https://hooks.slack.com/services/T00/B00/xxx" \
  --body '{"text":"Good morning. All systems nominal."}' \
  --schedule "0 8 * * 1-5"
```

### Claude-powered daily summary

```bash
claw cron add daily-summary \
  --type claude \
  --prompt "Review today's cron job output at ~/.claude-superpowers/cron/output/ and write a 5-bullet summary of what ran, what failed, and anything unusual." \
  --schedule "daily at 18:00"
```

## Job Persistence

Jobs are stored in two locations:

| File | Purpose |
|------|---------|
| `~/.claude-superpowers/cron/jobs.json` | Human-readable job manifest with schedules, types, and configuration |
| `~/.claude-superpowers/cron/jobstore.sqlite` | APScheduler's internal job store for trigger state and next-run tracking |

When the daemon starts, it reconciles `jobs.json` with the SQLite store. If you edit `jobs.json` manually, restart the daemon to pick up changes.

Example `jobs.json` entry:

```json
{
  "network-scan-6h": {
    "type": "skill",
    "skill": "network-scan",
    "schedule": "every 6h",
    "enabled": true,
    "created": "2026-02-28T10:30:00Z"
  }
}
```

## Daemon Management

The cron daemon runs as a macOS launchd service. Manage it with `claw daemon`:

### `claw daemon install`

Install the launchd plist and start the daemon.

```bash
claw daemon install
```

This creates `~/Library/LaunchAgents/com.claude-superpowers.cron.plist` and loads it via `launchctl`. The daemon starts automatically on login.

### `claw daemon uninstall`

Stop the daemon and remove the launchd plist.

```bash
claw daemon uninstall
```

### `claw daemon status`

Show whether the daemon is running, its PID, and uptime.

```bash
claw daemon status
```

### `claw daemon logs`

View the daemon's own logs (not individual job output).

```bash
claw daemon logs              # Recent entries
claw daemon logs --follow     # Stream live
```

Daemon logs are written to `~/.claude-superpowers/cron/daemon.log`.

## Modules

| Module | Path | Purpose |
|--------|------|---------|
| `cron_engine` | `superpowers/cron_engine.py` | APScheduler setup, job type dispatch, schedule parsing |
| `cron_runner` | `superpowers/cron_runner.py` | Job execution: subprocess, claude, HTTP, skill invocation |
| `launchd` | `superpowers/launchd.py` | Plist generation, launchctl install/uninstall/status |
| `cli_cron` | `superpowers/cli_cron.py` | Click commands for `claw cron` and `claw daemon` |
