# CLI Command Reference

The `claw` CLI is the primary interface to Nexus Core. All commands are organized into groups by subsystem.

```bash
claw --version    # Show version
claw --help       # List all commands
```

---

## Skill Management

### `claw skill`

Manage and execute skills.

| Subcommand | Description |
|-----------|-------------|
| `claw skill list` | Show all skills with status |
| `claw skill info <name>` | Show skill details |
| `claw skill run <name>` | Execute a skill |
| `claw skill create` | Scaffold a new skill (interactive or with flags) |
| `claw skill validate <path>` | Validate a skill directory |
| `claw skill link` | Regenerate all slash command symlinks |
| `claw skill sync` | Sync skills with the SkillHub repo |
| `claw skill auto-install` | Auto-create a skill from a description or template |

---

## Scheduling

### `claw cron`

Manage scheduled jobs.

| Subcommand | Description |
|-----------|-------------|
| `claw cron list` | Show all scheduled jobs |
| `claw cron add` | Add a new scheduled job |
| `claw cron remove <id>` | Remove a scheduled job (supports partial ID match) |
| `claw cron enable <id>` | Enable a disabled job |
| `claw cron disable <id>` | Disable a job (keeps config, stops execution) |
| `claw cron logs <id>` | Show recent log output for a job |
| `claw cron run <id>` | Force-run a job immediately |
| `claw cron status` | Show scheduler status |

### `claw daemon`

Manage the cron daemon service.

| Subcommand | Description |
|-----------|-------------|
| `claw daemon install` | Install and start the daemon service |
| `claw daemon uninstall` | Stop and remove the daemon service |
| `claw daemon status` | Show daemon status (PID, running state) |
| `claw daemon logs` | Tail the daemon log file |

---

## Messaging

### `claw msg`

Send messages via Slack, Telegram, Discord, email.

| Subcommand | Description |
|-----------|-------------|
| `claw msg send <channel> <text>` | Send a message to a channel target |
| `claw msg notify <profile> <text>` | Send to all targets in a notification profile |
| `claw msg channels` | List available channels and credential status |
| `claw msg profiles` | List notification profiles |
| `claw msg test <channel>` | Test connection to a channel |

---

## SSH & Remote Execution

### `claw ssh`

Execute commands on remote hosts and manage smart home devices.

| Subcommand | Description |
|-----------|-------------|
| `claw ssh run <host> <command>` | Run a command on one or more hosts |
| `claw ssh hosts` | List configured SSH hosts |
| `claw ssh health` | Run health checks on all hosts (ping + SSH + uptime) |
| `claw ssh test <host>` | Test SSH connectivity |
| `claw ssh ha` | Home Assistant controls |

---

## Browser Automation

### `claw browse`

Browser automation with Playwright.

| Subcommand | Description |
|-----------|-------------|
| `claw browse open <url>` | Open a URL and print page info |
| `claw browse screenshot <url>` | Navigate to a URL and take a screenshot |
| `claw browse extract <url>` | Extract text content from a page |
| `claw browse table <url>` | Extract a table from a page |
| `claw browse js <url> <script>` | Navigate to a URL and evaluate JavaScript |
| `claw browse profiles` | Manage browser profiles |

---

## Workflows

### `claw workflow`

Run multi-step YAML workflows.

| Subcommand | Description |
|-----------|-------------|
| `claw workflow list` | List available workflows |
| `claw workflow run <name>` | Execute a workflow |
| `claw workflow show <name>` | Show workflow steps |
| `claw workflow validate <path>` | Validate a workflow definition |
| `claw workflow init` | Install built-in workflow templates |

### `claw dag`

DAG-based parallel task execution.

| Subcommand | Description |
|-----------|-------------|
| `claw dag run <workflow>` | Run a workflow as a dependency-aware DAG |
| `claw dag visualize <workflow>` | Show ASCII visualization of the DAG |

---

## Memory

### `claw memory`

Persistent memory store.

| Subcommand | Description |
|-----------|-------------|
| `claw memory remember <key> <value>` | Store a memory (upserts if key exists) |
| `claw memory recall <key>` | Retrieve a memory by key |
| `claw memory list` | List stored memories |
| `claw memory search <query>` | Search memories by key or value |
| `claw memory forget <key>` | Delete a memory |
| `claw memory context` | Show what auto-context would inject |
| `claw memory decay` | Delete stale memories not accessed in N days |
| `claw memory stats` | Show memory store statistics |

---

## Vault & Security

### `claw vault`

Manage encrypted secrets.

| Subcommand | Description |
|-----------|-------------|
| `claw vault init` | Initialize vault and generate age keypair |
| `claw vault set <key> <value>` | Store a credential |
| `claw vault get <key>` | Retrieve a credential |
| `claw vault list` | List all keys in the vault |
| `claw vault delete <key>` | Remove a credential |
| `claw vault rotation` | Credential rotation alerts |

### `claw audit`

View the audit log.

| Subcommand | Description |
|-----------|-------------|
| `claw audit tail` | Show recent audit log entries |
| `claw audit search <query>` | Search audit log entries |

### `claw policy`

Manage orchestration safety policies.

| Subcommand | Description |
|-----------|-------------|
| `claw policy list` | Show all active policies and rules |
| `claw policy check <command>` | Test a command against all policies |
| `claw policy check-file <path>` | Test a file path against file access policies |
| `claw policy test-output <text>` | Test text for secret leaks |

---

## Agent & Orchestration

### `claw agent`

Discover and run subagents.

| Subcommand | Description |
|-----------|-------------|
| `claw agent list` | Show all registered agents |
| `claw agent info <name>` | Show detailed agent information |
| `claw agent run <name>` | Run an agent, optionally with a task description |
| `claw agent recommend <task>` | Show ranked agent recommendations for a task |

### `claw orchestrate`

Run orchestration commands (security audit, health check, etc.).

| Subcommand | Description |
|-----------|-------------|
| `claw orchestrate list` | Show available orchestration commands |
| `claw orchestrate info <name>` | Show details about an orchestration command |
| `claw orchestrate run <name>` | Run an orchestration command |

### `claw intake`

Clear context, plan requirements, and dispatch skills.

| Subcommand | Description |
|-----------|-------------|
| `claw intake clear` | Clear runtime context |
| `claw intake run <request>` | Run intake pipeline: clear, plan, dispatch |
| `claw intake show` | Show current intake session JSON |
| `claw intake flush-telegram` | Flush queued Telegram updates |

---

## Packs & Templates

### `claw pack`

Manage skill/workflow/agent packs.

| Subcommand | Description |
|-----------|-------------|
| `claw pack list` | List all installed packs |
| `claw pack install <source>` | Install a pack from a local directory or git URL |
| `claw pack uninstall <name>` | Remove an installed pack |
| `claw pack update <name>` | Update a pack by re-fetching from source |
| `claw pack validate <path>` | Validate a pack directory structure |

### `claw template`

Manage shipped configuration templates.

| Subcommand | Description |
|-----------|-------------|
| `claw template list` | List all tracked templates and status |
| `claw template init` | Copy managed templates to config directory |
| `claw template diff` | Show differences between current and shipped templates |
| `claw template reset <name>` | Restore a template to shipped version |
| `claw template upgrade` | Upgrade all templates, preserving customizations |

---

## Jobs & Releases

### `claw jobs`

Git-branch job orchestration.

| Subcommand | Description |
|-----------|-------------|
| `claw jobs list` | List all job branches |
| `claw jobs run <command>` | Run a command on a dedicated job branch |

### `claw release`

Manage releases, changelogs, and migrations.

| Subcommand | Description |
|-----------|-------------|
| `claw release prepare <version>` | Prepare a release: validate, check git, build |
| `claw release tag <version>` | Create an annotated git tag |
| `claw release verify <version>` | Verify a release tag and version match |
| `claw release rollback <version>` | Rollback a release: delete local tag |
| `claw release changelog` | Show changelog since last tag |
| `claw release migrate <from> <to>` | Generate a migration guide between versions |

---

## Monitoring & Reports

### `claw status`

Show system status across all subsystems. No subcommands -- run `claw status` directly.

### `claw dashboard`

Launch the web dashboard.

```bash
claw dashboard              # Default: localhost:8200
claw dashboard --port 9000  # Custom port
claw dashboard --reload     # Dev mode with auto-reload
```

### `claw report`

View, list, and export saved reports.

| Subcommand | Description |
|-----------|-------------|
| `claw report list` | List saved reports (most recent first) |
| `claw report show <id>` | Display a report in the terminal |
| `claw report export <id>` | Export a report to JSON or Markdown |

### `claw benchmark`

Run and report on orchestration benchmarks.

| Subcommand | Description |
|-----------|-------------|
| `claw benchmark list` | List available benchmark scenarios |
| `claw benchmark run` | Run benchmarks and display results |
| `claw benchmark report` | Show the last benchmark results |

---

## Setup

### `claw setup`

First-run setup and configuration wizard.

| Subcommand | Description |
|-----------|-------------|
| `claw setup run` | Run the full setup wizard |
| `claw setup check` | Check prerequisites (Python, Docker, Redis, age) |
| `claw setup env` | Create .env file from .env.example |
| `claw setup vault` | Initialize the encrypted vault |
| `claw setup telegram` | Configure Telegram bot integration |

---

## File Watchers

### `claw watcher`

Manage file watchers.

| Subcommand | Description |
|-----------|-------------|
| `claw watcher list` | List configured watcher rules |
| `claw watcher start` | Start the watcher daemon (foreground) |
| `claw watcher test <rule>` | Simulate a file event to test a rule |
