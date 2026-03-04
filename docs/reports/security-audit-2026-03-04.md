# Security Audit — 2026-03-04

## Scope
- Application code: `superpowers/`, `msg_gateway/`, `dashboard/`
- Runtime/deploy config: `docker-compose.yaml`, `.env` (local, not committed)
- Dependency vulnerability status for current `.venv`

## Methods
- Pattern scan for high-risk primitives (`shell=True`, `eval`, unsafe deserialization, token leaks)
- Static analysis with Bandit (`bandit -r superpowers msg_gateway dashboard`)
- Dependency CVE scan with pip-audit (`python -m pip_audit`)

## Findings

### 1) High — SSH host key verification is disabled
- **Evidence**: `AutoAddPolicy()` is used for all SSH connections in `ConnectionPool`.
- **Location**: `superpowers/ssh_fabric/pool.py:56`
- **Risk**: Accepts unknown host keys automatically, enabling MITM if DNS/network is compromised.
- **Recommendation**:
  - Use `RejectPolicy()` by default.
  - Load known hosts (`client.load_system_host_keys()` + optional managed known_hosts file).
  - Add explicit onboarding command to trust first host key intentionally.

### 2) High (Operational) — Live API secret present in local `.env`
- **Evidence**: `OPENAI_API_KEY` is present in local `.env`.
- **Location**: `.env:6` (local file, not tracked by git)
- **Risk**: Credential theft if host/user account is compromised; key was also pasted in chat context.
- **Recommendation**:
  - Revoke and reissue the key immediately.
  - Move secret to vault (`claw vault set OPENAI_API_KEY ...`) and remove from plaintext `.env`.
  - Keep file mode `0600` (currently set) and avoid sharing screenshots/logs with secrets.

### 3) Medium — Dynamic SQL column composition in rsync job updates
- **Evidence**: SQL statement interpolates column names via string join.
- **Location**: `dashboard/db.py:345`, `dashboard/db.py:350`
- **Risk**: If untrusted field names ever reach `update_status`, this becomes SQL injection on column clause.
- **Current exposure**: Low in current call sites (internally controlled), but fragile for future refactors.
- **Recommendation**:
  - Enforce a strict allowlist of updatable columns before composing SQL.

### 4) Medium — Dashboard session cookie not marked `Secure`
- **Evidence**: Auth cookie sets `httponly` and `samesite`, but not `secure=True`.
- **Location**: `dashboard/routers/auth.py:52-59`
- **Risk**: Cookie may be sent over plaintext HTTP in non-TLS deployments.
- **Recommendation**:
  - Set `secure=True` when `FORCE_HTTPS` or `ENVIRONMENT=production` is active.

### 5) Medium — Network-exposed service ports in default compose config
- **Evidence**: Redis/dashboard/msg-gateway/browser-engine are bound on all interfaces.
- **Location**: `docker-compose.yaml:5`, `docker-compose.yaml:15`, `docker-compose.yaml:27`, `docker-compose.yaml:53`
- **Risk**: Larger attack surface on any host with reachable network interfaces.
- **Recommendation**:
  - Bind to localhost where possible (e.g., `127.0.0.1:8200:8200`) and front with reverse proxy/auth as needed.

## Tooling Results

### Bandit
- Command: `bandit -r superpowers msg_gateway dashboard`
- Summary:
  - High: 1
  - Medium: 20
  - Low: 117
- Notes:
  - Most low/medium findings are generic subprocess/urlopen heuristics in code paths that already use fixed binaries/domains or trusted config.
  - The high-severity finding is the SSH host-key policy issue above.

### pip-audit
- Command: `python -m pip_audit`
- Result: **No known vulnerabilities found** in installed dependencies.

## Strengths Observed
- `shell=True` appears removed from active code paths.
- Webhook signature validation is fail-closed by default (`WEBHOOK_REQUIRE_SIGNATURE=true`).
- Telegram auth is allowlist-based (`ALLOWED_CHAT_IDS`), and empty allowlist rejects all inbound chats.
- Dashboard credentials are required; insecure defaults are flagged in config validation.

## Priority Remediation Order
1. Fix SSH host key verification policy.
2. Rotate/remove live API key from plaintext env.
3. Add SQL column allowlist in `update_status`.
4. Add `secure` cookie flag tied to production/TLS mode.
5. Tighten docker port bindings by deployment profile.

## Remediation Status (Updated 2026-03-04)
- SSH host key policy: **fixed** (`RejectPolicy` default + `load_system_host_keys`; opt-in `SSH_AUTO_ADD_HOST_KEYS=true`).
- Plaintext `OPENAI_API_KEY` in local `.env`: **removed locally** (`OPENAI_API_KEY=`).
- Rsync dynamic SQL field composition: **fixed** with strict update-field allowlist.
- Dashboard cookie secure flag: **fixed** with TLS/production-aware `secure` handling.
- Docker port bindings: **fixed** by binding exposed services to `127.0.0.1` in `docker-compose.yaml` and `docker-compose.prod.yaml`.

### Remaining Manual Action
- Rotate/revoke any previously exposed OpenAI API key in the OpenAI dashboard since it was pasted in chat and previously present in `.env`.
