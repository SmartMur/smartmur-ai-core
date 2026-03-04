# Workflows — Phase 6

YAML-driven multi-step workflow engine with conditions, rollback, and notifications.

## Quick Start

```bash
# Install built-in templates
claw workflow init

# List available workflows
claw workflow list

# Preview a workflow (dry run)
claw workflow run deploy --dry-run

# Execute for real
claw workflow run deploy
```

## Workflow YAML Format

```yaml
name: deploy
description: "Pull, test, deploy, verify"
notify_profile: critical  # optional: send summary via notification profile

steps:
  - name: git-pull
    type: shell
    command: "git pull origin main"
    on_failure: abort       # abort | continue | rollback

  - name: run-tests
    type: shell
    command: "PYTHONPATH=. pytest tests/ -q"
    on_failure: abort

  - name: approve
    type: approval_gate
    args:
      prompt: "Tests passed. Deploy to production? [y/N] "

  - name: deploy
    type: shell
    command: "docker compose up -d --build"
    on_failure: rollback
    timeout: 120

  - name: health-check
    type: http
    command: "http://localhost:8100/health"
    args:
      method: GET
    on_failure: rollback

rollback:
  - name: undo-deploy
    type: shell
    command: "docker compose down && git checkout HEAD~1 && docker compose up -d"
```

## Step Types

| Type | Description |
|------|-------------|
| `shell` | Run a shell command via `subprocess.run()` |
| `claude_prompt` | Run `claude -p "prompt" --output-format text` |
| `skill` | Execute a registered skill by name |
| `http` | HTTP request (POST by default, configurable via args) |
| `approval_gate` | Pause for human confirmation (auto-approved in dry-run) |

## Step Options

| Field | Default | Description |
|-------|---------|-------------|
| `on_failure` | `abort` | What to do if step fails: `abort`, `continue`, `rollback` |
| `timeout` | `300` | Max seconds before step is killed |
| `condition` | `""` | Condition to evaluate: `previous.ok`, `previous.failed`, `always` |
| `args` | `{}` | Extra arguments (passed as `WF_*` env vars for shell steps) |

## CLI Reference

```
claw workflow list              # List available workflows
claw workflow show NAME         # Show steps in detail
claw workflow run NAME          # Execute workflow
claw workflow run NAME --dry-run  # Preview without executing
claw workflow validate NAME     # Check for errors
claw workflow init              # Install built-in templates
```

## Built-in Workflows

- **deploy** — git pull → test → docker compose up → health check (with rollback)
- **backup** — snapshot VMs → verify snapshots
- **morning-brief** — heartbeat skill → Claude summary

## Conditions

Steps can have a `condition` field that controls whether they run:

- `previous.ok` — only run if the previous step passed
- `previous.failed` — only run if the previous step failed
- `always` — always run regardless of previous step status
- (empty) — always run (default)

## Rollback

When a step with `on_failure: rollback` fails, the engine executes all steps in the `rollback` section, then stops the workflow.

## Notifications

Set `notify_profile` to a notification profile name. After the workflow completes, a summary is sent via the messaging system (Phase 3).
