# Security

Authentication, encryption, sandboxing, and risk disclosures for claude-superpowers.

---

## Authentication Model

### Dashboard (HTTP Basic Auth)

The web dashboard at port 8200 requires HTTP Basic authentication on all `/api/*` endpoints.

| Setting | Source | Description |
|---------|--------|-------------|
| `DASHBOARD_USER` | `.env` | Username (no default -- must be set) |
| `DASHBOARD_PASS` | `.env` | Password (no default -- must be set) |

The `/health` endpoint is unauthenticated (used by Docker health checks and monitoring tools).

**Changing credentials:**

1. Edit `.env` and update `DASHBOARD_USER` / `DASHBOARD_PASS`
2. Recreate the container: `docker compose up -d dashboard` (a `restart` will NOT re-read `.env`)
3. Verify: `curl -u "user:pass" http://localhost:8200/api/status`

Generate a strong password:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

### Telegram Bot (Chat ID Allowlist)

The Telegram bot uses a secure-by-default authorization model.

| Setting | Source | Description |
|---------|--------|-------------|
| `ALLOWED_CHAT_IDS` | `.env` | Comma-separated list of permitted chat IDs |

Behavior:
- If `ALLOWED_CHAT_IDS` is empty or not set, **all messages are rejected**
- Unauthorized attempts are logged (once per chat ID to prevent log spam)
- The allowlist can be modified at runtime via the `AuthGate.add()` / `AuthGate.remove()` methods

Finding your chat ID: Send any message to the bot and check the application logs for the rejected chat ID.

### Webhook Signature Validation (Phase G)

Inbound webhooks are validated using **fail-closed** middleware (`msg_gateway/middleware.py`).

| Channel  | Mechanism | Env Variable |
|----------|-----------|--------------|
| Telegram | `X-Telegram-Bot-Api-Secret-Token` header | `TELEGRAM_WEBHOOK_SECRET` |
| Slack    | HMAC-SHA256 (`v0` signing) | `SLACK_SIGNING_SECRET` |
| Discord  | Ed25519 signature (via PyNaCl) | `DISCORD_PUBLIC_KEY` |

**Behavior:**
- All POST requests to `/webhook/*` paths MUST carry a valid signature
- If the corresponding env var is not set, the request is **rejected** (not allowed through)
- Set `WEBHOOK_REQUIRE_SIGNATURE=false` to disable validation (not recommended; for debugging only)
- Health endpoints (`/health`, `/api/health`) are always exempt

### Rate Limiting (Phase G)

Both the message gateway and the dashboard enforce per-IP rate limiting via token-bucket middleware.

| Setting | Default | Description |
|---------|---------|-------------|
| `RATE_LIMIT_PER_IP` | `60` | Max requests per minute per IP address |
| `RATE_LIMIT_PER_USER` | `120` | Max requests per minute per authenticated user |

**Behavior:**
- Returns `429 Too Many Requests` with `Retry-After: 60` header when exceeded
- Health endpoints are exempt from rate limiting
- Token buckets refill continuously (not in fixed windows)
- Stale buckets are cleaned up after 10 minutes of inactivity

Middleware files:
- `msg_gateway/middleware.py` -- webhook validation + rate limiting for the message gateway
- `dashboard/middleware.py` -- rate limiting for the dashboard

### Startup Security Validation (Phase G)

`Settings.validate_security()` checks configuration at startup and logs warnings for:

- Missing `DASHBOARD_USER` or `DASHBOARD_PASS`
- Insecure default credential values (e.g., "admin", "password", "changeme")
- `ENVIRONMENT=production` without `FORCE_HTTPS=true`
- `WEBHOOK_REQUIRE_SIGNATURE` disabled

Call `settings.validate_security()` in your app startup to surface issues early.

| Setting | Default | Description |
|---------|---------|-------------|
| `FORCE_HTTPS` | `false` (dev) / `true` (production) | Enforce HTTPS transport |
| `ENVIRONMENT` | `development` | Set to `production` to auto-enable HTTPS enforcement |

### Channel Adapter Interface (Phase G)

A new abstract base class (`msg_gateway/channels/base.py`) defines the contract for inbound channel adapters:

- `name: str` -- channel identifier
- `receive(request) -> Message` -- parse inbound webhook payload
- `acknowledge(message) -> None` -- send read receipt or reaction
- `start_processing_indicator(message) -> None` -- show typing indicator
- `send_response(message, response) -> None` -- send reply
- `supports_streaming: bool` -- whether the adapter supports streaming responses

This is separate from the simpler `superpowers/channels/base.py::Channel` class (outbound-only). Existing adapters can migrate to this interface incrementally.

### Webhook / API Security

The message gateway (`msg-gateway`) at port 8100 now includes webhook signature validation and rate limiting middleware. It should still be run on localhost or behind a reverse proxy for additional protection.

The MCP server (`claw-mcp`) communicates over stdio and inherits the security context of the calling process (Claude Code).

---

## Vault (Encrypted Credential Store)

### How It Works

The vault stores all credentials in a single age-encrypted file at `~/.claude-superpowers/vault.enc`.

1. **Keypair**: `claw vault init` generates an X25519 keypair via `age-keygen`
2. **Identity file**: Private key stored at `~/.claude-superpowers/age-identity.txt` (chmod 600)
3. **Encryption**: `age -r <public-key>` encrypts the JSON blob
4. **Decryption**: `age -d -i <identity-file>` decrypts it
5. **Atomic writes**: Set/delete operations decrypt to memory, modify, re-encrypt to a temp file, then `os.replace()` to the vault path

The `age` and `age-keygen` CLI binaries are called as subprocesses. No age library is linked.

### Key Management

| File | Permissions | Purpose |
|------|------------|---------|
| `~/.claude-superpowers/age-identity.txt` | `600` | age private key (X25519) |
| `~/.claude-superpowers/vault.enc` | `600` | Encrypted credential store |

On macOS, the identity file path is optionally cached in Keychain (service: `claude-superpowers-vault`, account: `age-identity`). This stores the *path*, not the key itself.

### Credential Rotation

The `CredentialRotationChecker` (`superpowers/credential_rotation.py`) tracks secret ages:

- Policies defined in `~/.claude-superpowers/rotation_policies.yaml`
- Default max age: 90 days
- Warning threshold: 80% of max age (72 days at default)
- Statuses: `ok`, `warning`, `expired`
- Check with: `claw vault rotation check`

---

## Skill Sandboxing

Skills execute via two modes in `SkillLoader`:

### Standard Mode (`loader.run()`)

- Inherits the full parent process environment
- Skill runs in its own directory as cwd
- 5-minute execution timeout

### Sandboxed Mode (`loader.run_sandboxed()`)

- **Minimal environment**: Only `PATH`, `HOME`, `LANG`, `TERM` are passed
- **Vault exception**: Skills with `vault` in their `permissions` list receive the full environment including vault-injected secrets
- Same 5-minute timeout
- Used by the intake pipeline for automatic skill execution

### Dependency Gating

Before execution, the loader checks all entries in the skill's `dependencies` list against `which`. Missing dependencies cause the skill to fail with a clear error, preventing partial execution.

---

## Audit Log

### Format

Append-only JSON Lines file at `~/.claude-superpowers/audit.log`.

Each line is a JSON object:

```json
{
  "ts": "2026-03-02T14:30:00.123456+00:00",
  "action": "skill.run",
  "detail": "Executed network-scan",
  "source": "cli",
  "metadata": {
    "skill": "network-scan",
    "exit_code": 0,
    "duration_ms": 4200
  }
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ts` | string (ISO 8601) | UTC timestamp |
| `action` | string | Action identifier (e.g., `skill.run`, `vault.set`, `cron.execute`, `intake.task_completed`) |
| `detail` | string | Human-readable description |
| `source` | string | Origin component (e.g., `cli`, `intake`, `cron`, `dashboard`) |
| `metadata` | object | Optional structured data specific to the action |

### What Is Logged

| Action Pattern | Events |
|---------------|--------|
| `skill.*` | Skill execution (start, complete, fail) |
| `vault.*` | Vault init, set, get, delete |
| `cron.*` | Job add, remove, enable, disable, execute |
| `msg.*` | Message send, test, notify |
| `ssh.*` | Remote command execution |
| `workflow.*` | Workflow run, step execution |
| `intake.*` | Context clear, plan, skill map, task start/complete, session save |
| `watcher.*` | File events and triggered actions |
| `dashboard.*` | API calls (when instrumented) |

### Accessing the Log

```bash
# CLI
claw audit tail              # Last 20 entries
claw audit search "vault"    # Search by keyword

# Dashboard API
GET /api/audit/tail?limit=50
GET /api/audit/search?query=skill&limit=20

# MCP
audit_tail(limit=20)
audit_search(query="ssh", limit=50)
```

---

## Hardening Checklist

### Network

- [ ] Bind the dashboard to `127.0.0.1` or use a reverse proxy with TLS
- [ ] Do not expose port 8100 (msg-gateway) to untrusted networks
- [ ] Use Cloudflare Tunnel or VPN for remote access (see `docs/cloudflared-setup.md`)
- [ ] Restrict Redis to localhost (`bind 127.0.0.1` in redis.conf or Docker network isolation)

### Webhook Security (Phase G)

- [ ] Set `TELEGRAM_WEBHOOK_SECRET` for Telegram webhook validation
- [ ] Set `SLACK_SIGNING_SECRET` for Slack webhook validation
- [ ] Set `DISCORD_PUBLIC_KEY` for Discord webhook validation
- [ ] Verify `WEBHOOK_REQUIRE_SIGNATURE=true` (default) is not overridden
- [ ] Test webhook rejection by sending unsigned requests

### Rate Limiting (Phase G)

- [ ] Verify rate limiting is active on both dashboard and msg-gateway
- [ ] Tune `RATE_LIMIT_PER_IP` if needed (default: 60 req/min)
- [ ] Tune `RATE_LIMIT_PER_USER` if needed (default: 120 req/min)
- [ ] Monitor 429 responses in logs for false positives

### Credentials

- [ ] Set strong `DASHBOARD_PASS` (use `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`)
- [ ] Avoid insecure defaults ("admin", "password", "changeme", etc.) for DASHBOARD_USER/DASHBOARD_PASS
- [ ] Run `settings.validate_security()` at startup to detect misconfigurations
- [ ] Set `ALLOWED_CHAT_IDS` for the Telegram bot (empty = all messages rejected)
- [ ] Store sensitive tokens in the vault, not in `.env` where possible
- [ ] Review `~/.claude-superpowers/age-identity.txt` permissions: must be `600`
- [ ] Review `~/.claude-superpowers/vault.enc` permissions: must be `600`
- [ ] Set up credential rotation policies (`claw vault rotation policy`)

### HTTPS / Transport (Phase G)

- [ ] Set `ENVIRONMENT=production` in production deployments (auto-enables FORCE_HTTPS)
- [ ] Or explicitly set `FORCE_HTTPS=true`
- [ ] Use a TLS-terminating reverse proxy (nginx, Caddy, or Cloudflare Tunnel)

### Skills

- [ ] Review `permissions` in `skill.yaml` before granting `vault` access
- [ ] Audit third-party skills before installing
- [ ] Use sandboxed execution (`run_sandboxed()`) for untrusted skills
- [ ] Check `dependencies` lists for unexpected binary requirements

### SSH

- [ ] Use key-based authentication instead of passwords where possible
- [ ] Store SSH passwords/passphrases in the vault, not in config files
- [ ] Limit `hosts.yaml` to hosts you actually need to manage
- [ ] Use specific host groups instead of `all` for destructive commands

### Docker

- [ ] Keep the dashboard volume mount read-only (`:ro` in docker-compose.yaml)
- [ ] Use Docker network isolation between services
- [ ] Pin image versions instead of using `latest` in production

### Filesystem

- [ ] The `~/.claude-superpowers/` directory should be owned by the running user
- [ ] The audit log (`audit.log`) should be append-only where the OS supports it
- [ ] Rotate or compress old audit logs periodically

---

## Risk Disclosures

### What Is NOT Protected

1. **Identity file on disk**: The age private key at `~/.claude-superpowers/age-identity.txt` is a plaintext file. Anyone with filesystem access to this file can decrypt the vault. The vault's security depends entirely on filesystem permissions and user account security.

2. **Secrets in memory**: During vault decrypt/encrypt cycles, secrets are briefly held in process memory. There is no secure memory wiping.

3. **Dashboard transport**: The dashboard serves over HTTP by default. Credentials are sent as Base64-encoded Basic auth headers. Without TLS (reverse proxy or Cloudflare Tunnel), credentials are visible on the network.

4. **Message gateway**: The `msg-gateway` service now validates webhook signatures (Phase G) but the `/send` endpoint has no authentication. Anyone who can reach port 8100 can send messages through configured channels unless network-level restrictions are in place.

5. **Cron job environment**: Shell-type cron jobs inherit the daemon's environment, which may include secrets loaded from `.env`. Job output logs may contain sensitive output.

6. **SSH credentials in vault**: While encrypted at rest, SSH passwords are decrypted and passed to paramiko at connection time. They exist in memory during the SSH session.

7. **Audit log contents**: The audit log records actions and metadata but does not redact sensitive values from detail strings. Review what your skills and commands write to the log.

8. **Browser profiles**: Playwright profiles at `~/.claude-superpowers/browser/profiles/` contain cookies, localStorage, and session data in plaintext on disk.

9. **Telegram bot session history**: When Redis is unavailable, conversation history is stored in-memory only and lost on restart. When Redis is available, history is stored in Redis without encryption.

10. **Claude-type cron jobs**: Jobs that run `claude -p` pass prompts and receive responses through subprocess. Prompts may contain sensitive context. Responses are written to log files.
