SSH fabric — run commands on remote hosts, health checks, Home Assistant control.

## Usage

### List configured hosts
```
claw ssh hosts
```

### Run a command on a host or group
```
claw ssh run proxmox1 "qm list"
claw ssh run docker "docker ps"
claw ssh run all "uptime"
```

### Test SSH connectivity
```
claw ssh test proxmox1
claw ssh test all
```

### Health check all hosts (ping + SSH + uptime)
```
claw ssh health
claw ssh health --json-path /tmp/health.json
```

### Home Assistant — get entity state
```
claw ssh ha state light.office
claw ssh ha state climate.living_room
```

### Home Assistant — call a service
```
claw ssh ha call light turn_on light.office
claw ssh ha call climate set_temperature climate.living_room
```

### Home Assistant — list entities
```
claw ssh ha list
claw ssh ha list --filter light
claw ssh ha list --filter switch
```

## Configuration

- Hosts file: `~/.claude-superpowers/hosts.yaml`
- Example: `~/Projects/claude-superpowers/examples/hosts.yaml`
- Home Assistant: set `HOME_ASSISTANT_URL` and `HOME_ASSISTANT_TOKEN` in `.env`

```
cd ~/Projects/claude-superpowers && claw ssh $ARGUMENTS
```
