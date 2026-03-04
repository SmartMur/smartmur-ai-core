# Template Manager

## Overview

The template manager tracks shipped configuration files (Docker Compose files, workflow YAMLs, `.env.example`) and detects when the user has modified them. During upgrades, it preserves user customizations by creating timestamped backups before overwriting with new shipped versions.

A JSON manifest at `~/.claude-superpowers/templates.json` records the SHA-256 hash of each shipped template and the hash at install time. Comparing the current file hash against the shipped hash reveals whether the user has made local changes.

## Managed Templates

The following files are tracked by default:

| Template | Source Path | Description |
|----------|-------------|-------------|
| `docker-compose.yaml` | `docker-compose.yaml` | Main Docker Compose stack |
| `docker-compose.prod.yaml` | `docker-compose.prod.yaml` | Production overlay |
| `workflows/deploy.yaml` | `workflows/deploy.yaml` | Deployment workflow |
| `workflows/backup.yaml` | `workflows/backup.yaml` | Backup workflow |
| `workflows/morning-brief.yaml` | `workflows/morning-brief.yaml` | Morning briefing workflow |
| `.env.example` | `.env.example` | Environment variable template |

Custom template sources can be provided when constructing the `TemplateManager`.

## Template Status

Each tracked template has one of four statuses:

| Status | Meaning |
|--------|---------|
| `current` | File matches the shipped version exactly |
| `modified` | User has made local changes (hash differs from shipped) |
| `missing` | File was tracked but has been deleted |
| `untracked` | Template source exists but has never been initialized |

## CLI Reference

All commands are under `claw template`.

### `claw template init`

Copy managed templates to the project directory. Only installs templates that do not yet exist at their destination. Already-installed templates are skipped.

```bash
claw template init
```

```
  Installed: workflows/deploy.yaml
  Installed: workflows/backup.yaml
  Installed: workflows/morning-brief.yaml

3 template(s) initialized.
```

### `claw template list`

Show all tracked templates and their current status.

```bash
claw template list
```

```
              Managed Templates
+-----------------------------+-------------------------------+----------+
| Template                    | Destination                   | Status   |
+-----------------------------+-------------------------------+----------+
| docker-compose.yaml         | /home/ray/.../docker-compose.yaml | modified |
| docker-compose.prod.yaml    | /home/ray/.../docker-compose.prod.yaml | current  |
| workflows/deploy.yaml       | /home/ray/.../workflows/deploy.yaml | current  |
| workflows/backup.yaml       | /home/ray/.../workflows/backup.yaml | missing  |
| workflows/morning-brief.yaml| /home/ray/.../workflows/morning-brief.yaml | current  |
| .env.example                | /home/ray/.../.env.example     | current  |
+-----------------------------+-------------------------------+----------+
```

### `claw template diff`

Show unified diffs between the current file and the shipped version. Without an argument, diffs all templates.

```bash
claw template diff                     # All templates
claw template diff docker-compose.yaml # Single template
```

```
docker-compose.yaml
--- shipped/docker-compose.yaml
+++ current/docker-compose.yaml
@@ -12,6 +12,7 @@
   msg-gateway:
     build: ./msg_gateway
     ports:
+      - "8100:8100"
       - "8000:8000"
```

### `claw template reset`

Restore a template to its shipped version. The current file is backed up with a `.bak` extension before overwriting.

```bash
claw template reset docker-compose.yaml
```

```
Reset: docker-compose.yaml (backup created)
```

The backup is saved as `docker-compose.yaml.bak` in the same directory.

### `claw template upgrade`

Apply template updates from the latest shipped versions. Behavior depends on the current state of each file:

| Current State | Action |
|---------------|--------|
| Unmodified by user | Overwrite with new shipped version |
| Modified by user | Create timestamped backup, then overwrite |
| Missing (user deleted) | Skip -- respects intentional removal |
| Source missing | Skip with warning |

```bash
claw template upgrade
```

```
  docker-compose.yaml: backup + updated
  docker-compose.prod.yaml: updated
  workflows/deploy.yaml: updated
  workflows/backup.yaml: skipped
  workflows/morning-brief.yaml: updated
  .env.example: updated

Upgrade complete.
```

Timestamped backups use the format `<file>.<YYYYMMDDHHMMSS>.bak` (e.g., `docker-compose.yaml.20260303120000.bak`).

## Python API

### TemplateManager

```python
from superpowers.template_manager import TemplateManager

tm = TemplateManager(
    project_dir="/home/ray/claude-superpowers",
    data_dir="/home/ray/.claude-superpowers",
)
```

### Initialize Templates

```python
installed = tm.init()
# ["workflows/deploy.yaml", "workflows/backup.yaml"]
```

### List Templates

```python
templates = tm.list_templates()
for t in templates:
    print(f"{t['name']}: {t['status']}")
# docker-compose.yaml: modified
# workflows/deploy.yaml: current
```

### Diff Templates

```python
diffs = tm.diff()  # All templates
diffs = tm.diff("docker-compose.yaml")  # Single template

for name, diff_text in diffs.items():
    if diff_text:
        print(f"--- {name} ---")
        print(diff_text)
```

### Reset a Template

```python
ok = tm.reset("docker-compose.yaml")
# True (backup created, file restored to shipped version)
```

### Upgrade All Templates

```python
actions = tm.upgrade()
# {
#     "docker-compose.yaml": "backup_and_updated",
#     "docker-compose.prod.yaml": "updated",
#     "workflows/backup.yaml": "skipped",
# }
```

### Custom Template Sources

```python
tm = TemplateManager(
    template_sources={
        "docker-compose.yaml": "docker-compose.yaml",
        "my-config.yaml": "deploy/my-config.yaml",
    },
)
```

## Manifest Format

The manifest is stored at `~/.claude-superpowers/templates.json`:

```json
{
  "docker-compose.yaml": {
    "shipped_hash": "a1b2c3d4e5f6...",
    "installed_hash": "a1b2c3d4e5f6...",
    "dest": "/home/ray/claude-superpowers/docker-compose.yaml",
    "installed_at": "2026-03-03T12:00:00+00:00"
  }
}
```

| Field | Description |
|-------|-------------|
| `shipped_hash` | SHA-256 of the source template at install time |
| `installed_hash` | SHA-256 of the file as written to the destination |
| `dest` | Absolute path to the installed file |
| `installed_at` | ISO 8601 timestamp of the last install or upgrade |

## Examples

### First-Time Template Setup

```bash
claw template init
claw template list
```

### Check for Local Modifications Before Upgrading

```bash
claw template diff
# Review changes, then:
claw template upgrade
```

### Restore a File You Accidentally Modified

```bash
claw template reset docker-compose.yaml
```

The original is backed up to `docker-compose.yaml.bak`. Your changes are preserved there if you need to re-apply them.

### Upgrade After Pulling New Code

```bash
git pull
claw template upgrade
```

Modified templates get timestamped backups. Unmodified templates are silently updated. Deleted templates are not recreated.

## Troubleshooting

**"All templates already installed"** -- `claw template init` only copies templates that do not yet exist. If you want to force an update, use `claw template upgrade` or `claw template reset <name>`.

**"source missing"** -- The template source file referenced in `template_sources` does not exist in the project directory. This can happen if a file was removed from the repo. Restore it from git or remove the entry from the manifest.

**Backup files accumulating** -- Each `upgrade` or `reset` creates a backup. Clean up old backups manually or with: `find . -name "*.bak" -mtime +30 -delete`.

**"Template 'xxx' not found"** -- The name passed to `claw template reset` must match a key in the template sources dict. Use `claw template list` to see valid names.

## Modules

| Module | Path | Purpose |
|--------|------|---------|
| `template_manager` | `superpowers/template_manager.py` | Core engine: manifest tracking, init, diff, reset, upgrade |
| `cli_template` | `superpowers/cli_template.py` | Click commands for `claw template` |
