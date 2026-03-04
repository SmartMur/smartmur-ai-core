"""Policy engine for orchestration safety — enforce command, file, and output policies."""

from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class PolicyAction(StrEnum):
    allow = "allow"
    deny = "deny"
    require_approval = "require_approval"


@dataclass
class PolicyRule:
    """A single rule within a policy."""

    action: PolicyAction
    resource_pattern: str = ""  # glob for file paths
    command_pattern: str = ""  # regex for commands
    secret_patterns: list[str] = field(default_factory=list)  # regex list for output scanning
    max_retries: int = 3
    timeout_seconds: int = 300
    description: str = ""

    def _compiled_command_re(self) -> re.Pattern | None:
        if not self.command_pattern:
            return None
        try:
            return re.compile(self.command_pattern, re.IGNORECASE)
        except re.error:
            logger.warning("Invalid command_pattern regex: %s", self.command_pattern)
            return None

    def matches_command(self, command: str) -> bool:
        """Return True if this rule's command_pattern matches the given command."""
        if not self.command_pattern:
            return False
        pat = self._compiled_command_re()
        if pat is None:
            return False
        return bool(pat.search(command))

    def matches_file(self, path: str) -> bool:
        """Return True if this rule's resource_pattern matches the file path."""
        if not self.resource_pattern:
            return False
        return fnmatch.fnmatch(path, self.resource_pattern)


@dataclass
class PolicyDecision:
    """Result of a policy check."""

    action: PolicyAction
    reason: str
    policy_name: str = ""


@dataclass
class Policy:
    """A named collection of rules."""

    name: str
    description: str = ""
    rules: list[PolicyRule] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in secret detection patterns
# ---------------------------------------------------------------------------

_DEFAULT_SECRET_PATTERNS: list[str] = [
    # Generic API keys (long hex/base64 strings preceded by key-like labels)
    r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})",
    # Bearer tokens
    r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}",
    # AWS access keys
    r"AKIA[0-9A-Z]{16}",
    # Generic tokens
    r"(?i)(?:token|secret|password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{8,})",
    # Private keys
    r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH|PGP)?\s*PRIVATE KEY-----",
    # GitHub personal access tokens
    r"gh[pousr]_[A-Za-z0-9_]{36,}",
    # Slack tokens
    r"xox[bpoa]-[0-9A-Za-z\-]{10,}",
    # Generic long hex secrets (32+ chars)
    r"(?i)(?:secret|key|token|password)\s*[:=]\s*['\"]?[0-9a-f]{32,}",
]

# Compiled versions for performance
_COMPILED_SECRET_PATTERNS: list[re.Pattern] = []


def _get_compiled_secret_patterns() -> list[re.Pattern]:
    """Lazily compile default secret patterns."""
    if not _COMPILED_SECRET_PATTERNS:
        for p in _DEFAULT_SECRET_PATTERNS:
            try:
                _COMPILED_SECRET_PATTERNS.append(re.compile(p))
            except re.error:
                logger.warning("Failed to compile secret pattern: %s", p)
    return _COMPILED_SECRET_PATTERNS


# ---------------------------------------------------------------------------
# Default built-in policies
# ---------------------------------------------------------------------------


def _default_policies() -> list[Policy]:
    """Return the built-in policies that are always active."""
    return [
        Policy(
            name="destructive-commands",
            description="Deny catastrophically destructive commands",
            rules=[
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+/\s*$|rm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?-[a-zA-Z]*f[a-zA-Z]*\s+/\s*$|rm\s+-rf\s+/\s*$",
                    description="Deny rm -rf /",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"(?i)\bDROP\s+(TABLE|DATABASE|SCHEMA)\b",
                    description="Deny DROP TABLE/DATABASE/SCHEMA",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"(?i)\bFORMAT\s+[A-Z]:",
                    description="Deny FORMAT drive commands",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"(?i)\bmkfs(?:\.[a-z0-9_+-]+)?\b",
                    description="Deny mkfs (filesystem format)",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"dd\s+.*of=/dev/[sh]d[a-z]",
                    description="Deny dd to raw block devices",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"(?i):\(\)\s*\{\s*:\|\:\s*&\s*\}\s*;",
                    description="Deny fork bombs",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"chmod\s+(-[a-zA-Z]*\s+)*777\s+/\s*$",
                    description="Deny chmod 777 /",
                ),
            ],
        ),
        Policy(
            name="force-push-protection",
            description="Deny force push to main/master branches",
            rules=[
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"git\s+push\s+.*--force.*\b(main|master)\b|git\s+push\s+.*\b(main|master)\b.*--force",
                    description="Deny force push to main/master",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    command_pattern=r"git\s+push\s+-f\s+.*\b(main|master)\b|git\s+push\s+.*\b(main|master)\b\s+-f",
                    description="Deny git push -f to main/master",
                ),
            ],
        ),
        Policy(
            name="approval-required",
            description="Commands that require explicit approval",
            rules=[
                PolicyRule(
                    action=PolicyAction.require_approval,
                    command_pattern=r"git\s+push\b",
                    description="Git push requires approval",
                ),
                PolicyRule(
                    action=PolicyAction.require_approval,
                    command_pattern=r"docker\s+(rm|rmi|container\s+rm|image\s+rm)\b",
                    description="Docker remove requires approval",
                ),
                PolicyRule(
                    action=PolicyAction.require_approval,
                    command_pattern=r"docker\s+system\s+prune\b",
                    description="Docker system prune requires approval",
                ),
            ],
        ),
        Policy(
            name="file-protection",
            description="Protect sensitive file paths",
            rules=[
                PolicyRule(
                    action=PolicyAction.deny,
                    resource_pattern="/etc/passwd",
                    description="Deny write access to /etc/passwd",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    resource_pattern="/etc/shadow",
                    description="Deny write access to /etc/shadow",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    resource_pattern="/etc/sudoers",
                    description="Deny write access to /etc/sudoers",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    resource_pattern="*/.ssh/authorized_keys",
                    description="Deny write access to authorized_keys",
                ),
                PolicyRule(
                    action=PolicyAction.deny,
                    resource_pattern="*/.env",
                    description="Deny write access to .env files",
                ),
                PolicyRule(
                    action=PolicyAction.require_approval,
                    resource_pattern="*.pem",
                    description="PEM files require approval",
                ),
                PolicyRule(
                    action=PolicyAction.require_approval,
                    resource_pattern="*.key",
                    description="Key files require approval",
                ),
            ],
        ),
        Policy(
            name="secret-detection",
            description="Detect secrets leaked in command output",
            rules=[
                PolicyRule(
                    action=PolicyAction.deny,
                    secret_patterns=_DEFAULT_SECRET_PATTERNS,
                    description="Detect API keys, tokens, passwords in output",
                ),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------


class PolicyEngine:
    """Load and evaluate orchestration safety policies."""

    def __init__(self, config_path: Path | None = None):
        self._policies: list[Policy] = list(_default_policies())
        self._config_path = config_path
        if config_path is not None:
            self.load_policies(config_path)

    def load_policies(self, config_path: Path) -> None:
        """Load additional policies from a YAML file.

        Custom policies are appended to (not replacing) the built-in defaults.
        """
        self._config_path = config_path
        if not config_path.is_file():
            logger.debug("Policy config not found: %s", config_path)
            return

        try:
            data = yaml.safe_load(config_path.read_text())
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Failed to load policy config %s: %s", config_path, exc)
            return

        if not isinstance(data, dict):
            logger.warning("Policy config must be a YAML mapping, got %s", type(data).__name__)
            return

        policies_data = data.get("policies", [])
        if not isinstance(policies_data, list):
            logger.warning("policies key must be a list")
            return

        for pdata in policies_data:
            if not isinstance(pdata, dict):
                continue
            rules: list[PolicyRule] = []
            for rdata in pdata.get("rules", []):
                if not isinstance(rdata, dict):
                    continue
                action_str = rdata.get("action", "deny")
                try:
                    action = PolicyAction(action_str)
                except ValueError:
                    logger.warning("Unknown policy action: %s", action_str)
                    continue
                rules.append(
                    PolicyRule(
                        action=action,
                        resource_pattern=rdata.get("resource_pattern", ""),
                        command_pattern=rdata.get("command_pattern", ""),
                        secret_patterns=rdata.get("secret_patterns", []),
                        max_retries=rdata.get("max_retries", 3),
                        timeout_seconds=rdata.get("timeout_seconds", 300),
                        description=rdata.get("description", ""),
                    )
                )
            self._policies.append(
                Policy(
                    name=pdata.get("name", "unnamed"),
                    description=pdata.get("description", ""),
                    rules=rules,
                )
            )
        logger.info("Loaded %d custom policies from %s", len(policies_data), config_path)

    def check_command(self, command: str) -> PolicyDecision:
        """Check a command string against all policies.

        Returns the first matching deny/require_approval decision.
        If no rules match, returns allow.

        Deny rules are evaluated first (across all policies), then
        require_approval rules, so that a deny always wins.
        """
        command = command.strip()
        if not command:
            return PolicyDecision(action=PolicyAction.allow, reason="Empty command")

        # First pass: deny rules
        for policy in self._policies:
            for rule in policy.rules:
                if rule.action == PolicyAction.deny and rule.matches_command(command):
                    return PolicyDecision(
                        action=PolicyAction.deny,
                        reason=rule.description or f"Denied by policy '{policy.name}'",
                        policy_name=policy.name,
                    )

        # Second pass: require_approval rules
        for policy in self._policies:
            for rule in policy.rules:
                if rule.action == PolicyAction.require_approval and rule.matches_command(command):
                    return PolicyDecision(
                        action=PolicyAction.require_approval,
                        reason=rule.description or f"Approval required by policy '{policy.name}'",
                        policy_name=policy.name,
                    )

        return PolicyDecision(action=PolicyAction.allow, reason="No matching policy")

    def check_file_access(self, path: str) -> PolicyDecision:
        """Check if accessing/modifying a file path is allowed.

        Returns the first matching deny/require_approval decision.
        """
        path = path.strip()
        if not path:
            return PolicyDecision(action=PolicyAction.allow, reason="Empty path")

        # Normalize path
        normalized = str(Path(path).resolve()) if not path.startswith("*") else path

        # First pass: deny
        for policy in self._policies:
            for rule in policy.rules:
                if rule.action == PolicyAction.deny and rule.resource_pattern:
                    if rule.matches_file(path) or rule.matches_file(normalized):
                        return PolicyDecision(
                            action=PolicyAction.deny,
                            reason=rule.description or f"Denied by policy '{policy.name}'",
                            policy_name=policy.name,
                        )

        # Second pass: require_approval
        for policy in self._policies:
            for rule in policy.rules:
                if rule.action == PolicyAction.require_approval and rule.resource_pattern:
                    if rule.matches_file(path) or rule.matches_file(normalized):
                        return PolicyDecision(
                            action=PolicyAction.require_approval,
                            reason=rule.description
                            or f"Approval required by policy '{policy.name}'",
                            policy_name=policy.name,
                        )

        return PolicyDecision(action=PolicyAction.allow, reason="No matching policy")

    def check_output(self, output: str) -> tuple[bool, str]:
        """Scan command output for secret patterns.

        Returns (has_secrets, redacted_output).
        If secrets are found, they are replaced with [REDACTED] in the output.
        """
        if not output:
            return False, output

        redacted = output
        found = False

        # Check built-in compiled patterns
        for pat in _get_compiled_secret_patterns():
            if pat.search(redacted):
                found = True
                redacted = pat.sub("[REDACTED]", redacted)

        # Check custom secret patterns from loaded policies
        for policy in self._policies:
            for rule in policy.rules:
                for sp in rule.secret_patterns:
                    try:
                        compiled = re.compile(sp)
                    except re.error:
                        continue
                    if compiled.search(redacted):
                        found = True
                        redacted = compiled.sub("[REDACTED]", redacted)

        return found, redacted

    def get_policies(self) -> list[Policy]:
        """Return all loaded policies (built-in + custom)."""
        return list(self._policies)

    def add_policy(self, policy: Policy) -> None:
        """Add a policy at runtime."""
        self._policies.append(policy)

    def remove_policy(self, name: str) -> bool:
        """Remove a policy by name. Returns True if found and removed."""
        before = len(self._policies)
        self._policies = [p for p in self._policies if p.name != name]
        return len(self._policies) < before

    @classmethod
    def from_data_dir(cls) -> PolicyEngine:
        """Create a PolicyEngine loading from the default data directory."""
        from superpowers.config import get_data_dir

        config_path = get_data_dir() / "policies.yaml"
        return cls(config_path=config_path)
