# Customization Guide

How to extend and customize every subsystem in claude-superpowers. This guide covers custom skills, workflows, cron jobs, channel adapters, file watchers, notification profiles, dashboard extensions, CLI commands, environment overrides, and the template system.

---

## Philosophy

claude-superpowers is designed around three principles that shape every customization point:

1. **Local-first**: Everything runs on your hardware. No cloud dependencies, no external SaaS requirements. Customizations should follow the same rule -- if an external service is unavailable, features degrade gracefully.

2. **Convention over configuration**: Subsystems discover resources by scanning well-known directories (`skills/`, `workflows/`, `~/.claude-superpowers/`). Drop a file in the right place with the right shape and it works.

3. **Composable primitives**: Skills, workflows, cron jobs, watchers, and messaging channels are independent units that connect through well-defined interfaces. A skill can be invoked from the CLI, a cron job, a workflow step, a file watcher, or an MCP tool -- the skill does not need to know which one called it.

---

## Table of Contents

- [Custom Skills](#custom-skills)
- [Custom Workflows](#custom-workflows)
- [Custom Cron Jobs](#custom-cron-jobs)
- [Custom Channel Adapters](#custom-channel-adapters)
- [Custom File Watchers](#custom-file-watchers)
- [Notification Profiles](#notification-profiles)
- [Dashboard Customization](#dashboard-customization)
- [CLI Extensions](#cli-extensions)
- [Environment and Config Overrides](#environment-and-config-overrides)
- [Template System](#template-system)
- [Examples](#examples)

---

## Custom Skills

Skills are the primary unit of automation. Each skill is a self-contained directory under `skills/` containing a manifest, an executable script, and optionally a slash command definition.

### Creating a Skill from Scratch

The fastest path is the interactive scaffolder:

```bash
claw skill create
```

You are prompted for a name, description, and script type (bash or python). The scaffolder generates three files and registers the slash command immediately.

For non-interactive creation, pass everything as flags:

```bash
claw skill create \
  --name cert-renewer \
  --description "Renew Let's Encrypt certificates and reload nginx" \
  --type bash \
  --permission vault \
  --permission ssh \
  --trigger "cron:weekly"
```

To create a skill entirely by hand:

```bash
mkdir -p skills/cert-renewer
```

Create `skills/cert-renewer/skill.yaml`:

```yaml
name: cert-renewer
version: "0.1.0"
description: "Renew Let's Encrypt certificates and reload nginx"
author: DreDay
script: run.sh
slash_command: true
dependencies: [certbot, ssh]
permissions: [vault, ssh]
triggers: ["cron:weekly"]
```

Create `skills/cert-renewer/run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# cert-renewer -- Renew Let's Encrypt certificates and reload nginx

main() {
    echo "[cert-renewer] checking certificate status..."
    certbot renew --dry-run 2>&1
    echo "[cert-renewer] reloading nginx..."
    ssh web-server "sudo systemctl reload nginx"
    echo "[cert-renewer] done"
}

main "$@"
```

Make it executable and validate:

```bash
chmod +x skills/cert-renewer/run.sh
claw skill validate skills/cert-renewer
claw skill sync
```

### skill.yaml Schema Reference

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `name` | yes | -- | string | Kebab-case identifier, unique across all skills |
| `version` | yes | -- | string | Semantic version (e.g., `"0.1.0"`) |
| `description` | yes | -- | string | One-line summary shown in `claw skill list` |
| `author` | yes | -- | string | Author attribution |
| `script` | yes | -- | string | Entry point script relative to skill directory |
| `slash_command` | no | `false` | boolean | If true, `claw skill sync` creates a Claude Code slash command |
| `triggers` | no | `[]` | list[string] | Event triggers for cron integration (e.g., `cron:daily`) |
| `dependencies` | no | `[]` | list[string] | Binaries checked via `which` before execution |
| `permissions` | no | `[]` | list[string] | Permission scopes for sandboxed execution |
| `skill_type` | no | `""` | string | Optional classification tag |

### Script Types

The skill loader detects how to execute based on the script file extension:

| Extension | Execution Command |
|-----------|-------------------|
| `.py` | `python3 <script>` |
| `.sh` | `bash <script>` |
| other | `./<script>` (direct execution, must have shebang) |

### Generated Templates

When `claw skill create` runs, it produces one of two templates:

**Bash template** -- includes a `usage()` function, `set -euo pipefail` for safety, argument parsing via `$1`, and a `main` function:

```bash
#!/usr/bin/env bash
set -euo pipefail

# my-skill -- Does something useful

usage() {
    echo "Usage: $(basename "$0") [options]"
    echo ""
    echo "  Does something useful"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    exit 0
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage

main() {
    echo "[my-skill] running..."
    # TODO: implement skill logic
}

main "$@"
```

**Python template** -- includes `argparse`, a `main()` returning an exit code, and `__future__` annotations:

```python
#!/usr/bin/env python3
"""my-skill -- Does something useful"""
from __future__ import annotations

import argparse
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Does something useful")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[my-skill] running...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Scaffolding from an Existing Script

If you already have a working script, wrap it as a skill in one step:

```python
from superpowers.skill_creator import scaffold_from_existing

skill_dir = scaffold_from_existing(
    source_script=Path("/home/ray/scripts/backup-check.sh"),
    name="backup-check",
    description="Verify ZFS snapshots on TrueNAS",
)
```

This copies your script into the skill directory, auto-detects the script type, generates `skill.yaml` and `command.md`, and preserves the original file unchanged.

### Sandboxing and Permissions

Skills run in two modes depending on the caller:

**Standard mode** (`SkillLoader.run()`):
- Inherits the full parent process environment
- Skill runs in its own directory as cwd
- 5-minute execution timeout

**Sandboxed mode** (`SkillLoader.run_sandboxed()`):
- Minimal environment: only `PATH`, `HOME`, `LANG`, `TERM` are passed
- Skills with `vault` in their `permissions` list receive the full environment
- Same 5-minute timeout
- Used by the intake pipeline for automatic skill execution

| Permission | Effect |
|------------|--------|
| `vault` | Full environment passthrough (including vault secrets) |
| `ssh` | Declares SSH access intent (documentation/future enforcement) |
| `nmap` | Declares network scanning capability (documentation/future enforcement) |
| (custom) | Allowed; custom strings are stored but not currently enforced |

### Dependency Gating

The `dependencies` field in `skill.yaml` is checked before execution. Every listed binary is verified via `which`. If any dependency is missing, the skill fails immediately with a clear error -- no partial execution occurs.

```yaml
dependencies: [nmap, jq, curl]
```

### Argument Passing

Arguments passed via CLI are converted to `SKILL_` prefixed environment variables:

```bash
claw skill run my-skill target=192.168.1.0/24 verbose=true
```

Inside the script:

```bash
echo $SKILL_TARGET      # 192.168.1.0/24
echo $SKILL_VERBOSE     # true
```

### Slash Command Registration

When `slash_command: true` is set in `skill.yaml`, `claw skill sync` does the following:

1. Generates `.claude/commands/<name>.md` inside the skill directory
2. Creates a symlink at `~/.claude/commands/<name>.md` pointing to that file
3. Claude Code discovers the symlink and registers `/<name>` as a slash command

Sync is idempotent. Run it any time you add, remove, or modify skills.

### Auto-Install

The auto-install system (`superpowers/auto_install.py`) can create skills on demand from a description. It works in three stages:

1. **Check existing skills** -- tokenizes the description and looks for keyword overlap with registered skills
2. **Match a built-in template** -- five templates are bundled: `network-scan`, `disk-usage`, `git-stats`, `docker-health`, `log-search`
3. **Scaffold a generic skill** -- if no template matches, creates a stub skill from the description

```bash
claw skill auto-install "scan the network for active hosts"
# -> Installs the network-scan template
```

Built-in templates:

| Template | Description | Tags |
|----------|-------------|------|
| `network-scan` | Scan local network using nmap or ping sweep | network, scan, hosts, nmap, ping |
| `disk-usage` | Report disk usage with high-usage alerts | disk, usage, storage, space, df |
| `git-stats` | Git repository statistics | git, stats, commits, contributors |
| `docker-health` | Docker container and image health check | docker, health, containers, images |
| `log-search` | Search system and application logs | log, search, grep, syslog, errors |

### Skill Lifecycle

| Stage | Command | What Happens |
|-------|---------|--------------|
| Create | `claw skill create` | Scaffold manifest + script + command.md |
| Validate | `claw skill validate skills/my-skill` | Check manifest schema + script existence |
| Sync | `claw skill sync` | Register slash commands as symlinks |
| List | `claw skill list` | Show all discovered skills |
| Run | `claw skill run my-skill` | Execute with dependency check |
| Uninstall | Remove the directory | `rm -rf skills/my-skill` |

---

## Custom Workflows

Workflows are YAML-defined multi-step pipelines that chain together shell commands, Claude prompts, skills, HTTP requests, and human approval gates. They live in the `workflows/` directory.

### Writing a Workflow YAML

Create a file in `workflows/`:

```yaml
# workflows/nightly-maintenance.yaml
name: nightly-maintenance
description: "Run backups, prune Docker images, check SSL certs, send report"
notify_profile: info

steps:
  - name: backup-databases
    type: shell
    command: "pg_dump mydb | gzip > /backups/mydb-$(date +%Y%m%d).sql.gz"
    on_failure: abort
    timeout: 600

  - name: prune-docker
    type: shell
    command: "docker system prune -af --volumes"
    on_failure: continue

  - name: check-certs
    type: skill
    command: ssl-cert-check
    on_failure: continue

  - name: summarize
    type: claude_prompt
    command: "Summarize tonight's maintenance: backup status, docker prune results, and SSL cert status."
    on_failure: continue

rollback:
  - name: notify-failure
    type: shell
    command: "echo 'Nightly maintenance failed' | mail -s 'ALERT' admin@example.com"
```

### Workflow YAML Schema

**Top-level fields:**

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `name` | yes | -- | string | Unique workflow identifier |
| `description` | yes | -- | string | Human-readable summary |
| `notify_profile` | no | `""` | string | Notification profile to use on completion |
| `steps` | yes | -- | list | Ordered list of step configurations |
| `rollback` | no | `[]` | list | Steps to execute when `on_failure: rollback` triggers |

**Step fields:**

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `name` | yes | -- | string | Step identifier (used in output and conditions) |
| `type` | yes | -- | enum | `shell`, `claude_prompt`, `skill`, `http`, `approval_gate` |
| `command` | yes | -- | string | Command, prompt, skill name, or URL depending on type |
| `on_failure` | no | `abort` | enum | `abort` (stop), `continue` (proceed), `rollback` (run rollback steps) |
| `timeout` | no | `300` | integer | Maximum seconds before step is killed |
| `condition` | no | `""` | string | `previous.ok`, `previous.failed`, `always`, or `""` (always) |
| `args` | no | `{}` | dict | Extra arguments (step-type specific) |

### Step Types in Detail

**`shell`** -- Runs a command via `subprocess.run()`. Extra `args` are injected as `WF_<KEY>` environment variables.

```yaml
- name: build
  type: shell
  command: "make build"
  args:
    target: production
    parallel: "4"
  # Available in script as $WF_TARGET and $WF_PARALLEL
```

**`claude_prompt`** -- Runs `claude -p "<prompt>" --output-format text`. The prompt text goes in the `command` field.

```yaml
- name: analyze-logs
  type: claude_prompt
  command: "Read /var/log/syslog from the last hour and list any anomalies."
  timeout: 120
```

**`skill`** -- Executes a registered skill by name. The `args` dict is passed to the skill loader.

```yaml
- name: scan-network
  type: skill
  command: network-scan
  args:
    subnet: "192.168.30.0/24"
```

**`http`** -- Makes an HTTP request. Default method is POST. Configure via `args`:

```yaml
- name: health-check
  type: http
  command: "http://localhost:8100/health"
  args:
    method: GET
    headers:
      Authorization: "Bearer ${API_TOKEN}"
    body:
      check: full
```

**`approval_gate`** -- Pauses for human confirmation via stdin. Auto-approved in `--dry-run` mode.

```yaml
- name: confirm-deploy
  type: approval_gate
  args:
    prompt: "Tests passed. Deploy to production? [y/N] "
```

### Conditions

Steps can be conditionally executed based on the previous step's result:

| Condition | Behavior |
|-----------|----------|
| `previous.ok` | Run only if the previous step passed |
| `previous.failed` | Run only if the previous step failed |
| `always` | Run regardless of previous step status |
| `""` (empty/default) | Always run |

Example -- send an alert only on failure:

```yaml
- name: deploy
  type: shell
  command: "docker compose up -d"
  on_failure: continue

- name: alert-on-failure
  type: shell
  command: "claw msg notify critical 'Deploy failed!'"
  condition: previous.failed
```

### Quality Gates and Rollback

When a step with `on_failure: rollback` fails, the engine immediately executes all steps in the `rollback` section, then stops. Rollback steps run unconditionally and in order.

```yaml
steps:
  - name: deploy
    type: shell
    command: "docker compose up -d --build"
    on_failure: rollback

rollback:
  - name: revert
    type: shell
    command: "docker compose down && git checkout HEAD~1 && docker compose up -d"
  - name: notify
    type: shell
    command: "claw msg notify critical 'Deploy rolled back'"
```

### Notifications

Set `notify_profile` to a profile name from `~/.claude-superpowers/profiles.yaml`. After the workflow completes (success or failure), a summary message is sent via the messaging system:

```
Workflow 'deploy': 4 passed, 0 failed
```

### CLI Reference

```bash
claw workflow list                  # List available workflows
claw workflow show <name>           # Show steps in detail
claw workflow run <name>            # Execute workflow
claw workflow run <name> --dry-run  # Preview without executing
claw workflow validate <name>       # Check for errors
claw workflow init                  # Install built-in templates
```

---

## Custom Cron Jobs

The cron subsystem supports four job types, three schedule formats, per-job model overrides, and output routing to messaging channels.

### Job Types

**`shell`** -- Run any command as a subprocess. The daemon's environment (including `.env` values) is inherited.

```bash
claw cron add backup-check \
  --type shell \
  --command "ssh truenas 'zpool status'" \
  --schedule "daily at 09:00"
```

**`claude`** -- Launch a headless Claude session via `claude -p`. The `--prompt` flag provides the prompt text.

```bash
claw cron add daily-summary \
  --type claude \
  --prompt "Review today's cron output and summarize in 5 bullet points." \
  --schedule "daily at 18:00"
```

**`webhook`** -- Send an HTTP POST to a URL with optional JSON body.

```bash
claw cron add slack-morning \
  --type webhook \
  --url "https://hooks.slack.com/services/T00/B00/xxx" \
  --body '{"text":"Good morning. All systems operational."}' \
  --schedule "0 8 * * 1-5"
```

**`skill`** -- Invoke a registered skill by name.

```bash
claw cron add heartbeat-15m \
  --type skill \
  --skill heartbeat \
  --schedule "every 15m"
```

### Schedule Syntax

| Format | Example | Description |
|--------|---------|-------------|
| Cron expression | `"0 */6 * * *"` | Standard 5-field cron: `minute hour day month weekday` |
| Interval | `"every 6h"` | Units: `s`, `m`, `h`, `d`. One unit at a time. |
| Daily-at | `"daily at 09:00"` | Once per day at the specified HH:MM |

Cron expressions follow `minute hour day month weekday`. Interval strings accept `every <N><unit>` where unit is `s` (seconds), `m` (minutes), `h` (hours), or `d` (days).

### Output Routing

Every job writes output to a structured log path:

```
~/.claude-superpowers/cron/output/{job-id}/{timestamp}.log
```

Optionally route output to a messaging channel or notification profile:

```bash
# Direct channel routing
claw cron add health-check \
  --type skill \
  --skill heartbeat \
  --schedule "every 30m" \
  --output "slack:#alerts"

# Profile routing
claw cron add health-check \
  --type skill \
  --skill heartbeat \
  --schedule "every 30m" \
  --output critical
```

Output format: `<channel>:<target>` for direct routing, or `<profile_name>` for profile-based fan-out.

Messaging failures are silently caught -- they never break job execution.

### Per-Job Model Overrides

Each cron job can override the LLM model used for `claude`-type jobs. This is useful for routing expensive analysis to a specific model while keeping lighter tasks on the default.

```python
engine.add_job(
    name="deep-analysis",
    schedule="daily at 02:00",
    job_type="claude",
    command="Analyze all system logs for the past 24 hours...",
    llm_model="claude-sonnet-4-20250514",  # Override for this job
)
```

The model resolution order is:
1. Per-job `llm_model` field (if non-empty)
2. `JOB_MODEL` environment variable
3. Default: `"claude"`

The resolved model is set as the `LLM_MODEL` environment variable in the job subprocess.

### Job Environment Variables

Shell-type jobs receive extra environment variables from the `args` dict, prefixed with `JOB_`:

```python
engine.add_job(
    name="scan",
    schedule="every 6h",
    job_type="shell",
    command="nmap -sn $JOB_SUBNET",
    args={"subnet": "192.168.30.0/24"},
)
```

Inside the shell, `$JOB_SUBNET` is `192.168.30.0/24`.

---

## Custom Channel Adapters

The messaging system uses a registry of channel adapters, each implementing a common interface. Adding a new channel requires three files.

### The Channel Contract

Every channel adapter extends `superpowers.channels.base.Channel`:

```python
from superpowers.channels.base import Channel, ChannelType, SendResult


class Channel:
    """Base class for messaging channel adapters."""

    channel_type: ChannelType

    def send(self, target: str, message: str) -> SendResult:
        """Send a message to the specified target.

        Args:
            target: Channel-specific destination (Slack channel, email address, etc.)
            message: Message text to send.

        Returns:
            SendResult with ok=True on success, ok=False with error on failure.
        """
        raise NotImplementedError

    def test_connection(self) -> SendResult:
        """Verify credentials and connectivity.

        Returns:
            SendResult with ok=True if the adapter can send messages.
        """
        raise NotImplementedError
```

The `SendResult` dataclass:

```python
@dataclass
class SendResult:
    ok: bool          # Whether the send succeeded
    channel: str      # Channel name (e.g., "slack")
    target: str       # Where the message was sent
    message: str = "" # Success details (e.g., message ID)
    error: str = ""   # Error description on failure
```

### Adding a New Channel: Step by Step

**1. Define the ChannelType enum value.**

Edit `superpowers/channels/base.py` and add your channel to the `ChannelType` enum:

```python
class ChannelType(StrEnum):
    slack = "slack"
    telegram = "telegram"
    discord = "discord"
    email = "email"
    imessage = "imessage"
    matrix = "matrix"       # New channel
```

**2. Create the adapter module.**

Create `superpowers/channels/matrix.py`:

```python
"""Matrix channel adapter."""
from __future__ import annotations

from superpowers.channels.base import Channel, ChannelError, ChannelType, SendResult


class MatrixChannel(Channel):
    channel_type = ChannelType.matrix

    def __init__(self, homeserver: str, access_token: str):
        if not homeserver or not access_token:
            raise ChannelError("Matrix homeserver URL and access token are required")
        self._homeserver = homeserver.rstrip("/")
        self._token = access_token

    def send(self, target: str, message: str) -> SendResult:
        """Send a message to a Matrix room.

        Args:
            target: Room ID (e.g., "!abc123:matrix.org")
            message: Plain text message.
        """
        import json
        import urllib.request

        url = f"{self._homeserver}/_matrix/client/r0/rooms/{target}/send/m.room.message"
        data = json.dumps({"msgtype": "m.text", "body": message}).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return SendResult(ok=True, channel="matrix", target=target)
        except Exception as exc:
            return SendResult(
                ok=False, channel="matrix", target=target, error=str(exc),
            )

    def test_connection(self) -> SendResult:
        import urllib.request

        url = f"{self._homeserver}/_matrix/client/r0/account/whoami"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self._token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return SendResult(ok=True, channel="matrix", target="")
        except Exception as exc:
            return SendResult(
                ok=False, channel="matrix", target="", error=str(exc),
            )
```

**3. Register the adapter in the channel registry.**

Edit `superpowers/channels/registry.py`:

Add availability detection in the `available()` method:

```python
def available(self) -> list[str]:
    names = []
    # ... existing channels ...
    if s.matrix_homeserver and s.matrix_access_token:
        names.append("matrix")
    return names
```

Add the factory case in `_create()`:

```python
def _create(self, name: str) -> Channel:
    # ... existing channels ...
    elif name == ChannelType.matrix.value:
        from superpowers.channels.matrix import MatrixChannel
        return MatrixChannel(
            homeserver=s.matrix_homeserver,
            access_token=s.matrix_access_token,
        )
    else:
        raise ChannelError(f"Unknown channel: {name}")
```

**4. Add settings fields.**

Edit `superpowers/config.py` and add the credential fields to the `Settings` dataclass:

```python
# Matrix
matrix_homeserver: str = ""
matrix_access_token: str = ""
```

Add the `_env()` calls in `Settings.load()`:

```python
matrix_homeserver=_env("MATRIX_HOMESERVER"),
matrix_access_token=_env("MATRIX_ACCESS_TOKEN"),
```

**5. Add environment variables to `.env.example`:**

```bash
MATRIX_HOMESERVER=https://matrix.example.org
MATRIX_ACCESS_TOKEN=
```

The new channel is now available in all messaging commands:

```bash
claw msg test matrix
claw msg send matrix "!room:matrix.org" "Hello from claw"
```

It can also be used in notification profiles and cron output routing.

### Inbound Channel Adapters (Phase G)

For bidirectional channels that receive messages (webhooks, bot polling), an additional abstract base class is defined in `msg_gateway/channels/base.py`:

| Method | Description |
|--------|-------------|
| `receive(request) -> Message` | Parse inbound webhook payload |
| `acknowledge(message) -> None` | Send read receipt or reaction |
| `start_processing_indicator(message) -> None` | Show typing indicator |
| `send_response(message, response) -> None` | Send reply |
| `supports_streaming: bool` | Whether the adapter supports streaming responses |

This is separate from the simpler outbound-only `Channel` class. Existing adapters can migrate to this interface incrementally.

---

## Custom File Watchers

File watchers monitor directories for changes and trigger actions automatically. Rules are defined in `~/.claude-superpowers/watchers.yaml`.

### Watcher Rule Schema

```yaml
- name: screenshot-optimizer     # Unique rule ID (required)
  path: ~/Desktop/Screenshot*.png  # Directory or glob pattern (required)
  events: [created]              # Event types (default: [created])
  action: shell                  # Action type (required)
  command: "optipng $WATCHER_FILE"  # Action target (required)
  args: {}                       # Extra arguments (default: {})
  enabled: true                  # Active flag (default: true)
```

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `name` | yes | -- | string | Unique rule identifier |
| `path` | yes | -- | string | Directory or glob pattern to monitor |
| `events` | no | `[created]` | list[enum] | `created`, `modified`, `deleted`, `moved` |
| `action` | yes | -- | enum | `shell`, `skill`, `workflow`, `move`, `copy` |
| `command` | yes | -- | string | Command to run or target path |
| `args` | no | `{}` | dict | Extra arguments |
| `enabled` | no | `true` | boolean | Whether the rule is active |

### Action Types

| Action | `command` Value | Behavior |
|--------|----------------|----------|
| `shell` | Shell command | Runs command with `WATCHER_FILE` set to triggering path. Extra `args` are available as `WATCHER_{KEY}` env vars. |
| `skill` | Skill name | Runs the named skill with `file` argument set to the triggering path. |
| `workflow` | Workflow name | Triggers the named workflow. |
| `move` | Target directory | Moves the triggering file to the specified directory. |
| `copy` | Target directory | Copies the triggering file to the specified directory. |

### Event Types

| Event | Trigger |
|-------|---------|
| `created` | A new file appears in the watched directory |
| `modified` | An existing file's contents change |
| `deleted` | A file is removed |
| `moved` | A file is renamed or moved within/to the directory |

### Practical Watcher Examples

**Auto-optimize screenshots:**

```yaml
- name: screenshot-optimizer
  path: ~/Desktop/Screenshot*.png
  events: [created]
  action: shell
  command: "optipng $WATCHER_FILE && notify-send 'Optimized' \"$(basename $WATCHER_FILE)\""
```

**Process invoices with a skill:**

```yaml
- name: invoice-processor
  path: ~/Documents/invoices/*.pdf
  events: [created]
  action: skill
  command: process-invoice
```

**Backup config changes:**

```yaml
- name: config-backup
  path: /etc/nginx/conf.d/*.conf
  events: [modified]
  action: copy
  command: /backups/nginx-configs/
```

**Trigger a deploy workflow when a release tag appears:**

```yaml
- name: release-trigger
  path: ~/releases/*.tar.gz
  events: [created]
  action: workflow
  command: deploy
```

### Managing Watchers

```bash
claw watcher list               # List configured rules and status
claw watcher start              # Start the watcher daemon (foreground)
claw watcher test <rule-name>   # Simulate a created event for testing
```

The watcher daemon logs to `~/.claude-superpowers/logs/watcher-daemon.log`.

---

## Notification Profiles

Profiles map a name to one or more channel+target pairs, enabling fan-out messaging with a single command.

### Creating a Profile

Edit `~/.claude-superpowers/profiles.yaml`:

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

on-call:
  - channel: telegram
    target: "987654321"
  - channel: email
    target: oncall@example.com
```

### Profile Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| `channel` | enum | `slack`, `telegram`, `discord`, `email` (or any custom adapter) |
| `target` | string | Channel-specific destination: Slack channel name, Telegram chat ID, Discord channel ID, email address |

### Using Profiles

**From the CLI:**

```bash
claw msg notify critical "PVE1 is unresponsive"
```

**From a cron job (output routing):**

```bash
claw cron add health-check \
  --type skill --skill heartbeat \
  --schedule "every 30m" \
  --output critical
```

**From a workflow (completion notification):**

```yaml
name: deploy
notify_profile: critical
steps:
  # ...
```

**Programmatically:**

```python
from superpowers.channels.registry import ChannelRegistry
from superpowers.config import Settings
from superpowers.profiles import ProfileManager

settings = Settings.load()
registry = ChannelRegistry(settings)
pm = ProfileManager(registry)

results = pm.send("critical", "Database backup failed!")
for r in results:
    print(f"{r.channel}: {'OK' if r.ok else r.error}")
```

### Listing Profiles

```bash
claw msg profiles
```

Displays all defined profiles with their channel and target mappings.

---

## Dashboard Customization

The dashboard is a FastAPI application with Alpine.js + htmx on the frontend. It is structured around routers, each handling a specific subsystem.

### Architecture

```
dashboard/
  app.py              # FastAPI app, router registration, static mount
  deps.py             # Dependency injection (auth, settings)
  middleware.py        # Rate limiting middleware
  routers/            # One module per subsystem
    status.py         # /api/status
    cron.py           # /api/cron/*
    messaging.py      # /api/msg/*
    skills.py         # /api/skills/*
    workflows.py      # /api/workflows/*
    memory.py         # /api/memory/*
    ssh.py            # /api/ssh/*
    audit.py          # /api/audit/*
    vault.py          # /api/vault/*
    watchers.py       # /api/watchers/*
    browser.py        # /api/browser/*
    chat.py           # /api/chat/*
    notifications.py  # /api/notifications/*
    jobs.py           # /api/jobs/*
    settings.py       # /api/settings/*
    auth.py           # /auth/* (public, no auth required)
  static/             # Alpine.js + htmx SPA
```

### Adding a New API Router

**1. Create the router module.**

Create `dashboard/routers/my_feature.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_items():
    """List all items."""
    return {"items": []}


@router.post("/")
def create_item(name: str):
    """Create a new item."""
    return {"name": name, "status": "created"}


@router.get("/{item_id}")
def get_item(item_id: str):
    """Get a specific item."""
    return {"id": item_id}
```

**2. Register the router in `app.py`.**

Import and include the router in the protected API group:

```python
from dashboard.routers import my_feature

api_router.include_router(
    my_feature.router,
    prefix="/my-feature",
    tags=["my-feature"],
)
```

All routes under `api_router` are automatically protected by HTTP Basic auth.

**3. Add a frontend page (optional).**

Add an HTML page to `dashboard/static/` that uses htmx or Alpine.js to interact with your API endpoints:

```html
<div x-data="{ items: [] }" x-init="
  fetch('/api/my-feature/', { headers: { 'Authorization': 'Basic ' + btoa(user + ':' + pass) } })
    .then(r => r.json())
    .then(data => items = data.items)
">
  <template x-for="item in items">
    <div x-text="item.name"></div>
  </template>
</div>
```

### Existing API Endpoints

The dashboard exposes 44 REST endpoints across 15 routers. All `/api/*` endpoints require HTTP Basic authentication. The `/health` endpoint is public.

| Router | Prefix | Purpose |
|--------|--------|---------|
| `status` | `/api` | System status overview |
| `cron` | `/api/cron` | Cron job management |
| `messaging` | `/api/msg` | Send messages, list channels |
| `skills` | `/api/skills` | Skill listing and execution |
| `workflows` | `/api/workflows` | Workflow listing and execution |
| `memory` | `/api/memory` | Memory store CRUD |
| `ssh` | `/api/ssh` | Remote command execution |
| `audit` | `/api/audit` | Audit log search and tail |
| `vault` | `/api/vault` | Credential management |
| `watchers` | `/api/watchers` | File watcher management |
| `browser` | `/api/browser` | Browser automation |
| `chat` | `/api/chat` | Chat interface |
| `notifications` | `/api/notifications` | Notification management |
| `jobs` | `/api/jobs` | Job orchestration |
| `settings` | `/api/settings` | Runtime configuration |

---

## CLI Extensions

The `claw` CLI is built with Click 8.x. Each subsystem registers its commands through Click groups, and the main entry point (`superpowers/cli.py`) aggregates them all.

### How the CLI Is Structured

```python
# superpowers/cli.py
@click.group()
@click.version_option(version=__version__, prog_name="claw")
def main():
    """Claude Superpowers -- autonomous skill execution and orchestration."""

main.add_command(vault_group)
main.add_command(cron_group)
main.add_command(msg_group)
main.add_command(skill)           # Invocable group with subcommands
main.add_command(workflow_group)
main.add_command(ssh_group)
main.add_command(browse_group)
main.add_command(memory_group)
main.add_command(watcher_group)
main.add_command(audit_group)
main.add_command(intake_group)
main.add_command(template_group)
main.add_command(setup_group)
main.add_command(jobs_group)
main.add_command(daemon)
main.add_command(dashboard_cmd)
main.add_command(status_dashboard)
```

### Adding a New Subcommand

**1. Create a CLI module.**

Create `superpowers/cli_myfeature.py`:

```python
"""Click subcommands for my feature."""
from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("myfeature")
def myfeature_group():
    """Manage my custom feature."""


@myfeature_group.command("list")
def myfeature_list():
    """List all items."""
    table = Table(title="My Feature Items")
    table.add_column("Name", style="cyan")
    table.add_column("Status")
    # Add your items here
    console.print(table)


@myfeature_group.command("run")
@click.argument("name")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def myfeature_run(name: str, dry_run: bool):
    """Execute a named item."""
    if dry_run:
        console.print(f"[dim]Would execute: {name}[/dim]")
        return
    console.print(f"[green]Executing:[/green] {name}")
    # Implementation here
```

**2. Register in `cli.py`.**

```python
from superpowers.cli_myfeature import myfeature_group

main.add_command(myfeature_group)
```

**3. Verify.**

```bash
claw myfeature list
claw myfeature run my-item --dry-run
```

### CLI Conventions

The project follows these patterns for CLI commands:

- **Rich output**: Use `rich.console.Console` and `rich.table.Table` for formatted output
- **Click groups**: Each subsystem is a `@click.group()` with subcommands
- **Lazy imports**: Import heavy modules inside command functions, not at module level
- **Consistent naming**: Command groups use `<subsystem>_group` naming
- **Error handling**: Use `raise SystemExit(1)` for non-zero exits, `click.echo` for user-facing errors

---

## Environment and Config Overrides

### .env Variables

The `.env` file in the project root is loaded at startup by `superpowers/config.py`. Shell environment variables take precedence over `.env` values. The loader is a minimal built-in parser with no external dependency.

**Full variable reference:**

| Category | Variable | Default | Description |
|----------|----------|---------|-------------|
| LLM | `ANTHROPIC_API_KEY` | `""` | API key for claude-type jobs and intake |
| Messaging | `SLACK_BOT_TOKEN` | `""` | Slack bot token (`xoxb-...`) |
| Messaging | `TELEGRAM_BOT_TOKEN` | `""` | Telegram Bot API token |
| Messaging | `TELEGRAM_DEFAULT_CHAT_ID` | `""` | Default Telegram chat ID |
| Messaging | `DISCORD_BOT_TOKEN` | `""` | Discord bot token |
| Messaging | `SMTP_HOST` | `""` | SMTP server hostname |
| Messaging | `SMTP_USER` | `""` | SMTP login username |
| Messaging | `SMTP_PASS` | `""` | SMTP login password |
| Messaging | `SMTP_PORT` | `587` | SMTP port |
| Messaging | `SMTP_FROM` | `""` | From address for outbound emails |
| Dashboard | `DASHBOARD_USER` | `""` | HTTP Basic auth username (must be set) |
| Dashboard | `DASHBOARD_PASS` | `""` | HTTP Basic auth password (must be set) |
| Dashboard | `DASHBOARD_SECRET` | `""` | JWT signing secret (auto-generated if empty) |
| Infra | `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| Vault | `VAULT_IDENTITY_FILE` | `~/.claude-superpowers/vault.key` | age identity file path |
| SSH | `SSH_CONNECT_TIMEOUT` | `10` | SSH connection timeout (seconds) |
| SSH | `SSH_COMMAND_TIMEOUT` | `30` | SSH command timeout (seconds) |
| Home | `HOME_ASSISTANT_URL` | `""` | Home Assistant base URL |
| Home | `HOME_ASSISTANT_TOKEN` | `""` | Home Assistant access token |
| Model | `CHAT_MODEL` | `claude` | Model for interactive chat |
| Model | `JOB_MODEL` | `claude` | Model for background jobs |
| Telegram | `ALLOWED_CHAT_IDS` | `""` | Comma-separated allowlist (empty = all rejected) |
| Telegram | `TELEGRAM_SESSION_TTL` | `3600` | Session history TTL (seconds) |
| Telegram | `TELEGRAM_MAX_HISTORY` | `20` | Max messages per session |
| Telegram | `TELEGRAM_MAX_PER_CHAT` | `2` | Max concurrent jobs per chat |
| Telegram | `TELEGRAM_MAX_GLOBAL` | `5` | Max concurrent jobs globally |
| Telegram | `TELEGRAM_QUEUE_OVERFLOW` | `10` | Max queued jobs before rejecting |
| Telegram | `TELEGRAM_MODE` | `polling` | `webhook` or `polling` |
| Telegram | `TELEGRAM_WEBHOOK_SECRET` | `""` | Secret for webhook validation |
| Telegram | `TELEGRAM_WEBHOOK_URL` | `""` | Public URL for webhook endpoint |
| Telegram | `TELEGRAM_ADMIN_CHAT_ID` | `""` | Admin chat ID for access requests |
| Security | `ENVIRONMENT` | `development` | `development` or `production` |
| Security | `FORCE_HTTPS` | `false` | Enforce HTTPS transport |
| Security | `WEBHOOK_REQUIRE_SIGNATURE` | `true` | Fail-closed webhook validation |
| Security | `RATE_LIMIT_PER_IP` | `60` | Max requests per minute per IP |
| Security | `RATE_LIMIT_PER_USER` | `120` | Max requests per minute per user |
| Data | `SUPERPOWERS_DATA_DIR` | `~/.claude-superpowers` | Base data directory |
| Data | `CLAUDE_SUPERPOWERS_DATA_DIR` | `~/.claude-superpowers` | Legacy alias |

### Configuration Files

All runtime configuration lives in `~/.claude-superpowers/` (overridable via `SUPERPOWERS_DATA_DIR`):

| File | Format | Purpose |
|------|--------|---------|
| `hosts.yaml` | YAML | SSH host definitions |
| `profiles.yaml` | YAML | Notification profiles |
| `watchers.yaml` | YAML | File watcher rules |
| `rotation_policies.yaml` | YAML | Credential rotation policies |
| `templates.json` | JSON | Template manager manifest |
| `cron/jobs.json` | JSON | Cron job manifest |
| `cron/scheduler.db` | SQLite | APScheduler state |
| `memory.db` | SQLite | Persistent memory store |
| `vault.enc` | Binary | age-encrypted credentials |
| `age-identity.txt` | Text | age private key (chmod 600) |
| `audit.log` | JSONL | Append-only audit log |

### Data Directory Override

To relocate all runtime data:

```bash
export SUPERPOWERS_DATA_DIR=/data/claude-superpowers
claw vault init  # Creates the directory structure
```

The `Settings.ensure_dirs()` method creates all required subdirectories:

```
<data_dir>/
  skills/
  cron/
  vault/
  logs/
  msg/
  ssh/
  watcher/
  browser/
  browser/profiles/
  memory/
  workflows/
```

### Runtime Settings Access

Load settings programmatically:

```python
from superpowers.config import Settings

settings = Settings.load()
print(settings.redis_url)          # "redis://localhost:6379/0"
print(settings.data_dir)           # Path("~/.claude-superpowers")
print(settings.telegram_bot_token) # Value from .env or environment
```

Pass a custom `.env` path:

```python
settings = Settings.load(dotenv_path=Path("/etc/claw/.env"))
```

Run security validation at startup:

```python
warnings = settings.validate_security()
# Returns list of strings; each string is a security concern
```

---

## Template System

The template manager tracks shipped configuration files (workflow YAMLs, docker-compose files, `.env.example`), detects user modifications, and supports upgrade with backup. This prevents `git pull` from blindly overwriting customized config.

### How It Works

Templates are tracked in a JSON manifest at `~/.claude-superpowers/templates.json`. Each entry records:

- The template name
- The SHA-256 hash of the shipped version
- The SHA-256 hash of the installed version
- The destination path
- The installation timestamp

### Managed Templates

| Template | Source File | Description |
|----------|-------------|-------------|
| `docker-compose.yaml` | `docker-compose.yaml` | Docker Compose stack definition |
| `docker-compose.prod.yaml` | `docker-compose.prod.yaml` | Production Compose overrides |
| `workflows/deploy.yaml` | `workflows/deploy.yaml` | Deploy workflow |
| `workflows/backup.yaml` | `workflows/backup.yaml` | Backup workflow |
| `workflows/morning-brief.yaml` | `workflows/morning-brief.yaml` | Morning briefing workflow |
| `.env.example` | `.env.example` | Configuration template |

### Template Operations

**Initialize** -- Copy templates that do not yet exist at their destination:

```bash
claw template init
```

Only copies files that are missing. Existing files (even if modified) are left untouched.

**List** -- Show all tracked templates and their modification status:

```bash
claw template list
```

Status values:

| Status | Meaning |
|--------|---------|
| `current` | File matches the shipped version exactly |
| `modified` | User has changed the file since installation |
| `missing` | File was deleted by the user |
| `untracked` | Template has not been initialized yet |

**Diff** -- Show differences between current files and shipped versions:

```bash
claw template diff                    # All templates
claw template diff docker-compose.yaml  # Specific template
```

Output is in unified diff format.

**Reset** -- Restore a template to its shipped version. Creates a `.bak` backup of the current file:

```bash
claw template reset docker-compose.yaml
# Creates docker-compose.yaml.bak, then overwrites with shipped version
```

**Upgrade** -- Apply template updates from a new project version, preserving user customizations:

```bash
claw template upgrade
```

Upgrade behavior per template:

| Condition | Action |
|-----------|--------|
| File is unmodified by user | Replace with new shipped version |
| File has been modified by user | Create timestamped backup, then replace |
| File was deleted by user | Skip (respects intentional removal) |
| Source file is missing | Skip with "missing_source" status |

Backup files are named `<file>.<suffix>.<timestamp>.bak` (e.g., `docker-compose.yaml.20260303120000.bak`).

### Programmatic Access

```python
from superpowers.template_manager import TemplateManager

tm = TemplateManager()

# Initialize templates
installed = tm.init()

# List with status
for t in tm.list_templates():
    print(f"{t['name']}: {t['status']}")

# Check diffs
diffs = tm.diff("docker-compose.yaml")
if diffs["docker-compose.yaml"]:
    print("File has been modified")

# Reset to shipped version
tm.reset("docker-compose.yaml")

# Upgrade all templates
actions = tm.upgrade()
for name, action in actions.items():
    print(f"{name}: {action}")
```

### Custom Template Sources

Override the default template sources when constructing the manager:

```python
tm = TemplateManager(
    project_dir=Path("/home/ray/claude-superpowers"),
    template_sources={
        "my-config.yaml": "deploy/my-config.yaml",
        "custom-workflow.yaml": "workflows/custom-workflow.yaml",
    },
)
```

---

## Examples

### Example 1: SSL Certificate Monitor with Alerts

Create a skill that checks SSL certificate expiration across your domains and sends alerts through a notification profile.

**1. Create the skill:**

```bash
mkdir -p skills/ssl-monitor
```

`skills/ssl-monitor/skill.yaml`:

```yaml
name: ssl-monitor
version: "0.1.0"
description: "Check SSL certificate expiration and alert on upcoming renewals"
author: DreDay
script: run.sh
slash_command: true
dependencies: [openssl]
permissions: []
triggers: []
```

`skills/ssl-monitor/run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

DOMAINS="${SKILL_DOMAINS:-example.com,api.example.com,app.example.com}"
WARN_DAYS="${SKILL_WARN_DAYS:-30}"
EXIT_CODE=0

echo "[ssl-monitor] Checking certificates (warn < ${WARN_DAYS} days)"
echo ""

IFS=',' read -ra DOMAIN_LIST <<< "$DOMAINS"
for domain in "${DOMAIN_LIST[@]}"; do
    expiry=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null \
        | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

    if [ -z "$expiry" ]; then
        echo "FAIL  $domain -- could not retrieve certificate"
        EXIT_CODE=1
        continue
    fi

    expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$expiry" +%s 2>/dev/null)
    now_epoch=$(date +%s)
    days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

    if [ "$days_left" -lt "$WARN_DAYS" ]; then
        echo "WARN  $domain -- expires in ${days_left} days ($expiry)"
        EXIT_CODE=1
    else
        echo "OK    $domain -- expires in ${days_left} days"
    fi
done

exit $EXIT_CODE
```

```bash
chmod +x skills/ssl-monitor/run.sh
claw skill sync
```

**2. Create a notification profile:**

Add to `~/.claude-superpowers/profiles.yaml`:

```yaml
ssl-alerts:
  - channel: slack
    target: "#infrastructure"
  - channel: email
    target: ops@example.com
```

**3. Schedule the check:**

```bash
claw cron add ssl-check-daily \
  --type skill \
  --skill ssl-monitor \
  --schedule "daily at 08:00" \
  --output ssl-alerts
```

**4. Test it:**

```bash
claw skill run ssl-monitor domains=example.com,google.com warn_days=90
```

---

### Example 2: Deploy Workflow with Approval Gate and Rollback

Create a custom workflow that pulls code, runs tests, waits for manual approval, deploys, runs a health check, and rolls back on failure.

`workflows/staging-deploy.yaml`:

```yaml
name: staging-deploy
description: "Deploy to staging with approval gate and automatic rollback"
notify_profile: critical

steps:
  - name: git-pull
    type: shell
    command: "git -C /opt/myapp pull origin staging"
    on_failure: abort

  - name: install-deps
    type: shell
    command: "cd /opt/myapp && pip install -r requirements.txt"
    on_failure: abort
    timeout: 120

  - name: run-tests
    type: shell
    command: "cd /opt/myapp && PYTHONPATH=. pytest tests/ -q --tb=short"
    on_failure: abort
    timeout: 300

  - name: approve-deploy
    type: approval_gate
    args:
      prompt: "Tests passed. Deploy to staging? [y/N] "

  - name: docker-deploy
    type: shell
    command: "cd /opt/myapp && docker compose -f docker-compose.staging.yaml up -d --build"
    on_failure: rollback
    timeout: 180

  - name: health-check
    type: http
    command: "http://staging.example.com/health"
    args:
      method: GET
    on_failure: rollback
    timeout: 30

  - name: smoke-test
    type: skill
    command: qa-guardian
    on_failure: rollback

rollback:
  - name: revert-containers
    type: shell
    command: "cd /opt/myapp && docker compose -f docker-compose.staging.yaml down"
  - name: revert-code
    type: shell
    command: "git -C /opt/myapp checkout HEAD~1"
  - name: redeploy-previous
    type: shell
    command: "cd /opt/myapp && docker compose -f docker-compose.staging.yaml up -d"
  - name: notify-rollback
    type: shell
    command: "claw msg notify critical 'Staging deploy rolled back to previous version'"
```

Test it first:

```bash
claw workflow run staging-deploy --dry-run
```

Then execute:

```bash
claw workflow run staging-deploy
```

---

### Example 3: Automated Log Ingestion Pipeline

Combine a file watcher, a custom skill, and a cron job to automatically process and summarize log files.

**1. Create the log processor skill:**

`skills/log-ingest/skill.yaml`:

```yaml
name: log-ingest
version: "0.1.0"
description: "Parse and index a log file into the memory store"
author: DreDay
script: run.py
slash_command: false
dependencies: []
permissions: []
```

`skills/log-ingest/run.py`:

```python
#!/usr/bin/env python3
"""log-ingest -- Parse a log file and store key events in memory."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def main() -> int:
    log_file = os.environ.get("SKILL_FILE") or os.environ.get("WATCHER_FILE")
    if not log_file:
        print("[log-ingest] Error: no file specified")
        return 1

    path = Path(log_file)
    if not path.exists():
        print(f"[log-ingest] File not found: {path}")
        return 1

    errors = []
    warnings = []
    for line in path.read_text().splitlines():
        if re.search(r"\bERROR\b", line, re.IGNORECASE):
            errors.append(line.strip())
        elif re.search(r"\bWARN(ING)?\b", line, re.IGNORECASE):
            warnings.append(line.strip())

    print(f"[log-ingest] Processed {path.name}")
    print(f"  Errors:   {len(errors)}")
    print(f"  Warnings: {len(warnings)}")

    if errors:
        print("\n  Top errors:")
        for e in errors[:5]:
            print(f"    {e[:120]}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
```

```bash
chmod +x skills/log-ingest/run.py
```

**2. Set up the file watcher:**

Add to `~/.claude-superpowers/watchers.yaml`:

```yaml
- name: log-ingest
  path: /var/log/myapp/*.log
  events: [modified]
  action: skill
  command: log-ingest
  enabled: true
```

**3. Schedule a daily summary:**

```bash
claw cron add log-summary \
  --type claude \
  --prompt "Review today's log-ingest output in ~/.claude-superpowers/cron/output/ and write a summary of errors and warnings across all processed logs." \
  --schedule "daily at 23:00" \
  --output daily-digest
```

**4. Start the watcher:**

```bash
claw watcher start
```

Now whenever a log file is modified in `/var/log/myapp/`, the `log-ingest` skill runs automatically. At 11 PM, Claude summarizes the day's findings and sends them to the `daily-digest` notification profile.

---

### Example 4: Adding a Custom CLI Command with Dashboard Integration

Create a `claw inventory` command that tracks hardware inventory, with a matching dashboard API endpoint.

**1. Create the CLI module.**

`superpowers/cli_inventory.py`:

```python
"""Click subcommands for hardware inventory tracking."""
from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from superpowers.config import get_data_dir

console = Console()


def _inventory_path() -> Path:
    return get_data_dir() / "inventory.json"


def _load() -> list[dict]:
    path = _inventory_path()
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _save(items: list[dict]) -> None:
    path = _inventory_path()
    path.write_text(json.dumps(items, indent=2))


@click.group("inventory")
def inventory_group():
    """Track hardware inventory."""


@inventory_group.command("list")
def inventory_list():
    """List all inventory items."""
    items = _load()
    if not items:
        console.print("[dim]No inventory items.[/dim]")
        return

    table = Table(title="Hardware Inventory")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("IP")
    table.add_column("Status")

    for item in items:
        table.add_row(
            item.get("name", ""),
            item.get("type", ""),
            item.get("ip", ""),
            item.get("status", "unknown"),
        )
    console.print(table)


@inventory_group.command("add")
@click.argument("name")
@click.option("--type", "item_type", default="server", help="Device type")
@click.option("--ip", default="", help="IP address")
def inventory_add(name: str, item_type: str, ip: str):
    """Add an inventory item."""
    items = _load()
    items.append({"name": name, "type": item_type, "ip": ip, "status": "active"})
    _save(items)
    console.print(f"[green]Added:[/green] {name}")
```

**2. Register in `cli.py`:**

```python
from superpowers.cli_inventory import inventory_group

main.add_command(inventory_group)
```

**3. Create the dashboard router.**

`dashboard/routers/inventory.py`:

```python
import json
from pathlib import Path

from fastapi import APIRouter

from superpowers.config import get_data_dir

router = APIRouter()


def _inventory_path() -> Path:
    return get_data_dir() / "inventory.json"


@router.get("/")
def list_inventory():
    path = _inventory_path()
    if not path.exists():
        return {"items": []}
    return {"items": json.loads(path.read_text())}


@router.post("/")
def add_inventory(name: str, item_type: str = "server", ip: str = ""):
    path = _inventory_path()
    items = json.loads(path.read_text()) if path.exists() else []
    items.append({"name": name, "type": item_type, "ip": ip, "status": "active"})
    path.write_text(json.dumps(items, indent=2))
    return {"status": "created", "name": name}
```

**4. Register in `dashboard/app.py`:**

```python
from dashboard.routers import inventory

api_router.include_router(
    inventory.router, prefix="/inventory", tags=["inventory"],
)
```

**5. Verify:**

```bash
claw inventory add proxmox --type hypervisor --ip 192.168.30.10
claw inventory add truenas --type storage --ip 192.168.13.69
claw inventory list

# API access
curl -u "admin:pass" http://localhost:8200/api/inventory/
```

---

## Further Reading

| Topic | Document |
|-------|----------|
| Full config reference | [CONFIGURATION.md](CONFIGURATION.md) |
| Security model and hardening | [SECURITY.md](SECURITY.md) |
| Deployment guide | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Upgrade procedures | [UPGRADE.md](UPGRADE.md) |
| Operational runbooks | [RUNBOOKS.md](RUNBOOKS.md) |
| Skill system details | [skills.md](skills.md) |
| Workflow engine | [workflows.md](workflows.md) |
| Cron scheduler | [cron.md](cron.md) |
| Messaging channels | [messaging.md](messaging.md) |
| File watchers | [watchers.md](watchers.md) |
| Dashboard and API | [dashboard.md](dashboard.md) |
| MCP tools for Claude Code | [mcp-server.md](mcp-server.md) |
