# Network Scan

Scan all configured network hosts — ping sweep + TCP port check. No nmap required.

## What it does

1. Ping each configured host to check reachability and measure latency
2. For live hosts, probe common TCP ports (22, 80, 443, 8080, 8443)
3. Optionally sweep entire subnets for host discovery
4. Output a formatted status table with host status and open ports
5. Return exit code 0 if all critical hosts are up, 1 if any are down

## Configuration

Set these environment variables (or in skill.yaml `env:` section):

- `NETWORK_SCAN_HOSTS` — comma-separated `ip:label` pairs (default: homelab hosts)
- `NETWORK_SCAN_SUBNETS` — CIDR subnets to sweep, e.g. `192.168.30.0/24`
- `NETWORK_SCAN_PORTS` — ports to check (default: `22,80,443,8080,8443`)
- `NETWORK_SCAN_CRITICAL` — IPs that must be up (default: all configured hosts)
- `NETWORK_SCAN_TIMEOUT` — timeout in seconds (default: `2`)
- `NETWORK_SCAN_WORKERS` — parallel threads (default: `20`)

Execute: `python3 ~/claude-superpowers/skills/network-scan/run.py`
