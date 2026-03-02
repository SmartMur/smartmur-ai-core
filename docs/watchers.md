# File Watchers

The watcher subsystem monitors directories for file changes and triggers actions automatically.

## Configuration

Watcher rules live in `~/.claude-superpowers/watchers.yaml`. Each rule specifies a path pattern, event types to watch, and an action to execute.

### Rule Format

```yaml
- name: torrent-mover
  path: ~/Downloads/*.torrent
  events: [created]
  action: move
  command: /mnt/data/torrents/watch/
  enabled: true
```

### Fields

| Field     | Required | Description                                        |
|-----------|----------|----------------------------------------------------|
| `name`    | yes      | Unique identifier for the rule                     |
| `path`    | yes      | Directory or glob pattern to watch                 |
| `events`  | no       | Event types: `created`, `modified`, `deleted`, `moved` (default: `[created]`) |
| `action`  | yes      | Action type: `shell`, `skill`, `workflow`, `move`, `copy` |
| `command` | yes      | Action-specific command or target                  |
| `args`    | no       | Extra arguments (dict, passed to action)           |
| `enabled` | no       | Whether the rule is active (default: `true`)       |

## Actions

### shell

Runs a shell command with `WATCHER_FILE` set to the triggering file path. Extra `args` are available as `WATCHER_{KEY}` env vars.

```yaml
- name: screenshot-optimizer
  path: ~/Desktop/Screenshot*.png
  events: [created]
  action: shell
  command: "optipng $WATCHER_FILE"
```

### skill

Runs a registered skill with the triggering file path passed as the `file` argument.

```yaml
- name: invoice-processor
  path: ~/Documents/invoices/*.pdf
  events: [created]
  action: skill
  command: process-invoice
```

### workflow

Triggers a named workflow (not yet implemented).

### move

Moves the triggering file to the target directory.

```yaml
- name: torrent-mover
  path: ~/Downloads/*.torrent
  events: [created]
  action: move
  command: /mnt/data/torrents/watch/
```

### copy

Copies the triggering file to the target directory.

```yaml
- name: backup-configs
  path: ~/dotfiles/*
  events: [modified]
  action: copy
  command: ~/dotfiles-backup/
```

## CLI Commands

```bash
# List configured rules
claw watcher list

# Start watcher daemon (foreground)
claw watcher start

# Test a rule by simulating a created event
claw watcher test torrent-mover
```

## Daemon Setup

For persistent background operation on Debian/Linux, create a user `systemd` unit that runs:

```bash
claw watcher start
```

For ad-hoc foreground use:

```bash
claw watcher start
```

The watcher daemon logs to `~/.claude-superpowers/logs/watcher-daemon.log`.
