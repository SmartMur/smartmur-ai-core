# MCP Server — Claude Code Integration

The MCP server exposes all claw superpowers as native Claude Code tools. Once configured, Claude Code can directly call messaging, SSH, browser, workflow, cron, skill, memory, vault, and audit functions — no shell commands needed.

## Setup

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "claw": {
      "command": "claw-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

Or if not installed as a package, use the Python path directly:

```json
{
  "mcpServers": {
    "claw": {
      "command": "/path/to/claude-superpowers/.venv/bin/python",
      "args": ["-m", "superpowers.mcp_server"],
      "env": {}
    }
  }
}
```

## Available Tools (43 total)

### Messaging (5 tools)
- `send_message(channel, target, message)` — Send via Slack/Telegram/Discord/Email
- `test_channel(channel)` — Verify channel credentials
- `list_channels()` — Show configured channels
- `send_notification(profile, message)` — Fan-out via notification profile
- `list_profiles()` — List notification profiles

### SSH (7 tools)
- `ssh_run(target, command)` — Run commands on hosts/groups
- `ssh_list_hosts()` — List registered hosts
- `ssh_list_groups()` — List host groups
- `ssh_health_check()` — Check all hosts (ping, SSH, load)
- `ha_get_state(entity_id)` — Home Assistant entity state
- `ha_call_service(domain, service, entity_id)` — HA service call
- `ha_list_entities(filter_prefix)` — List HA entities

### Memory (6 tools)
- `remember(key, value, category, tags, project)` — Store a memory
- `recall(key, category, project)` — Retrieve by key
- `search_memory(query, category, project, limit)` — Search memories
- `forget(key, category)` — Delete a memory
- `list_memories(category, project, limit)` — List all memories
- `memory_stats()` — Memory store statistics

### Browser (7 tools)
- `browse_page(url, profile)` — Navigate and get page content
- `browse_screenshot(url, selector, profile)` — Take screenshot
- `browse_extract(url, selector)` — Extract text from CSS selector
- `browse_extract_table(url, selector)` — Extract HTML table
- `browse_run_js(url, script)` — Execute JavaScript
- `browse_fill_and_submit(url, fields, submit_selector)` — Fill form
- `list_browser_profiles()` — List browser profiles

### Workflows (4 tools)
- `run_workflow(name, dry_run)` — Execute a YAML workflow
- `list_workflows()` — List available workflows
- `show_workflow(name)` — Show workflow steps
- `validate_workflow(name)` — Validate workflow config

### Cron (6 tools)
- `cron_add_job(name, schedule, job_type, command, output_channel)` — Add job
- `cron_remove_job(job_id)` — Remove job
- `cron_list_jobs()` — List all jobs
- `cron_enable_job(job_id)` — Enable job
- `cron_disable_job(job_id)` — Disable job
- `cron_job_logs(job_id, limit)` — View job output logs

### Skills (3 tools)
- `run_skill(name, args)` — Execute a skill
- `list_skills()` — List installed skills
- `skill_info(name)` — Show skill details

### Audit (2 tools)
- `audit_tail(limit)` — View recent audit entries
- `audit_search(query, limit)` — Search audit log

### Vault (2 tools)
- `vault_list_keys()` — List key names (no values)
- `vault_status()` — Check vault health

## Architecture

```
Claude Code → MCP Protocol (stdio) → FastMCP Server → claw modules
```

Each tool lazily instantiates its dependencies (Settings, registries, engines) inside the tool function body. No imports happen at registration time, so the server starts fast and only loads what's needed.

## Running standalone

```bash
# Via entry point
claw-mcp

# Via Python module
python -m superpowers.mcp_server
```

The server communicates over stdio using the MCP protocol. It's not meant to be run directly — Claude Code manages its lifecycle.
