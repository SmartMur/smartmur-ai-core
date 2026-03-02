# Skill System

## What Is a Skill?

A skill is a self-contained unit of automation that Claude Code can discover and execute. Each skill lives in its own directory under `skills/`, contains a manifest (`skill.yaml`), an executable script, and optionally a `command.md` that registers it as a Claude Code slash command.

Skills can be anything: network scanners, deployment scripts, data pipelines, code generators, or system health checks. The skill system handles discovery, validation, dependency checking, execution, and slash command registration.

## Skill Directory Structure

```
skills/
└── my-skill/
    ├── skill.yaml      # Manifest (required)
    ├── run.sh          # Entry point script (required, or run.py)
    └── command.md      # Slash command definition (auto-generated)
```

The `_template/` directory provides a copy-paste starting point:

```
skills/_template/
├── skill.yaml
├── run.sh
└── command.md
```

## skill.yaml Manifest Format

Every skill must have a `skill.yaml` in its root directory. Here is the full schema with all fields:

```yaml
# Required fields
name: my-skill              # Unique kebab-case identifier
version: "0.1.0"            # Semver version string
description: "What this skill does"  # Human-readable summary
author: DreDay              # Author name
script: run.sh              # Entry point relative to skill directory

# Optional fields
slash_command: true          # Register as Claude Code slash command (default: false)
triggers: []                 # Event triggers for cron integration (e.g., ["cron:daily"])
dependencies: []             # Required binaries that must be on PATH (e.g., [nmap, jq])
permissions: []              # Permission scopes (e.g., [ssh, vault, nmap])
```

### Field Reference

| Field           | Required | Type       | Description |
|-----------------|----------|------------|-------------|
| `name`          | Yes      | string     | Kebab-case identifier, must be unique across all skills |
| `version`       | Yes      | string     | Semantic version of the skill |
| `description`   | Yes      | string     | One-line description shown in `claw skill list` |
| `author`        | Yes      | string     | Who wrote this skill |
| `script`        | Yes      | string     | Path to the entry point script, relative to skill dir |
| `slash_command`  | No       | boolean    | If `true`, `claw skill sync` creates a Claude Code slash command |
| `triggers`      | No       | list[str]  | Event triggers for cron integration (e.g., `cron:daily`) |
| `dependencies`  | No       | list[str]  | Binaries checked via `which` before execution |
| `permissions`   | No       | list[str]  | Scopes controlling environment access during sandboxed runs |

### Permissions

The `permissions` list controls what the skill can access when run in sandboxed mode (`run_sandboxed`):

- **`vault`** -- The skill receives the full environment, including vault-injected secrets. Without this permission, sandboxed execution strips the environment to `PATH`, `HOME`, `LANG`, and `TERM` only.
- **`ssh`** -- Declares that the skill needs SSH access (used for documentation and intent signaling).
- **`nmap`** -- Declares network scanning capability (used for documentation and intent signaling).

Custom permission strings are allowed. The system currently enforces `vault`; other permissions serve as declarations for future phases.

## Creating a Skill Manually

1. Create a directory under `skills/`:

```bash
mkdir -p skills/my-tool
```

2. Write `skill.yaml`:

```yaml
name: my-tool
version: "0.1.0"
description: "Does something useful"
author: DreDay
script: run.sh
slash_command: true
dependencies: [curl, jq]
permissions: []
triggers: []
```

3. Write the script (`run.sh` or `run.py`):

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[my-tool] running..."
curl -s https://httpbin.org/get | jq .origin
```

4. Make it executable:

```bash
chmod +x skills/my-tool/run.sh
```

5. Validate and sync:

```bash
claw skill validate skills/my-tool
claw skill sync
```

## Creating a Skill via `claw skill create`

The interactive scaffolder handles everything:

```bash
claw skill create
```

You will be prompted for:

- **Skill name** (auto-converted to kebab-case)
- **Description**
- **Script type** (bash or python)

You can also pass everything as flags:

```bash
claw skill create \
  --name deploy-api \
  --description "Deploy the API to production" \
  --type bash \
  --permission ssh \
  --permission vault \
  --trigger "cron:daily"
```

The creator generates:

- `skills/<name>/skill.yaml` -- Manifest
- `skills/<name>/run.sh` or `run.py` -- Stub script with boilerplate
- `skills/<name>/command.md` -- Slash command documentation

It also auto-runs `sync` to register any slash commands immediately.

### Generated Bash Template

```bash
#!/usr/bin/env bash
set -euo pipefail

# my-skill — Does something useful

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
    # Add your skill logic here
}

main "$@"
```

### Generated Python Template

```python
#!/usr/bin/env python3
"""my-skill — Does something useful"""
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

## How Slash Command Generation Works

When a skill has `slash_command: true`, `claw skill sync` does the following:

1. Generates a `.claude/commands/<name>.md` file inside the skill directory
2. Creates a **symlink** from `~/.claude/commands/<name>.md` pointing to that file
3. Claude Code discovers the symlink and registers `/<name>` as a slash command

```
skills/network-scan/.claude/commands/network-scan.md   (generated)
        ^
        |  symlink
~/.claude/commands/network-scan.md  ──────────────────┘
```

This means after running `claw skill sync`, typing `/network-scan` in Claude Code will invoke the skill.

Sync is idempotent -- existing symlinks are removed and recreated. Run it any time you add or modify skills.

## The Skill Loader and Sandboxing

The `SkillLoader` handles execution with two modes:

### Standard Execution (`loader.run()`)

- Verifies all `dependencies` are available on PATH
- Passes arguments as `SKILL_<KEY>` environment variables
- Runs in the skill's directory as cwd
- Inherits the full parent environment
- 5-minute timeout

### Sandboxed Execution (`loader.run_sandboxed()`)

- Same dependency check
- Runs with a **minimal environment**: only `PATH`, `HOME`, `LANG`, `TERM`
- If the skill has `vault` in its permissions, the full environment is passed instead
- Same 5-minute timeout

### Argument Passing

Arguments passed to `claw skill run` are converted to environment variables:

```bash
claw skill run my-skill target=192.168.1.0/24 verbose=true
```

Inside the script, these are available as:

```bash
echo $SKILL_TARGET      # 192.168.1.0/24
echo $SKILL_VERBOSE     # true
```

### Script Type Detection

The loader determines how to execute based on file extension:

| Extension | Command          |
|-----------|------------------|
| `.py`     | `python3 <script>` |
| `.sh`     | `bash <script>`    |
| other     | `./<script>` (direct execution) |

## CLI Reference

### `claw skill list`

Show all discovered skills in a table.

```
$ claw skill list
                    Skills
┌──────────────┬─────────┬────────────────────┬───────────┬─────────────┐
│ Name         │ Version │ Description        │ Slash Cmd │ Permissions │
├──────────────┼─────────┼────────────────────┼───────────┼─────────────┤
│ network-scan │ 0.1.0   │ Scan all home ...  │    yes    │ ssh, nmap   │
└──────────────┴─────────┴────────────────────┴───────────┴─────────────┘
```

Running `claw skill` with no subcommand is equivalent to `claw skill list`.

### `claw skill info <name>`

Show detailed information about a specific skill.

```
$ claw skill info network-scan
         Skill: network-scan
┌─────────────┬──────────────────────────────────────┐
│ Name        │ network-scan                         │
│ Version     │ 0.1.0                                │
│ Description │ Scan all home network subnets ...    │
│ Author      │ DreDay                               │
│ Script      │ /path/to/skills/network-scan/run.sh  │
│ Slash Cmd   │ yes                                  │
│ Triggers    │ -                                    │
│ Dependencies│ -                                    │
│ Permissions │ ssh, nmap                            │
└─────────────┴──────────────────────────────────────┘
```

### `claw skill run <name> [args...]`

Execute a skill. Arguments are passed as `key=value` pairs.

```bash
claw skill run network-scan subnet=192.168.1.0/24
```

### `claw skill sync`

Regenerate all slash command symlinks for skills with `slash_command: true`.

```bash
$ claw skill sync
Synced 2 slash command(s)
  ~/.claude/commands/network-scan.md -> .../skills/network-scan/.claude/commands/network-scan.md
  ~/.claude/commands/template-skill.md -> .../skills/_template/.claude/commands/template-skill.md
```

### `claw skill validate <path>`

Validate a skill directory against the manifest schema.

```bash
$ claw skill validate skills/my-skill
Skill is valid.

$ claw skill validate skills/broken-skill
Validation failed:
  - Missing required field: description
  - Script not found: run.sh
```

Checks performed:
- `skill.yaml` exists and is valid YAML
- All required fields present (`name`, `version`, `description`, `author`, `script`)
- Referenced script file exists

### `claw skill create`

Interactive skill scaffolder. See [Creating a Skill via claw skill create](#creating-a-skill-via-claw-skill-create) above.
