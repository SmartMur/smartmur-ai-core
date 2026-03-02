# Infra Fixer

General-purpose infrastructure health monitor. Checks ALL Docker services, detects crash loops, validates configs, and auto-fixes common issues.

## Usage

```
/infra-fixer
/infra-fixer --no-fix
```

## What it monitors

- **All Docker containers** across 9 compose projects (40+ containers)
- Container health status (running, stopped, restarting, crash-looping)
- Docker healthcheck results (healthy/unhealthy)
- Expected-running containers per project (alerts when core services are down)
- .env files for placeholder values (detects "your_xxx_here" patterns)
- Docker disk usage (images, volumes, build cache)

## Auto-fix capabilities

- **Crash loops:** Stops containers burning CPU in restart loops
- **Stopped core services:** Restarts expected containers that stopped unexpectedly
- **Use `--no-fix`** to run checks only without applying fixes

## Monitored Projects

| Project | Core Containers |
|---------|----------------|
| claude-superpowers | redis, msg-gateway, dashboard |
| zabbix | postgres, server, web |
| netaudit | api, timescaledb, redis |
| joplin | app, db |
| npm | nginx-proxy-manager |
| cloudflared | cloudflared |
| dockhand | dockhand |
| zntv | zntv |
| home_media | gluetun, qbittorrent, jellyfin |

## Exit Codes

- 0: all healthy
- 1: issues detected
- 2: monitor execution error
