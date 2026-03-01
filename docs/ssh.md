# SSH Fabric

Remote host management, command execution, health monitoring, and Home Assistant integration.

## Host Configuration

Hosts are defined in `~/.claude-superpowers/hosts.yaml`:

```yaml
hosts:
  - alias: proxmox
    hostname: 192.168.30.10
    port: 22
    username: root
    auth: key
    key_file: ~/.ssh/id_ed25519
    groups:
      - servers
      - hypervisors
    tags:
      role: hypervisor

  - alias: truenas
    hostname: 192.168.13.69
    username: ray
    auth: password
    groups:
      - storage

  - alias: pihole
    hostname: 192.168.30.53
    auth: agent
    groups:
      - dns
```

### Fields

| Field      | Required | Default   | Description                              |
|------------|----------|-----------|------------------------------------------|
| `alias`    | yes      | —         | Short name used in commands              |
| `hostname` | yes      | —         | IP address or DNS name                   |
| `port`     | no       | `22`      | SSH port                                 |
| `username` | no       | `root`    | SSH login user                           |
| `auth`     | no       | `key`     | Authentication method: `key`, `password`, `agent` |
| `key_file` | no       | `""`      | Path to SSH private key (for `key` auth) |
| `groups`   | no       | `["all"]` | Groups this host belongs to; `all` is auto-appended |
| `tags`     | no       | `{}`      | Arbitrary key-value metadata             |

## Authentication Methods

### `key` (default)

Uses SSH key-based authentication. If `key_file` is set, that key is used explicitly. Otherwise paramiko uses the default key discovery.

If the key has a passphrase, store it in the vault:

```bash
claw vault set ssh:proxmox:passphrase "my-passphrase"
```

### `password`

Requires the encrypted vault. Store the password first:

```bash
claw vault set ssh:truenas:password "hunter2"
```

The connection pool looks up `ssh:<alias>:password` at connect time.

### `agent`

Delegates authentication to the running SSH agent (`ssh-agent`). No key file or password needed.

## Vault Integration

The SSH fabric uses the same `age`-encrypted vault as the rest of claude-superpowers (`~/.claude-superpowers/vault.enc`). Vault keys used by SSH:

| Vault Key                       | Purpose                  |
|---------------------------------|--------------------------|
| `ssh:<alias>:password`          | Password for `password` auth |
| `ssh:<alias>:passphrase`        | Key passphrase for `key` auth |

Manage with `claw vault`:

```bash
claw vault set ssh:truenas:password "s3cret"
claw vault get ssh:truenas:password
claw vault list
```

## CLI Commands

### Run commands on hosts

```bash
# Single host
claw ssh proxmox "uptime"

# By group
claw ssh servers "df -h"

# All hosts
claw ssh all "hostname"
```

### Host management

```bash
# List configured hosts
claw ssh hosts

# Show groups
claw ssh groups

# Health check
claw ssh health
claw ssh health --json
```

## Connection Pool

The `ConnectionPool` manages cached paramiko SSH clients:

- Lazy connection: clients are created on first use
- Caching: subsequent calls to the same host reuse the existing connection
- Staleness detection: if the transport is no longer active, the client reconnects
- Max age: connections older than `max_age` seconds (default 300) are recycled
- Context manager: `with ConnectionPool(hosts) as pool:` automatically closes all connections on exit

## SSH Executor

The `SSHExecutor` resolves targets (aliases or groups) and runs commands across matched hosts:

```python
from superpowers.ssh_fabric import ConnectionPool, HostRegistry, SSHExecutor

hosts = HostRegistry()
with ConnectionPool(hosts) as pool:
    executor = SSHExecutor(pool, hosts)
    results = executor.run("all", "uptime")
    for r in results:
        print(f"{r.host}: {'OK' if r.ok else 'FAIL'} — {r.stdout.strip()}")
```

Key behaviors:

- A connection failure on one host does not abort execution on others
- Each result includes `stdout`, `stderr`, `exit_code`, and an `ok` flag
- `ok` is `True` only when `exit_code == 0` and no error occurred

## Health Checker

The `HealthChecker` runs ICMP ping and SSH probes against all configured hosts:

```python
from superpowers.ssh_fabric import ConnectionPool, HostRegistry, SSHExecutor
from superpowers.ssh_fabric.health import HealthChecker

hosts = HostRegistry()
with ConnectionPool(hosts) as pool:
    executor = SSHExecutor(pool, hosts)
    checker = HealthChecker(hosts, executor)
    report = checker.check_all()

    for h in report.hosts:
        print(f"{h.alias}: ping={'OK' if h.ping_ok else 'FAIL'} ssh={'OK' if h.ssh_ok else 'FAIL'}")

    # Write to ~/.claude-superpowers/ssh/health.json
    checker.write_json(report)
```

### Health report JSON

Written to `~/.claude-superpowers/ssh/health.json` via atomic replace:

```json
{
  "timestamp": 1700000000.0,
  "all_ok": false,
  "hosts": [
    {
      "alias": "proxmox",
      "hostname": "192.168.30.10",
      "ping_ok": true,
      "ssh_ok": true,
      "uptime": "up 5 days, load average: 0.15, 0.20, 0.18",
      "load_avg": "0.15, 0.20, 0.18",
      "latency_ms": 1.2,
      "error": ""
    }
  ]
}
```

## Home Assistant Integration

Control Home Assistant devices via the REST API:

```python
from superpowers.ssh_fabric.homeassistant import HomeAssistantClient

ha = HomeAssistantClient(
    url="http://192.168.30.50:8123",
    token="your-long-lived-access-token",
)

# Get entity state
state = ha.get_state("light.office")
print(state["state"])  # "on" or "off"

# Turn devices on/off
ha.turn_on("light.office")
ha.turn_off("switch.fan")

# Set thermostat
ha.set_temperature("climate.living_room", 72.0)

# Call any service
ha.call_service("light", "turn_on", "light.office", {"brightness": 200})

# List all states
states = ha.get_states()
```

### Setup

Store the HA token in the vault:

```bash
claw vault set ha:token "your-long-lived-access-token"
```

The token is a long-lived access token generated in the Home Assistant UI under Profile > Long-Lived Access Tokens.

### Error Handling

All errors are raised as `SSHError` with descriptive messages:

- HTTP 401: invalid or expired token
- HTTP 404: entity not found
- Connection refused: HA instance unreachable
