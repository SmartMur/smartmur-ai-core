# Security Policy

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Claude Superpowers, please report it **directly and confidentially** to the security team rather than opening a public issue.

**Email**: security@smartmur.dev

Please include:
- Description of the vulnerability
- Affected component(s) and version(s)
- Steps to reproduce (if applicable)
- Potential impact
- Suggested fix (if you have one)

**Do not** disclose the vulnerability publicly until we have issued a patch.

## Response Timeline

- **48 hours**: Initial acknowledgment of your report
- **7 days**: Assessment and severity determination
- **30 days**: Target for patch release (may be sooner for critical issues)
- **Ongoing**: Updates on remediation progress

## Supported Versions

| Version | Python     | Status           | Support Ends |
|---------|------------|------------------|--------------|
| 0.1.0   | 3.12+      | Current          | TBD          |
| < 0.1.0 | 3.12+      | Unsupported      | N/A          |

Security updates are provided for the current version. Users are encouraged to upgrade promptly.

## What Qualifies as a Security Issue

We consider the following as security vulnerabilities:

- **Injection attacks** — Code injection, SQL injection, command injection, shell escape
- **Authentication/Authorization bypasses** — Unintended access to protected resources or functions
- **Credential exposure** — Accidental leakage of secrets, API keys, passwords, or tokens
- **Vault vulnerabilities** — Bypass of encryption, integrity issues, or weak key management
- **Privilege escalation** — Ability to execute commands with elevated privileges unexpectedly
- **File system access violations** — Unintended read/write outside sandboxed paths
- **Denial of service** — Resource exhaustion or crashes affecting availability
- **Cryptographic weaknesses** — Misuse of encryption, weak algorithms, or incorrect implementations

## What Does NOT Qualify

- Feature requests or enhancement suggestions
- Non-security bugs (use Issues instead)
- Cosmetic or UI/UX problems
- Documentation gaps or typos
- Performance issues (unless they enable DoS)
- Misconfiguration by users (e.g., storing vault key in an insecure location)

## Security Features

Claude Superpowers implements defense-in-depth:

### Encrypted Vault
- Credentials stored with **age encryption** at rest (`~/.claude-superpowers/vault.enc`)
- Key material managed via macOS Keychain or equivalent secure storage
- Atomic writes prevent partial/corrupted secrets
- CLI: `claw vault get|set|delete|rotation`

### Skill Sandboxing
- Skill execution strips unnecessary environment variables
- Vault access only granted if explicitly permitted in `skill.yaml`
- Execution sandboxed via process isolation
- Audit logging of all skill invocations

### Audit Logging
- Append-only log at `~/.claude-superpowers/audit.log`
- Records: skill executions, cron jobs, messages sent, SSH commands
- Logs include timestamp, user, command, result
- Tamper detection via integrity checks

### Credential Rotation
- YAML-based rotation policies with warning and expiration thresholds
- Automated alerts for stale or expired credentials
- CLI: `claw vault rotation check|policy`
- Integration with scheduling system for compliance monitoring

### No Default Credentials
- Dashboard requires strong password in `.env` (`DASHBOARD_USER` / `DASHBOARD_PASS`)
- No hardcoded API keys or tokens
- All external integrations require explicit configuration
- `.env.example` provided as reference; `.env` not committed

### Local-First Architecture
- All services run on-premise (local Docker Compose stack)
- No cloud dependencies for core functionality
- External integrations (Slack, Telegram, Discord) are optional adapters
- Network isolation via local Redis pubsub for message bus

## Best Practices

Users should:

1. **Protect the vault key** — Keep `VAULT_IDENTITY_FILE` and Keychain password secure
2. **Rotate credentials regularly** — Use `claw vault rotation policy` to enforce compliance
3. **Review audit logs** — Monitor `~/.claude-superpowers/audit.log` for unexpected activity
4. **Update promptly** — Apply security patches as soon as available
5. **Limit SSH access** — Use strong keys and restrict host access via firewall
6. **Secure .env** — Treat `.env` as sensitive; never commit to version control
7. **Run services as non-root** — Avoid running Docker or cron daemon as root
8. **Monitor browser automation** — Review browser session permissions and website access

## Coordinated Disclosure

We follow coordinated disclosure practices:

- Vulnerabilities are kept confidential until a patch is available
- We provide credit to reporters in release notes (unless they request anonymity)
- We coordinate timing with maintainers of affected dependencies (if applicable)
- Public disclosure happens once users have had time to upgrade

## Security Updates

- Subscribe to GitHub Releases: https://github.com/smartmur/claude-superpowers/releases
- Security advisories published separately from regular releases
- Patch releases provided for critical vulnerabilities on older versions if necessary

## Questions or Suggestions?

If you have general security questions or want to discuss hardening strategies, feel free to reach out to security@smartmur.dev (non-disclosure required for unreported vulnerabilities).

---

*Last updated: 2026-03-03*
