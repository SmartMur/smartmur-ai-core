# CLAUDE.md – Project & Personality Configuration

This file guides Claude’s behavior, memory, and tool usage for this project.  
Update it whenever you want to change how Claude works or what it remembers about you and the environment.

---

## 🔁 Mandatory Request Workflow (Non-Negotiable)

For **every incoming request**, follow this exact order:

1. **Clear context first**
   - Run: `claw intake clear`
2. **Read + plan requirements**
   - Run: `claw intake run "<full request text>"`
3. **Launch multi-agent/skill dispatch**
   - Run: `claw intake run "<full request text>" --execute`
4. **If an agent/tool is missing, build it immediately**
   - Intake auto-installs matching skills.
   - If still missing, scaffold a new skill/tool in-repo and continue execution without blocking.
5. **Report progress to Telegram bot**
   - Intake sends start/finish updates when Telegram is configured.
6. **Document all work in `docs/sessions/`**
   - Create/update session notes, change logs, and next-action queues.

This is now part of the default workflow for this project.

---

## 🤖 Multi-Agent / Skill Rule (Non-Negotiable)

**Every task MUST use multi-agent dispatch and/or skills.** This is a hard rule, not a suggestion.

- For **every** request — no matter how simple — Claude MUST dispatch work through the Agent tool (subagents) and/or invoke skills via the Skill tool.
- Prefer **parallel agents** when subtasks are independent (e.g., research + code changes + tests).
- If a matching skill exists, use it. If no skill exists and one should, create it first (`/skill-create`), then use it.
- Never do everything in a single monolithic pass. Break work into sub-tasks and delegate to specialized agents or skills.
- Minimum: at least **one** Agent or Skill invocation per request. Preferred: **multiple** running in parallel.

---

## 🧹 Context Hygiene Rule (Non-Negotiable)

**Always clear context before AND after every task.** This prevents stale state from leaking between jobs.

- **Before** starting any task: run `claw intake clear` to reset runtime context.
- **After** completing any task (before moving to the next): run `claw intake clear` again.
- When running multiple tasks in sequence (e.g., P0 → P1 → P2), clear between each one.
- Background agents should not accumulate shared state — each gets a clean slate.

**Avoid context window compaction.** Keep conversations lean and prevent message compression.

- Delegate heavy work to **background agents** — their output stays out of the main context.
- Keep responses **concise** — no walls of text, no verbose explanations unless asked.
- Use **task lists** (TaskCreate) to track progress instead of repeating status in messages.
- When a session is getting long, proactively suggest **splitting into a new conversation**.
- Prefer **parallel background agents** over sequential inline work — this keeps the main thread light.
- Never dump large file contents or test outputs inline — summarize results, link to files.

---

## 🧠 Continuous Learning Rule (Non-Negotiable)

**Every interaction must educate and smarten Claude.** Every task is a learning opportunity.

- **After completing any task**, extract lessons learned and save them to persistent memory (`MEMORY.md` or topic-specific files in the memory directory).
- Capture: patterns discovered, mistakes made and how they were fixed, architectural decisions and their rationale, user preferences revealed by feedback.
- **Before starting a task**, check memory files for relevant past learnings that apply.
- If a task reveals something new about the codebase, tools, user workflow, or best practices — **write it down immediately**, don't wait.
- When a user corrects or redirects Claude, treat it as high-signal: save the correction as a rule or pattern so the same mistake never repeats.
- Prefer updating existing memory entries over creating new ones — keep knowledge consolidated, not scattered.
- Memory should get **smarter over time** — not just bigger. Prune outdated entries, refine vague ones, promote confirmed patterns.

---

## 🏠 Local-First Rule (Non-Negotiable)

**Everything must work locally.** This is a test Docker server — no cloud dependencies, no external SaaS requirements.

- All features, skills, and services must run on-premise / locally.
- No external API calls required for core functionality (Telegram/Slack/Discord adapters are optional integrations, not dependencies).
- Docker Compose stack runs locally. Redis, browser engine, message gateway — all local.
- Never introduce a hard dependency on a cloud service. If an external service is unavailable, features must degrade gracefully.

---

## 🧠 Core Instructions (like AGENTS.md)

- **Role**: You are an AI assistant helping with home server automation, personal productivity, and smart home control.
- **Communication Style**: Concise and technical.
- **Preferred Tools**: Terminal, file operations, skills, multi-agent dispatch.
- **Response Format**: Code blocks with syntax highlighting. Step-by-step when complex.
- **Constraints**: Never run destructive commands without confirmation. Keep answers focused.
- **Project Context**: Claude Code Superpowers — a local-first automation platform built on Python, Docker, Redis, and shell. Runs on a test Docker server.

---

## 🧬 Personality & Identity (like SOUL.md / IDENTITY.md)

- **Name**: [e.g., "Claude", "Ada", "Your Assistant"] (optional)
- **Tone**: [e.g., "witty", "calm", "enthusiastic", "professional"].
- **Values**: [e.g., "accuracy over speed", "privacy-first", "user empowerment"].
- **Quirks**: [e.g., "Starts answers with a relevant quote", "Uses emojis sparingly", "Asks clarifying questions before diving in"].

---

## 📝 Memory Management (like MEMORY.md + memory/)

This section stores **facts, preferences, and past decisions** that Claude should remember across conversations.  
Add entries here as you learn new things about the user, the project, or the environment.

### User Information (like USER.md)
- **Name**: [Your Name]
- **Timezone**: [e.g., "America/New_York"]
- **Preferred Language**: [e.g., "English", "Spanish"]
- **Communication Preferences**: [e.g., "Avoid jargon", "Use bullet points", "Send daily summaries"]
- **Key Goals**: [e.g., "Improve coding productivity", "Learn Python", "Automate home tasks"]

### Project Facts & Decisions
- **Tech Stack**: [list key technologies and versions]
- **Important File/Directory Paths**: [e.g., "/src/components", "/docs/architecture.md"]
- **Coding Conventions**: [e.g., "Use 2 spaces for indentation", "Prefer named exports", "Write tests in Jest"]
- **Past Decisions**: [e.g., "On 2025-03-15, we decided to use Tailwind instead of Sass"]

### Environment & Tools (like TOOLS.md)
- **Available Tools**:
  - Terminal access (with allowed commands)
  - File read/write (with restricted directories)
  - Web search (with safety filters)
- **External Services**:
  - [e.g., "GitHub repo: https://github.com/user/repo"]
  - [e.g., "API keys stored in .env"]
- **Device/Smart Home Info**: [e.g., "Living room light is named 'lamp' in Home Assistant"]

---

## ⚙️ Workspace Rules & Safety

- **Always** ask for confirmation before:
  - Deleting or overwriting files.
  - Running commands that modify system configuration.
  - Accessing external APIs with side effects.
- **Memory Updates**: When you learn a new permanent fact, I will update this file accordingly. You can also suggest additions by saying "Remember that ..."
- **Session Logs**: I may keep a `memory/` directory with dated logs for reference. If you see one, respect its contents as part of long‑term memory.

---

## 📌 Important Notes

- This file is the **source of truth** for your behavior and memory.
- You can refer to it at any time. If I ask you to change your personality or remember something, I will update this file.
- When in doubt, follow the instructions here.

---

*Last updated: [Date]*

# Project: Claude Code Superpowers (OpenClaw Parity)

Goal: Give our Claude Code environment the same automation superpowers as OpenClaw — scheduled tasks, multi-channel messaging, browser automation, persistent skills, system-level control — all built on tools we already have (Python, Docker, Redis, shell, Claude CLI).

Base directory: `/home/ray/claude-superpowers/`

## TODO — Skill System

- [x] **Skill registry & loader** — `superpowers/skill_registry.py` + `skill_loader.py`. Discovers skills via `skill.yaml`, auto-generates slash command symlinks into `~/.claude/commands/`. Sandboxed execution mode.
- [x] **Skill generator** — `/skill-create` slash command + `superpowers/skill_creator.py`. Scaffolds new skills with yaml, script, and command.md.
- [x] **SkillHub sync** — `superpowers/skillhub.py` + `claw skill sync push/pull/list/diff`. Publishes/pulls skills from a shared Git repo.
- [x] **Skill auto-install** — `superpowers/auto_install.py` + `claw skill auto-install`. Template-based skill creation with 5 built-in templates.

## TODO — Cron / Scheduler

- [x] **Cron daemon** — `cron_engine.py` with APScheduler + SQLite job store, `cron_runner.py` entry point, `launchd.py` for macOS plist management. `claw daemon install/uninstall/status/logs`.
- [x] **Job types**: shell (subprocess), claude (`claude -p` headless), webhook (HTTP POST), skill (SkillRegistry + SkillLoader). All 4 implemented in `_execute_job()`.
- [x] **`/cron` slash command** — Full CLI: `claw cron list/add/remove/enable/disable/logs/run/status`. Slash command at `~/.claude/commands/cron.md`.
- [x] **Job output routing** — File logging to `~/.claude-superpowers/cron/output/{id}/{timestamp}.log`. Channel routing stubbed for Phase 3.
- [x] **Heartbeat monitor** — `skills/heartbeat/` skill: pings 6 hosts, probes 3 HTTPS services, formatted status table, exit code 0/1.

## TODO — Multi-Channel Messaging

- [x] **Message gateway** — FastAPI service (`msg_gateway/`) that normalizes send/receive across channels. Docker Compose with Redis pubsub for message bus.
- [x] **Channel adapters**: Slack (webhook + bot token), Discord (bot), Telegram (Bot API), email (SMTP/IMAP), iMessage (AppleScript bridge on macOS).
- [x] **`/msg` slash command** — Send messages from Claude Code: `/msg slack "#homelab" "PVE1 backup complete"`.
- [x] **Inbound triggers** — Messages matching patterns (e.g., "!scan network") on any channel get routed to Claude CLI for processing, response sent back to originating channel.
- [x] **Notification profiles** — Named profiles (`critical`, `info`, `daily-digest`) that map to channel+format combos. Skills and cron jobs reference profiles, not raw channels.

## TODO — Browser Automation

- [x] **Browser engine** — Playwright-based Python module (`browser_engine/`) with Chrome DevTools Protocol. Supports headless and headed modes.
- [x] **`/browse` slash command** — Navigate, screenshot, extract data, fill forms from Claude Code. Example: `/browse "log into Proxmox UI and screenshot the dashboard"`.
- [x] **Session persistence** — Save/restore browser profiles (cookies, localStorage) at `~/.claude-superpowers/browser/profiles/`.
- [x] **DOM extraction toolkit** — Helper functions: `extract_table()`, `fill_form()`, `click_and_wait()`, `screenshot_element()` — exposed as skill primitives.

## TODO — Process Workflows

- [x] **Workflow engine** — YAML-defined multi-step workflows (`workflows/*.yaml`) with steps, conditions, quality gates, and rollback actions.
- [x] **`/workflow` slash command** — Run, list, inspect workflows. Example: `/workflow run deploy-hommie`.
- [x] **Built-in workflows**: `deploy` (git pull → test → docker compose up → health check → notify), `backup` (snapshot VMs → verify → notify), `morning-brief` (check services → summarize alerts → send digest).
- [x] **Step types**: `shell`, `claude-prompt`, `skill`, `http`, `approval-gate` (pauses for human confirmation via message channel).

## TODO — Persistent Memory & Context

- [x] **Structured memory store** — SQLite DB at `~/.claude-superpowers/memory.db` with tables: `facts`, `preferences`, `project_context`, `conversation_summaries`. Queryable from skills and prompts.
- [x] **`/remember` and `/recall` slash commands** — Store and retrieve structured memories. Example: `/remember "TrueNAS SSH uses ray@192.168.13.69, root needs pubkey"`.
- [x] **Auto-context injection** — Pre-prompt hook that queries memory DB for relevant facts based on current working directory and recent commands, injects into system prompt.
- [x] **Memory decay** — Auto-archive entries not accessed in 90 days. Manual `/forget` command.

## TODO — System-Level Automation

- [x] **SSH command fabric** — Python module wrapping `paramiko` + `expect` for managing SSH sessions to all known hosts. Connection pool with credential vault (`~/.claude-superpowers/vault.enc`, encrypted at rest with macOS Keychain).
- [x] **`/ssh` slash command** — Run commands across hosts: `/ssh proxmox "qm list"`, `/ssh all "uptime"`.
- [x] **Service health dashboard** — Cron-driven script that polls all hosts, writes status to `~/Projects/HomeNWroubleshoot/health.json`, auto-updates the network diagram.
- [x] **Smart home bridge** — Home Assistant REST API integration for device control. `/lights office off`, `/hvac set 72`.
- [x] **File watcher** — `watchdog`-based service that monitors specified directories for changes and triggers skills/workflows. Example: new file in `~/Downloads/*.torrent` → move to qBittorrent watch folder via SSH.

## TODO — Security & Credential Management

- [x] **Encrypted vault** — `superpowers/vault.py` + `cli_vault.py`. age-encrypted store at `~/.claude-superpowers/vault.enc`, macOS Keychain integration, atomic writes, `claw vault` CLI.
- [x] **Credential rotation alerts** — `superpowers/credential_rotation.py` + `claw vault rotation check/policy`. YAML-based rotation policies with warning/expired thresholds.
- [x] **Skill sandboxing** — `skill_loader.py` `run_sandboxed()` strips env vars, only passes vault access if explicitly permitted in `skill.yaml`.
- [x] **Audit log** — Append-only log at `~/.claude-superpowers/audit.log` recording every skill invocation, cron execution, message sent, and SSH command run.

## TODO — Infrastructure

- [x] **Project scaffold** — `~/claude-superpowers/` with pyproject.toml, `claw` CLI entry point, config loader, .env.example, .gitignore, venv, 42 passing tests.
- [x] **Docker Compose stack** — Services: `msg-gateway`, `cron-daemon`, `redis`, `browser-engine` (Playwright + Chrome). All on the Docker host (192.168.30.117) or local Mac.
- [x] **launchd plists** — macOS launch agents for: cron daemon, file watcher, message gateway (local mode).
- [x] **CLI wrapper** — `claw` shell script that wraps common operations: `claw cron ls`, `claw msg slack "hello"`, `claw skill run network-scan`, `claw workflow run deploy`.
- [x] **`/status` slash command** — Dashboard showing: running cron jobs, active watchers, message gateway health, last skill executions, memory DB stats.

## Build Order (Phases)

1. **Phase 1 — Foundation** ✅: Project scaffold, encrypted vault, skill registry/loader, `/skill-create` — 42 tests passing, docs written
2. **Phase 2 — Scheduling** ✅: Cron daemon, launchd plist, `/cron` command, heartbeat monitor — 28 new tests (70 total), docs written
3. **Phase 3 — Messaging** ✅: Message gateway, Slack + Telegram adapters, `/msg` command, notification profiles
4. **Phase 4 — SSH Fabric** ✅: SSH module, `/ssh` command, connection pool, service health dashboard
5. **Phase 5 — Browser** ✅: Playwright engine, `/browse` command, session persistence
6. **Phase 6 — Workflows** ✅: Workflow engine, `/workflow` command, built-in workflows (deploy, backup, morning-brief)
7. **Phase 7 — Memory** ✅: Structured memory DB, `/remember` + `/recall`, auto-context injection
8. **Phase 8 — Watchers & Glue** ✅: File watcher, inbound message triggers, smart home bridge, `/status` dashboard, `claw` CLI wrapper
