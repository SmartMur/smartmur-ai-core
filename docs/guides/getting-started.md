# Getting Started

## Prerequisites

- **Python 3.12+** (3.12 or 3.13 recommended)
- **Debian/Ubuntu package manager** (`apt`)
- **age** encryption tool

Install age:

```bash
sudo apt update
sudo apt install -y age
```

On macOS you can still use:

```bash
brew install age
```

Verify:

```bash
age --version
age-keygen --version
```

## Installation

Clone the repo and install in editable mode:

```bash
cd /path/to/claude-superpowers
pip install -e ".[dev]"
```

Verify the CLI:

```bash
claw --version
# claude-superpowers 0.1.0
```

## Initialize the Vault

Set up encrypted credential storage:

```bash
claw vault init
```

Store some credentials:

```bash
claw vault set ANTHROPIC_API_KEY sk-ant-your-key-here
claw vault set GITHUB_TOKEN ghp_xxxxxxxxxxxx
```

Verify they are stored:

```bash
claw vault list
claw vault get ANTHROPIC_API_KEY
```

## Create Your First Skill

Use the interactive scaffolder:

```bash
claw skill create
```

Follow the prompts:

```
Skill name (kebab-case): hello-world
Description: Print a greeting
Script type (bash, python) [bash]: bash
```

This creates `skills/hello-world/` with a ready-to-edit script. Open the generated file and add your logic:

```bash
$EDITOR skills/hello-world/run.sh
```

Run it:

```bash
claw skill run hello-world
```

Or use it as a Claude Code slash command -- type `/hello-world` in your Claude Code session.

## One-Shot Skill Creation

Skip the prompts with flags:

```bash
claw skill create \
  --name check-ports \
  --description "Check if common ports are open on a target" \
  --type bash
```

## Explore Existing Skills

```bash
# List all skills
claw skill list

# Get details on a skill
claw skill info network-scan

# Validate a skill directory
claw skill validate skills/network-scan

# Re-sync all slash commands
claw skill sync
```

## Available Slash Commands

After running `claw skill sync`, any skill with `slash_command: true` in its manifest is available as a Claude Code slash command. Type `/` followed by the skill name:

- `/network-scan` -- Scan all home network subnets
- `/hello-world` -- (your custom skill)
- Any other skill you create with `slash_command: true`

## Project Structure at a Glance

```
claw vault init/set/get/list/delete   # Encrypted credential management
claw skill list/info/run/sync/create  # Skill lifecycle
claw skill validate <path>            # Manifest validation
claw status                           # System health check
```

## Next Steps

All 8 core phases are complete. Explore additional subsystems:

| Subsystem | Command | Documentation |
|-----------|---------|---------------|
| Cron scheduling | `claw cron list` | [docs/reference/cron.md](../reference/cron.md) |
| Multi-channel messaging | `claw msg channels` | [docs/reference/messaging.md](../reference/messaging.md) |
| SSH remote execution | `claw ssh hosts` | [docs/reference/ssh.md](../reference/ssh.md) |
| Browser automation | `claw browse open <url>` | [docs/reference/browser.md](../reference/browser.md) |
| Workflow orchestration | `claw workflow list` | [docs/reference/workflows.md](../reference/workflows.md) |
| Persistent memory | `claw memory list` | [docs/reference/memory.md](../reference/memory.md) |
| File watchers | `claw watcher list` | [docs/reference/watchers.md](../reference/watchers.md) |
| Web dashboard | `claw dashboard` | [docs/reference/dashboard.md](../reference/dashboard.md) |
| MCP server | Configure in Claude Code settings | [docs/reference/mcp-server.md](../reference/mcp-server.md) |

## Troubleshooting

### `age: command not found`

Install age on Debian/Ubuntu: `sudo apt install -y age` (or `brew install age` on macOS).

### `Identity file not found ... Run claw vault init`

Run `claw vault init` to generate the age keypair.

### `Skill not found: <name>`

Make sure the skill directory exists under `skills/` and contains a valid `skill.yaml`. Run `claw skill validate skills/<name>` to check.

### Slash command not appearing in Claude Code

Run `claw skill sync` to regenerate symlinks. Verify the symlink exists:

```bash
ls -la ~/.claude/commands/
```
