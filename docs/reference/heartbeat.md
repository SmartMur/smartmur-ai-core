# Heartbeat Skill

## Overview

The heartbeat skill performs health checks against your homelab infrastructure. It pings hosts, probes HTTP services, and produces a structured status report. Run it manually to spot-check your network or schedule it as a cron job for continuous monitoring.

## Monitored Hosts

| Host | Address | ICMP Ping | HTTP Probe |
|------|---------|-----------|------------|
| Switch | `192.168.30.1` | yes | yes (management UI) |
| CGM | `192.168.30.50` | yes | yes (API endpoint) |
| TrueNAS | `192.168.30.117` | yes | yes (web UI port 443) |
| PVE1 | `192.168.30.100` | yes | yes (Proxmox API port 8006) |
| PVE2 | `192.168.30.101` | yes | yes (Proxmox API port 8006) |
| Docker | `192.168.30.110` | yes | yes (Portainer port 9443) |

Host definitions live in the skill's configuration file at `skills/heartbeat/hosts.yaml`. Add or remove hosts by editing that file.

## Health Checks

Each host receives two checks:

1. **ICMP Ping** -- Sends 3 ICMP echo requests with a 2-second timeout. A host is considered reachable if at least one reply is received.

2. **HTTP Service Probe** -- Sends an HTTP(S) GET or HEAD request to the host's service URL with a 5-second timeout. A service is considered healthy if it returns a 2xx or 3xx status code. TLS certificate errors are ignored (self-signed certs are common in homelabs).

## Running Manually

### Via claw CLI

```bash
claw skill run heartbeat
```

### Via Claude Code slash command

Type `/heartbeat` in a Claude Code session.

### Direct execution

```bash
cd /home/ray/claude-superpowers
./skills/heartbeat/run.sh
```

## Output Format

The skill outputs a table to stdout:

```
HOST       IP               PING    HTTP    LATENCY
Switch     192.168.30.1     UP      200     12ms
CGM        192.168.30.50    UP      200     8ms
TrueNAS    192.168.30.117   UP      200     15ms
PVE1       192.168.30.100   UP      200     22ms
PVE2       192.168.30.101   DOWN    --      --
Docker     192.168.30.110   UP      200     11ms

Summary: 5/6 hosts UP | 1 DOWN (PVE2)
```

When any host is DOWN or an HTTP probe fails, the exit code is `1`. When all hosts are healthy, the exit code is `0`. This makes it easy to chain with notifications or alerting.

## Setting Up as a Cron Job

Schedule heartbeat checks using the cron subsystem:

### Every 15 minutes

```bash
claw cron add heartbeat-check \
  --type skill \
  --skill heartbeat \
  --schedule "every 15m"
```

### Every hour with a webhook alert on failure

Combine heartbeat with a shell wrapper that sends a webhook when something is down:

```bash
claw cron add heartbeat-alert \
  --type shell \
  --command "claw skill run heartbeat || curl -X POST https://hooks.slack.com/services/T00/B00/xxx -d '{\"text\":\"Heartbeat FAILED -- check claw cron logs heartbeat-alert\"}'" \
  --schedule "every 1h"
```

### Daily Claude-powered analysis

Let Claude read the heartbeat history and identify patterns:

```bash
claw cron add heartbeat-analysis \
  --type claude \
  --prompt "Read the last 7 days of heartbeat logs at ~/.claude-superpowers/cron/output/heartbeat-check/ and identify any hosts with recurring downtime or increasing latency trends." \
  --schedule "daily at 08:00"
```

### View heartbeat job logs

```bash
claw cron logs heartbeat-check
claw cron logs heartbeat-check --tail 20
```

## Configuration

The `hosts.yaml` file in the skill directory defines what to check:

```yaml
hosts:
  - name: Switch
    address: 192.168.30.1
    http_url: http://192.168.30.1
    ping: true

  - name: TrueNAS
    address: 192.168.30.117
    http_url: https://192.168.30.117
    ping: true
    tls_verify: false

  - name: PVE1
    address: 192.168.30.100
    http_url: https://192.168.30.100:8006
    ping: true
    tls_verify: false
```

Each entry supports:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Display name in output |
| `address` | yes | IP or hostname for ICMP ping |
| `http_url` | no | URL for HTTP probe (skip if omitted) |
| `ping` | no | Enable ICMP ping (default: `true`) |
| `tls_verify` | no | Verify TLS certificates (default: `false`) |
| `timeout` | no | Per-host timeout override in seconds |
