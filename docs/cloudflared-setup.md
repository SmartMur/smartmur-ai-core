# Cloudflare Tunnel Setup Guide

## What Are Cloudflare Tunnels?

Cloudflare Tunnels (formerly Argo Tunnels) create a secure, outbound-only connection from your server to Cloudflare's edge network. This lets you expose local services (dashboards, APIs, web apps) to the internet without opening inbound firewall ports or configuring port forwarding.

**Why we use them:**
- No open inbound ports on the home server (security)
- Automatic HTTPS with Cloudflare-managed certificates
- DDoS protection and Cloudflare Access policies built in
- Survives IP changes (no dynamic DNS needed)
- Zero-trust access control for internal services

## Architecture

```
                  Internet
                     |
              +------+------+
              |  Cloudflare  |
              |    Edge      |
              +------+------+
                     |
           outbound-only tunnel
           (QUIC/HTTP2, encrypted)
                     |
        +------------+------------+
        | Docker: cloudflared     |
        | (cloudflare/cloudflared)|
        +------------+------------+
                     |
        +------------+------------+
        |  Local services         |
        |  (dashboard, APIs, etc) |
        +-------------------------+

  /home/ray/docker/cloudflared/
  +-- docker-compose.yml     # Container definition
  +-- .env                   # CLOUDFLARE_TUNNEL_TOKEN=<token>

  /home/ray/claude-superpowers/skills/
  +-- tunnel-setup/          # Setup helper skill
  +-- cloudflared-fixer/     # Automated monitor + fixer
```

## Prerequisites

1. **Cloudflare account** -- free tier works
2. **A domain** managed by Cloudflare DNS (nameservers pointing to Cloudflare)
3. **Docker** installed on the server
4. **Access to Cloudflare Zero Trust dashboard**: https://one.dash.cloudflare.com/

## Step-by-Step Setup

### 1. Create a Tunnel in Cloudflare Dashboard

1. Log in to https://one.dash.cloudflare.com/
2. Navigate to **Networks > Tunnels**
3. Click **Create a tunnel**
4. Choose **Cloudflared** as the connector type
5. Name your tunnel (e.g., "homelab" or "docker-server")
6. Copy the tunnel token -- it looks like a long base64 string starting with `eyJ...`

### 2. Configure the Token

Using the tunnel-setup skill:

```
/tunnel-setup set-token eyJhIjoiYWJjZGVmMTIzNDU2Nzg5MCIs...
```

This will:
- Validate the token format (50+ chars, base64-like, not a placeholder)
- Write it to `/home/ray/docker/cloudflared/.env`
- Start the cloudflared container via `docker compose up -d`
- Log the action to the audit log
- Send a Telegram notification

Alternatively, set it manually:

```bash
echo 'CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiYWJj...' > /home/ray/docker/cloudflared/.env
cd /home/ray/docker/cloudflared && docker compose up -d
```

### 3. Configure Public Hostnames (in Cloudflare Dashboard)

Back in the Cloudflare dashboard, on your tunnel's configuration page:

1. Click **Public Hostname** tab
2. Add entries mapping subdomains to local services:
   - `dashboard.yourdomain.com` -> `http://localhost:8080`
   - `api.yourdomain.com` -> `http://localhost:3000`
3. Cloudflare automatically creates the DNS CNAME records

### 4. Verify the Tunnel

```
/tunnel-setup status
```

Expected output for a healthy tunnel:
```
=== Cloudflare Tunnel Status ===

Token:     eyJhIjoiY...your token masked
Valid:     yes

Container: cloudflared-cloudflared-1 -- RUNNING
  Status:       running
  Restarts:     0

Health: OK
```

Check logs if something looks wrong:
```
/tunnel-setup logs
```

## Troubleshooting

### Invalid Token (exit code 255, crash loop)

**Symptoms:** Container exits immediately with code 255, restart count climbs rapidly.

**Cause:** The token in `.env` is a placeholder or is invalid.

**Fix:**
```
/tunnel-setup stop
/tunnel-setup set-token <correct-token-from-cloudflare-dashboard>
```

### Placeholder Token ("your_tunnel_token_here")

**Symptoms:** Container crash-loops. Logs show authentication failure.

**Cause:** Default placeholder was never replaced with a real token.

**Fix:** Get a real token from the Cloudflare dashboard and use `/tunnel-setup set-token`.

### Network / DNS Errors

**Symptoms:** Logs show "connection refused", "DNS resolution failed", or "dial tcp" errors.

**Cause:** Server cannot reach Cloudflare's edge (DNS issue, firewall, or internet outage).

**Fix:**
1. Check internet connectivity: `ping 1.1.1.1`
2. Check DNS: `dig +short cloudflare.com`
3. Check if outbound HTTPS/QUIC is blocked
4. Restart the container: `/tunnel-setup start`

### Certificate / TLS Errors

**Symptoms:** Logs show "certificate", "TLS", or "SSL" errors.

**Cause:** Usually a clock skew issue or a corporate proxy intercepting HTTPS.

**Fix:**
1. Verify system time: `date -u`
2. Sync if needed: `sudo timedatectl set-ntp true`
3. Check if a proxy is intercepting traffic

### Container Not Found

**Symptoms:** `/tunnel-setup status` shows "not found".

**Cause:** Container was never created or was removed.

**Fix:**
```
/tunnel-setup start
```

This runs `docker compose up -d` from the cloudflared compose directory.

## Automated Monitoring

The **cloudflared-fixer** skill (`/cloudflared-fixer`) and **infra-fixer** skill (`/infra-fixer`) automatically monitor the tunnel container:

- **Crash loop detection**: If restart count exceeds threshold, the container is stopped to prevent CPU waste
- **Token validation**: Checks `.env` for placeholder values
- **Log analysis**: Scans for known error patterns (invalid token, network errors, cert issues)
- **Auto-recovery**: Restarts the container for transient failures
- **Alerting**: Sends Telegram notifications for crash loops and failures
- **Status persistence**: Writes status to `~/.claude-superpowers/cloudflared-monitor/status.json`
- **Incident log**: Appends to `~/.claude-superpowers/cloudflared-monitor/incident-log.jsonl`

These can be scheduled via cron:
```
claw cron add --name "tunnel-check" --schedule "*/5 * * * *" --type skill --command "cloudflared-fixer"
```

## Docker Compose Reference

File: `/home/ray/docker/cloudflared/docker-compose.yml`

```yaml
services:
    cloudflared:
        command: 'tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}'
        image: 'cloudflare/cloudflared:latest'
        restart: unless-stopped
        env_file:
            - .env
```

The `--no-autoupdate` flag disables cloudflared's built-in auto-updater (we control the image version via Docker instead). The `restart: unless-stopped` policy means Docker will restart the container unless explicitly stopped with `docker stop`.

## Useful Commands

| Command | Description |
|---------|-------------|
| `/tunnel-setup status` | Check tunnel health |
| `/tunnel-setup set-token <token>` | Set token and start |
| `/tunnel-setup start` | Start container |
| `/tunnel-setup stop` | Stop container |
| `/tunnel-setup logs` | View recent logs |
| `/cloudflared-fixer` | Run automated diagnostics |
| `/infra-fixer` | Full infrastructure check |
