"""Notification profiles — named groups of channel+target combos."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from superpowers.channels.base import ChannelError, SendResult
from superpowers.channels.registry import ChannelRegistry


@dataclass
class ProfileTarget:
    channel: str
    target: str


@dataclass
class NotificationProfile:
    name: str
    targets: list[ProfileTarget] = field(default_factory=list)


class ProfileManager:
    def __init__(
        self,
        registry: ChannelRegistry,
        profiles_path: Path | None = None,
    ):
        self._registry = registry
        if profiles_path is None:
            profiles_path = Path.home() / ".claude-superpowers" / "profiles.yaml"
        self._path = profiles_path
        self._profiles: dict[str, NotificationProfile] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = yaml.safe_load(self._path.read_text()) or {}
        except (yaml.YAMLError, OSError):
            return

        for name, targets in data.items():
            if not isinstance(targets, list):
                continue
            profile = NotificationProfile(name=name)
            for t in targets:
                if isinstance(t, dict) and "channel" in t and "target" in t:
                    profile.targets.append(
                        ProfileTarget(channel=t["channel"], target=t["target"])
                    )
            self._profiles[name] = profile

    def list_profiles(self) -> list[NotificationProfile]:
        return list(self._profiles.values())

    def get(self, name: str) -> NotificationProfile:
        if name not in self._profiles:
            raise KeyError(f"Profile not found: {name}")
        return self._profiles[name]

    def send(self, profile_name: str, message: str) -> list[SendResult]:
        """Fan out a message to all targets in a profile."""
        profile = self.get(profile_name)
        results = []
        for t in profile.targets:
            try:
                ch = self._registry.get(t.channel)
                results.append(ch.send(t.target, message))
            except ChannelError as exc:
                results.append(SendResult(
                    ok=False, channel=t.channel, target=t.target, error=str(exc),
                ))
        return results
