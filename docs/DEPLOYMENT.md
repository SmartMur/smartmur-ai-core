# Deployment

Docker Compose deployment, standalone setup, reverse proxy configuration, and health monitoring.

---

## Docker Compose (Full Stack)

The `docker-compose.yaml` in the project root defines three services:

| Service | Port | Purpose |
|---------|------|---------|
| `redis` | 6379 | Session storage for Telegram bot, message pubsub |
| `msg-gateway` | 8100 | HTTP API for multi-channel messaging |
| `dashboard` | 8200 | Web UI + REST API for all subsystems |

### Prerequisites

- Docker Engine 20.10+
- Docker Compose v2
- `.env` file configured (see `docs/CONFIGURATION.md`)

### Deploy

```bash
cd /home/ray/claude-superpowers

# Configure environment
cp .env.example .env
# Edit .env with actual values -- at minimum set DASHBOARD_USER and DASHBOARD_PASS

# Build and start
docker compose up -d

# Verify
docker compose ps
curl -u "${DASHBOARD_USER}:${DASHBOARD_PASS}" http://localhost:8200/api/status
curl http://localhost:8100/health
```

### Update

```bash
cd /home/ray/claude-superpowers

# Pull latest code
git pull --ff-only

# Rebuild and restart
docker compose up -d --build

# Verify
docker compose ps
curl http://localhost:8200/health
```

### Teardown

```bash
docker compose down           # Stop and remove containers
docker compose down -v        # Also remove volumes (Redis data)
```

### Service Details

**Redis**:
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped
```

**Message Gateway**:
```yaml
services:
  msg-gateway:
    build:
      context: .
      dockerfile: msg_gateway/Dockerfile
    ports:
      - "8100:8100"
    env_file:
      - .env
    depends_on:
      - redis
    restart: unless-stopped
```

**Dashboard**:
```yaml
services:
  dashboard:
    build:
      context: .
      dockerfile: dashboard/Dockerfile
    ports:
      - "8200:8200"
    env_file:
      - .env
    volumes:
      - ${HOME}/.claude-superpowers:/root/.claude-superpowers
    restart: unless-stopped
```

The dashboard volume mount gives the container access to jobs, memory DB, audit logs, and other runtime data. For production, append `:ro` to make it read-only:

```yaml
    volumes:
      - ${HOME}/.claude-superpowers:/root/.claude-superpowers:ro
```

---

## Standalone / CLI Deployment

If Docker is not used, run the dashboard and cron daemon directly.

### Install

```bash
cd /home/ray/claude-superpowers

# Create venv (if system python lacks ensurepip, use --without-pip)
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e ".[dev]"

# Install age for vault
sudo apt install -y age    # Debian/Ubuntu
# brew install age          # macOS

# Configure
cp .env.example .env
# Edit .env

# Initialize vault
claw vault init
```

### Run Dashboard Directly

```bash
claw dashboard                          # http://127.0.0.1:8200
claw dashboard --host 0.0.0.0 --port 9000  # Custom bind
claw dashboard --reload                 # Auto-reload for development
```

### Run Cron Daemon

```bash
# Foreground
python -m superpowers.cron_runner

# As a managed service (installs systemd user unit or launchd plist)
claw daemon install
claw daemon status
```

---

## systemd Service (Linux)

The cron daemon can be installed as a systemd user service.

### Install via CLI

```bash
claw daemon install
```

This creates `~/.config/systemd/user/claude-superpowers-cron.service` and starts it with `systemctl --user`.

### Manual systemd Unit

If you need to customize the unit, create it manually:

```ini
# ~/.config/systemd/user/claude-superpowers-cron.service
[Unit]
Description=Claude Superpowers Cron Daemon
After=network.target

[Service]
Type=simple
ExecStart=/home/ray/claude-superpowers/.venv/bin/python -m superpowers.cron_runner
WorkingDirectory=/home/ray/claude-superpowers
EnvironmentFile=/home/ray/claude-superpowers/.env
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now claude-superpowers-cron
systemctl --user status claude-superpowers-cron
journalctl --user -u claude-superpowers-cron -f
```

### File Watcher Service

Similarly, run the file watcher as a systemd service:

```ini
# ~/.config/systemd/user/claude-superpowers-watcher.service
[Unit]
Description=Claude Superpowers File Watcher
After=network.target

[Service]
Type=simple
ExecStart=/home/ray/claude-superpowers/.venv/bin/claw watcher start
WorkingDirectory=/home/ray/claude-superpowers
EnvironmentFile=/home/ray/claude-superpowers/.env
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

### Telegram Bot Service

```ini
# ~/.config/systemd/user/claude-superpowers-telegram.service
[Unit]
Description=Claude Superpowers Telegram Bot
After=network.target

[Service]
Type=simple
ExecStart=/home/ray/claude-superpowers/.venv/bin/python -m telegram-bot.entrypoint
WorkingDirectory=/home/ray/claude-superpowers
EnvironmentFile=/home/ray/claude-superpowers/.env
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

---

## launchd (macOS)

On macOS, the daemon uses launchd instead of systemd.

### Install via CLI

```bash
claw daemon install
```

Creates `~/Library/LaunchAgents/com.claude-superpowers.cron.plist` and loads it via `launchctl`.

### Manage

```bash
claw daemon status      # Check running state
claw daemon uninstall   # Stop and remove the plist
claw daemon logs        # View daemon output
```

---

## Reverse Proxy

### nginx

```nginx
server {
    listen 443 ssl;
    server_name claw.example.com;

    ssl_certificate /etc/letsencrypt/live/claw.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/claw.example.com/privkey.pem;

    # Dashboard
    location / {
        proxy_pass http://127.0.0.1:8200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Message Gateway (optional, if exposed externally)
    location /msg/ {
        proxy_pass http://127.0.0.1:8100/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name claw.example.com;
    return 301 https://$server_name$request_uri;
}
```

### Caddy

```
claw.example.com {
    # Dashboard
    reverse_proxy localhost:8200

    # Message Gateway at /msg/
    handle_path /msg/* {
        reverse_proxy localhost:8100
    }
}
```

Caddy automatically provisions and renews TLS certificates via Let's Encrypt.

### Cloudflare Tunnel (Zero Port Exposure)

For zero-port-exposure remote access, use Cloudflare Tunnels. See `docs/cloudflared-setup.md` for full setup.

```bash
# Quick setup via skill
/tunnel-setup set-token <your-tunnel-token>
/tunnel-setup status
```

The tunnel creates an outbound-only connection from your server to Cloudflare's edge. No inbound ports need to be opened. Cloudflare provides TLS, DDoS protection, and access policies.

---

## TLS

### Option 1: Reverse Proxy with Let's Encrypt

Use nginx + certbot or Caddy (auto-TLS). See reverse proxy section above.

### Option 2: Cloudflare Tunnel

Cloudflare handles TLS termination at the edge. The tunnel between your server and Cloudflare is encrypted (QUIC/HTTP2). Local services can run on plain HTTP.

### Option 3: Self-Signed (Development Only)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/claw.key \
  -out /etc/ssl/certs/claw.crt \
  -subj "/CN=claw.local"
```

Use with nginx `ssl_certificate` / `ssl_certificate_key` directives.

---

## Health Check Endpoints

| Service | Endpoint | Auth | Expected Response |
|---------|----------|------|-------------------|
| Dashboard | `GET /health` | None | `200 OK` with `{"status": "ok"}` |
| Dashboard API | `GET /api/status` | Basic | Aggregate health across all subsystems |
| Message Gateway | `GET /health` | None | `200 OK` |

### Docker Health Checks

Add health checks to `docker-compose.yaml`:

```yaml
services:
  dashboard:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8200/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  msg-gateway:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

### External Monitoring

Schedule the heartbeat skill to check all services:

```bash
claw cron add service-check \
  --type skill \
  --skill heartbeat \
  --schedule "every 5m" \
  --output "critical"
```

This runs the heartbeat skill every 5 minutes and sends results to the `critical` notification profile on failure.

---

## Monitoring

### Cron Daemon Logs

```bash
claw daemon logs              # Recent entries
claw daemon logs --follow     # Stream live
# Raw file: ~/.claude-superpowers/logs/cron-daemon.log
```

### Audit Log

```bash
claw audit tail               # Last 20 entries
claw audit search "error"     # Search by keyword
# Raw file: ~/.claude-superpowers/audit.log
```

### SSH Health Report

```bash
claw ssh health               # Table output
claw ssh health --json        # JSON at ~/.claude-superpowers/ssh/health.json
```

### Dashboard Status Page

The dashboard home page (`#/home`) shows status cards for all 10 subsystems: cron, messaging, SSH, workflows, memory, skills, audit, vault, watchers, browser.

---

## Port Summary

| Port | Service | Bind Default | Protocol |
|------|---------|-------------|----------|
| 6379 | Redis | `0.0.0.0` | TCP |
| 8100 | Message Gateway | `0.0.0.0` | HTTP |
| 8200 | Dashboard | `0.0.0.0` | HTTP |

For production, bind services to `127.0.0.1` and use a reverse proxy for external access:

```yaml
# docker-compose.yaml override
services:
  dashboard:
    ports:
      - "127.0.0.1:8200:8200"
  msg-gateway:
    ports:
      - "127.0.0.1:8100:8100"
  redis:
    ports:
      - "127.0.0.1:6379:6379"
```
