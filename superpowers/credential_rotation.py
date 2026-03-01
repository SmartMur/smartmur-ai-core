"""Credential rotation alerts — track vault secret ages and alert when rotation is due."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import yaml


DEFAULT_MAX_AGE_DAYS = 90
WARNING_THRESHOLD = 0.8  # warn at 80% of max age


class AlertStatus(str, Enum):
    ok = "ok"
    warning = "warning"
    expired = "expired"


@dataclass
class CredentialAlert:
    key: str
    age_days: int
    max_age_days: int
    status: AlertStatus


@dataclass
class RotationPolicy:
    max_age_days: int = DEFAULT_MAX_AGE_DAYS
    last_rotated: str = ""  # ISO 8601

    @property
    def last_rotated_dt(self) -> datetime | None:
        if not self.last_rotated:
            return None
        return datetime.fromisoformat(self.last_rotated)


class CredentialRotationChecker:
    def __init__(self, policies_path: Path | None = None):
        if policies_path is None:
            policies_path = Path.home() / ".claude-superpowers" / "rotation_policies.yaml"
        self._path = policies_path
        self._policies: dict[str, RotationPolicy] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = yaml.safe_load(self._path.read_text()) or {}
        except (yaml.YAMLError, OSError):
            return
        for key, entry in data.items():
            if not isinstance(entry, dict):
                continue
            self._policies[key] = RotationPolicy(
                max_age_days=entry.get("max_age_days", DEFAULT_MAX_AGE_DAYS),
                last_rotated=entry.get("last_rotated", ""),
            )

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, policy in sorted(self._policies.items()):
            data[key] = {
                "max_age_days": policy.max_age_days,
                "last_rotated": policy.last_rotated,
            }
        self._path.write_text(yaml.safe_dump(data, default_flow_style=False))

    def get_policy(self, key: str) -> RotationPolicy:
        return self._policies.get(key, RotationPolicy())

    def set_policy(self, key: str, max_age_days: int) -> None:
        existing = self._policies.get(key, RotationPolicy())
        existing.max_age_days = max_age_days
        self._policies[key] = existing
        self._save()

    def mark_rotated(self, key: str, when: datetime | None = None) -> None:
        """Record that a credential was rotated (call after vault set)."""
        if when is None:
            when = datetime.now(timezone.utc)
        existing = self._policies.get(key, RotationPolicy())
        existing.last_rotated = when.isoformat()
        self._policies[key] = existing
        self._save()

    def check_key(self, key: str, now: datetime | None = None) -> CredentialAlert:
        if now is None:
            now = datetime.now(timezone.utc)
        policy = self.get_policy(key)
        last = policy.last_rotated_dt
        if last is None:
            # No rotation date tracked — treat as expired
            return CredentialAlert(
                key=key,
                age_days=-1,
                max_age_days=policy.max_age_days,
                status=AlertStatus.expired,
            )
        age = (now - last).days
        if age >= policy.max_age_days:
            status = AlertStatus.expired
        elif age >= int(policy.max_age_days * WARNING_THRESHOLD):
            status = AlertStatus.warning
        else:
            status = AlertStatus.ok
        return CredentialAlert(
            key=key,
            age_days=age,
            max_age_days=policy.max_age_days,
            status=status,
        )

    def check_all(self, vault_keys: list[str], now: datetime | None = None) -> list[CredentialAlert]:
        """Check all vault keys against rotation policies."""
        if now is None:
            now = datetime.now(timezone.utc)
        return [self.check_key(key, now) for key in sorted(vault_keys)]

    def list_policies(self) -> dict[str, RotationPolicy]:
        return dict(self._policies)


def run_rotation_check(
    settings,
    profile: str = "info",
    vault=None,
    checker: CredentialRotationChecker | None = None,
    profile_manager=None,
    now: datetime | None = None,
) -> list[CredentialAlert]:
    """Standalone function: run check and send alerts via ProfileManager."""
    from superpowers.channels.registry import ChannelRegistry
    from superpowers.profiles import ProfileManager
    from superpowers.vault import Vault

    if vault is None:
        vault = Vault(
            vault_path=settings.data_dir / "vault.enc",
            identity_file=settings.vault_identity_file or None,
        )

    if checker is None:
        checker = CredentialRotationChecker(
            policies_path=settings.data_dir / "rotation_policies.yaml",
        )

    keys = vault.list_keys()
    alerts = checker.check_all(keys, now=now)

    # Only send notification if there are warnings or expired credentials
    actionable = [a for a in alerts if a.status != AlertStatus.ok]
    if not actionable:
        return alerts

    lines = ["Credential Rotation Alert", "=" * 30]
    for a in actionable:
        age_str = f"{a.age_days}d" if a.age_days >= 0 else "unknown"
        lines.append(f"  [{a.status.value.upper()}] {a.key} — age: {age_str}, max: {a.max_age_days}d")
    message = "\n".join(lines)

    if profile_manager is None:
        try:
            registry = ChannelRegistry(settings)
            profile_manager = ProfileManager(registry)
        except Exception:
            return alerts

    try:
        profile_manager.send(profile, message)
    except (KeyError, Exception):
        pass

    return alerts
