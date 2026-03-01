# Claw Web Dashboard

Browser-based UI for all claude-superpowers subsystems at `http://localhost:8200`.

## Quick Start

```bash
# Local dev
claw dashboard
# → http://127.0.0.1:8200

# With auto-reload
claw dashboard --reload

# Custom host/port
claw dashboard --host 0.0.0.0 --port 9000

# Docker
docker compose up dashboard
# → http://localhost:8200
```

## Architecture

- **Frontend**: Alpine.js + htmx (CDN, no build step, ~30kb)
- **Backend**: FastAPI with 11 API routers (44 endpoints)
- **Routing**: SPA hash routing (`#/cron`, `#/ssh`, etc.)
- **Theme**: Dark theme with CSS custom properties, responsive grid
- **Dependencies**: Lazy-singleton pattern via `deps.py` — same engines as CLI/MCP

## Directory Structure

```
dashboard/
  __init__.py
  app.py              # FastAPI: mounts routers + static files
  deps.py             # Lazy-singleton engine factories
  models.py           # Pydantic v2 request/response models
  routers/
    __init__.py
    status.py          # GET /api/status (aggregate health)
    cron.py            # /api/cron/* (CRUD + logs + run)
    messaging.py       # /api/msg/* (send, test, channels, profiles)
    ssh.py             # /api/ssh/* (hosts, run, health)
    workflows.py       # /api/workflows/* (list, show, run, validate)
    memory.py          # /api/memory/* (CRUD + search + stats)
    skills.py          # /api/skills/* (list, info, run)
    audit.py           # /api/audit/* (tail, search)
    vault.py           # /api/vault/* (keys, status — no secrets)
    watchers.py        # /api/watchers/* (list rules)
    browser.py         # /api/browser/* (list profiles)
  static/
    index.html         # SPA shell with sidebar nav
    app.js             # Alpine.js page components + API helpers
    app.css            # Dark theme
    favicon.svg
  Dockerfile
```

## REST API Endpoints (44 total)

| Router | Endpoints |
|--------|-----------|
| **status** | `GET /api/status` |
| **cron** | `GET /api/cron/jobs`, `GET /api/cron/jobs/{id}`, `POST /api/cron/jobs`, `DELETE /api/cron/jobs/{id}`, `POST /api/cron/jobs/{id}/enable`, `POST /api/cron/jobs/{id}/disable`, `POST /api/cron/jobs/{id}/run`, `GET /api/cron/jobs/{id}/logs` |
| **messaging** | `GET /api/msg/channels`, `POST /api/msg/send`, `POST /api/msg/test/{channel}`, `GET /api/msg/profiles`, `POST /api/msg/profiles/{name}/send` |
| **ssh** | `GET /api/ssh/hosts`, `GET /api/ssh/groups`, `POST /api/ssh/run`, `GET /api/ssh/health` |
| **workflows** | `GET /api/workflows`, `GET /api/workflows/{name}`, `POST /api/workflows/{name}/validate`, `POST /api/workflows/{name}/run` |
| **memory** | `GET /api/memory`, `GET /api/memory/stats`, `GET /api/memory/search`, `POST /api/memory`, `GET /api/memory/{key}`, `DELETE /api/memory/{key}`, `POST /api/memory/decay` |
| **skills** | `GET /api/skills`, `GET /api/skills/{name}`, `POST /api/skills/{name}/run` |
| **audit** | `GET /api/audit/tail`, `GET /api/audit/search` |
| **vault** | `GET /api/vault/keys`, `GET /api/vault/status` |
| **watchers** | `GET /api/watchers/rules`, `GET /api/watchers/rules/{name}` |
| **browser** | `GET /api/browser/profiles` |

## Dashboard Pages

| Page | Route | Features |
|------|-------|----------|
| Home | `#/home` | Status cards for all 10 subsystems, click-to-navigate |
| Cron | `#/cron` | Job table, add/enable/disable/delete/run jobs, view logs |
| Messaging | `#/msg` | Channel status, send messages, test channels, profiles |
| SSH | `#/ssh` | Host list, run commands, health check with ping/SSH probes |
| Workflows | `#/workflows` | List, inspect steps, validate, dry run, live run |
| Memory | `#/memory` | Search, add/delete entries, category stats |
| Skills | `#/skills` | List, info detail, run skills |
| Audit | `#/audit` | Tail log, search entries |
| Vault | `#/vault` | Init status, key names (no secrets exposed) |
| Watchers | `#/watchers` | Rule list with paths, events, actions |
| Browser | `#/browser` | Profile list |

## Docker

The dashboard is added to `docker-compose.yaml`:

```yaml
dashboard:
  build:
    context: .
    dockerfile: dashboard/Dockerfile
  ports:
    - "8200:8200"
  env_file:
    - .env
  volumes:
    - ${HOME}/.claude-superpowers:/root/.claude-superpowers:ro
  restart: unless-stopped
```

The volume mount is read-only so the dashboard can read jobs, memory DB, audit logs, etc.

## Testing

57 tests in `tests/test_dashboard.py` covering all API endpoints:

```bash
PYTHONPATH=. pytest tests/test_dashboard.py -v
```

Tests use dependency injection override (setting `deps._*` singletons to fakes) — no real engines or files needed.

## Security Notes

- Vault endpoint exposes key **names** only, never secret values
- No authentication built-in — bind to localhost or use a reverse proxy
- All destructive operations (delete job, forget memory, run workflow) require explicit POST/DELETE
