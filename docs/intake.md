# Intake Orchestration

## Overview

The intake system is the mandatory request bootstrap pipeline for every incoming task. It clears stale runtime context, extracts structured requirements from free-form text, maps each requirement to a skill (auto-installing from templates when needed), assigns agent roles, optionally executes all tasks in parallel, persists the session to disk, and sends progress notifications to Telegram.

The pipeline is driven by `claw intake run` and implemented across four modules:

| Module | Path | Purpose |
|--------|------|---------|
| `intake` | `superpowers/intake.py` | Core pipeline: clear, plan, map, execute, save |
| `cli_intake` | `superpowers/cli_intake.py` | Click CLI commands and Telegram notification logic |
| `role_router` | `superpowers/role_router.py` | Keyword-based role assignment and skill gating |
| `intake_telemetry` | `superpowers/intake_telemetry.py` | Structured audit events for each lifecycle phase |

Supporting module:

| Module | Path | Purpose |
|--------|------|---------|
| `auto_install` | `superpowers/auto_install.py` | Skill matching, template installation, generic scaffolding |

## How It Works

### Pipeline Phases

Every call to `claw intake run` executes these phases in order:

1. **Context clearing** -- Deletes all `*.json` files in `~/.claude-superpowers/runtime/` and writes a fresh `context-cleared.json` marker with a UTC timestamp.

2. **Requirement extraction** -- Splits the input text into actionable lines. Bullet prefixes (`-`, `*`) are stripped. If no line breaks are found, the entire input becomes a single requirement.

3. **Plan building** -- Creates an `IntakeTask` for each requirement. Tasks start in `planned` status with no skill assigned.

4. **Role assignment** -- The `RoleRouter` scans each requirement for keywords and assigns one of three roles: `planner`, `executor`, or `verifier`. If a `--role` filter is active, non-matching tasks are immediately skipped.

5. **Skill mapping** -- For each non-skipped task, `auto_install.check_and_install()` attempts to find or create a matching skill:
   - First, searches existing registered skills for token overlap with the requirement text.
   - If no match, checks the 5 built-in templates (`network-scan`, `disk-usage`, `git-stats`, `docker-health`, `log-search`).
   - If no template matches, scaffolds a generic bash skill from the requirement description.

6. **Execution** (only with `--execute`) -- Runs all mapped skills in parallel using a `ThreadPoolExecutor`. Each task runs sandboxed via `SkillLoader.run_sandboxed()`. Output is captured and truncated to 2000 characters.

7. **Session persistence** -- Writes the full session payload (requirements, tasks, role assignments, timestamps) to `~/.claude-superpowers/runtime/current_request.json`.

8. **Notification** -- If Telegram is configured, sends start and finish messages with task counts and status summaries. Uses retry with exponential backoff for chat ID discovery. Queues messages to a JSONL file when no chat ID is available.

### IntakeTask Lifecycle

Each task moves through these statuses:

| Status | Meaning |
|--------|---------|
| `planned` | Created but not yet mapped or executed |
| `running` | Skill execution in progress |
| `ok` | Skill completed with exit code 0 |
| `failed` | Skill not found, mapping failed, or non-zero exit |
| `skipped` | Excluded by role filter or no mapped skill |

### Role Routing

The `RoleRouter` assigns one of three roles to each task based on keywords found in the requirement text.

**Roles:**

| Role | Description | Trigger Keywords |
|------|-------------|-----------------|
| `planner` | Analysis, design, and planning tasks | plan, analyze, design, review, decompose, suggest, assess, propose, outline, evaluate |
| `executor` | Direct action and execution tasks | (default -- assigned when no planner/verifier keywords match) |
| `verifier` | Validation, testing, and auditing tasks | verify, test, check, validate, audit, confirm, assert, inspect, scan, lint |

Role assignment is keyword-based: the router tokenizes the requirement, checks for overlap with the planner keyword set first, then the verifier set. If neither matches, the task defaults to `executor`.

**Per-role skill filtering:**

Each role maps to a set of allowed skill types:

| Role | Allowed Skill Types |
|------|-------------------|
| `planner` | `planning`, `analysis` |
| `executor` | `execution`, `""` (default/untyped) |
| `verifier` | `validation`, `testing` |

The `RoleRouter.filter_skills()` method returns only skills whose `skill_type` attribute falls within the allowed set for a given role.

**CLI role override:**

Pass `--role <role>` to `claw intake run` to restrict execution to tasks assigned to a specific role. Tasks assigned to other roles are skipped with a diagnostic message.

### Telemetry

The `IntakeTelemetry` class emits structured audit events to `~/.claude-superpowers/audit.log` (JSON Lines format) at each pipeline phase. It wraps the shared `AuditLog` module.

**Lifecycle events:**

| Event | Action String | When Emitted | Metadata |
|-------|--------------|--------------|----------|
| Context cleared | `intake.context_cleared` | After runtime dir cleanup | `runtime_dir` |
| Requirements extracted | `intake.requirements_extracted` | After text parsing | `count`, `preview` (first 200 chars) |
| Plan built | `intake.plan_built` | After task list creation | `task_count` |
| Skill mapped | `intake.skill_mapped` | When a skill is found for a task | `task_id`, `requirement`, `skill` |
| Skill map failed | `intake.skill_map_failed` | When no skill can be found | `task_id`, `requirement` |
| Task started | `intake.task_started` | Before skill execution begins | `task_id`, `skill` |
| Task completed | `intake.task_completed` | After skill execution finishes | `task_id`, `skill`, `status`, `duration_ms` |
| Session saved | `intake.session_saved` | After JSON persistence | `total`, `ok`, `failed`, `execute` |
| Notification sent | `intake.notification` | After each Telegram send attempt | `channel`, `phase`, `success` |

Each event is an append-only JSON line with a UTC `ts` timestamp, `action`, `detail`, `source` ("intake"), and optional `metadata` dict.

### Telegram Notification Flow

The CLI layer handles Telegram notifications around the pipeline:

1. **Start notification** -- Sent before the pipeline runs, includes `execute` mode, `role` filter, and the first 300 characters of the request.
2. **Finish notification** -- Sent after completion, includes task counts by status (`ok`, `failed`, `planned`, `running`, `skipped`).

**Chat ID resolution order:**

1. `--telegram-chat` CLI flag (explicit override)
2. `TELEGRAM_DEFAULT_CHAT_ID` environment variable
3. Auto-discovery via `getUpdates` API (polls the bot's last 25 updates for a chat ID)

**Queuing:** When no chat ID can be resolved, messages are appended to `~/.claude-superpowers/runtime/pending_telegram_updates.jsonl`. These are automatically flushed when a subsequent send succeeds, or manually via `claw intake flush-telegram`.

## CLI Reference

### `claw intake clear`

Clear runtime context files. Removes all `*.json` from the runtime directory and writes a fresh marker.

```bash
claw intake clear
```

```
Context cleared. /home/ray/.claude-superpowers/runtime/context-cleared.json
```

### `claw intake run`

Run the full intake pipeline: clear context, extract requirements, map skills, assign roles, optionally execute.

```bash
claw intake run <request_text> [options]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--execute` | off | Execute mapped skills in parallel after planning |
| `--max-workers` | 4 | Maximum parallel skill executions |
| `--notify-telegram / --no-notify-telegram` | on | Send start/finish updates to Telegram |
| `--telegram-chat` | `""` | Override Telegram chat_id for this run |
| `--role` | `all` | Only run tasks assigned to this role (`planner`, `executor`, `verifier`, `all`) |

**Output:** A Rich table showing task ID, requirement, assigned role, mapped skill, status, and any error messages.

### `claw intake show`

Display the current session JSON from the last intake run.

```bash
claw intake show
```

Reads and pretty-prints `~/.claude-superpowers/runtime/current_request.json`. Shows nothing if no session exists.

### `claw intake flush-telegram`

Flush queued Telegram updates that were saved when no chat ID was available.

```bash
claw intake flush-telegram [--telegram-chat <chat_id>]
```

Uses the same chat ID resolution order as `claw intake run`. Exits with code 1 if no chat ID can be determined.

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | For notifications | Telegram Bot API token |
| `TELEGRAM_DEFAULT_CHAT_ID` | Recommended | Default chat ID for Telegram notifications. Without this, the system falls back to auto-discovery or queuing. |
| `CLAUDE_SUPERPOWERS_DATA_DIR` | No | Override the base data directory (default: `~/.claude-superpowers`) |

### File Paths

| Path | Purpose |
|------|---------|
| `~/.claude-superpowers/runtime/` | Runtime context files |
| `~/.claude-superpowers/runtime/current_request.json` | Current/last session payload |
| `~/.claude-superpowers/runtime/context-cleared.json` | Context-cleared marker |
| `~/.claude-superpowers/runtime/pending_telegram_updates.jsonl` | Queued Telegram messages |
| `~/.claude-superpowers/audit.log` | Telemetry event log (JSON Lines) |

## Examples

### Basic single-task intake (plan only)

```bash
claw intake run "check disk usage on all servers"
```

```
                     Request Intake
┌───┬──────────────────────────────────────┬──────────┬────────────┬─────────┬───────┐
│ # │ Requirement                          │ Role     │ Skill      │ Status  │ Error │
├───┼──────────────────────────────────────┼──────────┼────────────┼─────────┼───────┤
│ 1 │ check disk usage on all servers      │ verifier │ disk-usage │ planned │       │
└───┴──────────────────────────────────────┴──────────┴────────────┴─────────┴───────┘
Session saved to ~/.claude-superpowers/runtime/current_request.json
```

### Multi-requirement intake

Pass a multi-line string with bullet points. Each line becomes a separate task:

```bash
claw intake run "- scan the network for new hosts
- check docker container health
- review git commit history for the last week"
```

```
                     Request Intake
┌───┬──────────────────────────────────────────┬──────────┬───────────────┬─────────┬───────┐
│ # │ Requirement                              │ Role     │ Skill         │ Status  │ Error │
├───┼──────────────────────────────────────────┼──────────┼───────────────┼─────────┼───────┤
│ 1 │ scan the network for new hosts           │ verifier │ network-scan  │ planned │       │
│ 2 │ check docker container health            │ verifier │ docker-health │ planned │       │
│ 3 │ review git commit history for the last …  │ planner  │ git-stats     │ planned │       │
└───┴──────────────────────────────────────────┴──────────┴───────────────┴─────────┴───────┘
```

### Execute mode

Add `--execute` to run all mapped skills immediately:

```bash
claw intake run "scan the network for active hosts" --execute
```

Tasks run in parallel (up to `--max-workers` concurrent). The table shows final statuses (`ok` or `failed`) instead of `planned`.

### Role-filtered execution

Run only verifier-role tasks:

```bash
claw intake run "- plan the deployment strategy
- verify the backup integrity
- test the API endpoints" --execute --role verifier
```

Tasks assigned to `planner` or `executor` are skipped. Only the `verify` and `test` tasks execute.

### Suppress Telegram notifications

```bash
claw intake run "check disk usage" --no-notify-telegram
```

### Flush queued Telegram messages

After setting `TELEGRAM_DEFAULT_CHAT_ID` or messaging the bot:

```bash
claw intake flush-telegram
```

```
Flushed 3 queued Telegram updates to 123456789.
```

### Inspect the last session

```bash
claw intake show
```

Outputs the full JSON payload including timestamps, requirements, task statuses, role assignments, and reasons.

## Session Payload Format

The JSON saved to `current_request.json` has this structure:

```json
{
  "created_at": "2026-03-02T14:30:00+00:00",
  "execute": true,
  "role": "all",
  "requirements": [
    "scan the network for new hosts",
    "check docker container health"
  ],
  "tasks": [
    {
      "id": 1,
      "requirement": "scan the network for new hosts",
      "skill": "network-scan",
      "status": "ok",
      "output": "[network-scan] scanning 192.168.1.0/24 ...",
      "error": "",
      "assigned_role": "verifier"
    }
  ],
  "role_assignments": [
    {
      "task_id": 1,
      "role": "verifier",
      "reason": "matched: scan"
    }
  ]
}
```

## Skill Auto-Install

When the intake pipeline cannot find an existing skill for a requirement, `auto_install` handles creation automatically:

### Resolution order

1. **Existing skill match** -- Tokenizes the requirement and checks all registered skills for token overlap. If any skill's name or description shares at least one token, it is returned.

2. **Built-in template match** -- Matches requirement tokens against keyword maps for the 5 built-in templates:

   | Template | Keywords |
   |----------|----------|
   | `network-scan` | network, scan, nmap, ping, hosts, subnet, ip, discovery |
   | `disk-usage` | disk, usage, storage, space, volume, mount, df, full |
   | `git-stats` | git, repo, commit, contributor, stats, history, churn |
   | `docker-health` | docker, container, image, health, compose, status |
   | `log-search` | log, search, error, syslog, journal, grep, debug |

   If a template matches (score >= 1 keyword), the skill is scaffolded from the template with a working script.

3. **Generic scaffold** -- If no template matches, a generic bash skill is created with a kebab-case name derived from the first 40 characters of the requirement.

## Troubleshooting

### No skill mapped for a requirement

The `auto_install` module requires at least one keyword token overlap. If the requirement uses unusual phrasing, the system may scaffold a generic skill that does nothing useful. Check the `skills/` directory for the generated skill and edit its `run.sh` as needed.

### Telegram notifications not sending

Common causes:

- **Missing token**: Set `TELEGRAM_BOT_TOKEN` in `.env`.
- **Missing chat ID**: Set `TELEGRAM_DEFAULT_CHAT_ID` in `.env`, or send any message to the bot first so auto-discovery can find the chat.
- **Messages queued**: Run `claw intake flush-telegram` after the chat ID is available.
- **Network issues**: The bot API call retries up to 3 times with exponential backoff (1s, 2s, 4s). Check connectivity to `api.telegram.org`.

### Session file missing or stale

`claw intake show` reads `~/.claude-superpowers/runtime/current_request.json`. If the file is missing, run `claw intake run` first. If it shows old data, the last run may have failed before the save phase -- check `~/.claude-superpowers/audit.log` for telemetry events.

### Role filter skipping all tasks

When `--role` is set, tasks whose auto-assigned role does not match are skipped. Use `--role all` (the default) to run everything. Check role assignments in `claw intake show` output to understand why tasks were assigned specific roles.

### Execution failures

When `--execute` is used and any task fails, `claw intake run` exits with code 1. Check the `error` column in the output table. Common causes:

- **Skill dependency missing**: The skill's `dependencies` list includes a binary not on `PATH`.
- **Sandboxing**: Skills run via `run_sandboxed()` with a minimal environment (`PATH`, `HOME`, `LANG`, `TERM` only). Add `vault` to the skill's `permissions` list if it needs full environment access.
- **Timeout**: Skills have a 5-minute execution timeout. Long-running tasks may need to be restructured.
