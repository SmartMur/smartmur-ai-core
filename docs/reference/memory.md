# Persistent Memory

Phase 7 of Claude Superpowers. A SQLite-backed key/value memory store with categories, search, decay, and auto-context injection.

## Quick Start

```bash
# Store a memory
claw memory remember "truenas-ssh" "ray@192.168.13.69, root needs pubkey"

# Recall it
claw memory recall "truenas-ssh"

# Search across all memories
claw memory search "ssh"

# List everything
claw memory list

# Scoped to a project
claw memory remember "db-host" "timescale.local:5432" --project hommie

# Delete a memory
claw memory forget "truenas-ssh"

# View stats
claw memory stats

# Clean up stale entries (not accessed in 90 days)
claw memory decay --days 90

# Preview auto-context injection
claw memory context --project hommie
```

## Categories

| Category | Purpose |
|---|---|
| `fact` | General knowledge, IPs, credentials hints, host info |
| `preference` | User preferences (tooling, style, workflow) |
| `project_context` | Project-specific facts (DB schemas, deploy targets) |
| `conversation_summary` | Summaries of past conversations |

## Slash Commands

- `/remember "key" "value"` — store a memory
- `/recall "key"` — retrieve a memory

## Auto-Context Injection

The `ContextBuilder` class queries the memory store for relevant entries and formats them as a markdown snippet for system prompt injection.

```python
from superpowers.memory import MemoryStore, ContextBuilder

store = MemoryStore()
builder = ContextBuilder(store)
context = builder.inject_hook(project="hommie")
# Returns formatted markdown with relevant memories
```

## Storage

- Database: `~/.claude-superpowers/memory.db` (SQLite with WAL mode)
- Schema: `memories` table with UNIQUE constraint on (category, key, project)
- Upsert: Calling `remember` with an existing key updates the value and increments access count

## Decay

Entries not accessed in N days (default 90) can be cleaned up:

```bash
claw memory decay --days 90
```

## Architecture

- `superpowers/memory/base.py` — data types (MemoryCategory, MemoryEntry, MemoryStoreError)
- `superpowers/memory/store.py` — MemoryStore (SQLite CRUD)
- `superpowers/memory/context.py` — ContextBuilder (auto-context injection)
- `superpowers/cli_memory.py` — Click CLI group
