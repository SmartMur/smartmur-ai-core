"""Host registry — loads and resolves SSH hosts from YAML config."""

from __future__ import annotations

from pathlib import Path

from superpowers.config import get_data_dir
from superpowers.ssh_fabric.base import AuthMethod, HostConfig, SSHError

DEFAULT_HOSTS_PATH = get_data_dir() / "hosts.yaml"


class HostRegistry:
    def __init__(self, hosts_path: Path | None = None):
        self._path = hosts_path or DEFAULT_HOSTS_PATH
        self._hosts: dict[str, HostConfig] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return

        try:
            import yaml
        except ImportError:
            # Fall back to a minimal YAML subset if PyYAML isn't installed.
            # hosts.yaml is simple enough that json may work for some files,
            # but we just skip loading rather than crash.
            return

        try:
            raw = self._path.read_text()
            data = yaml.safe_load(raw)
        except Exception:
            return

        if not isinstance(data, dict):
            return

        hosts_list = data.get("hosts", [])
        if not isinstance(hosts_list, list):
            return

        for entry in hosts_list:
            if not isinstance(entry, dict) or "alias" not in entry or "hostname" not in entry:
                continue

            auth_str = entry.get("auth", "key")
            try:
                auth = AuthMethod(auth_str)
            except ValueError:
                auth = AuthMethod.key

            groups = entry.get("groups", ["all"])
            if isinstance(groups, str):
                groups = [groups]
            if "all" not in groups:
                groups.append("all")

            host = HostConfig(
                alias=entry["alias"],
                hostname=entry["hostname"],
                port=int(entry.get("port", 22)),
                username=entry.get("username", "root"),
                auth=auth,
                key_file=entry.get("key_file", ""),
                groups=groups,
                tags=entry.get("tags", {}),
            )
            self._hosts[host.alias] = host

    def get(self, alias: str) -> HostConfig:
        if alias not in self._hosts:
            raise SSHError(f"Host not found: {alias}")
        return self._hosts[alias]

    def resolve(self, target: str) -> list[HostConfig]:
        # Exact alias match
        if target in self._hosts:
            return [self._hosts[target]]

        # Group match (including "all")
        matched = [h for h in self._hosts.values() if target in h.groups]
        if matched:
            return matched

        raise SSHError(f"No hosts or groups match target: {target}")

    def list_hosts(self) -> list[HostConfig]:
        return list(self._hosts.values())

    def groups(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for host in self._hosts.values():
            for group in host.groups:
                result.setdefault(group, []).append(host.alias)
        return result
