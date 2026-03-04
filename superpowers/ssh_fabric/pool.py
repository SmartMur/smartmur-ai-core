"""Connection pool — cached paramiko SSH clients with lazy creation."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from superpowers.ssh_fabric.base import AuthMethod, HostConfig, SSHError
from superpowers.ssh_fabric.hosts import HostRegistry

if TYPE_CHECKING:
    import paramiko

    from superpowers.vault import Vault


class ConnectionPool:
    def __init__(
        self,
        hosts: HostRegistry,
        vault: Vault | None = None,
        max_age: int = 300,
    ):
        self._hosts = hosts
        self._vault = vault
        self._max_age = max_age
        self._clients: dict[str, tuple[paramiko.SSHClient, float]] = {}

    def get_client(self, alias: str) -> paramiko.SSHClient:
        host = self._hosts.get(alias)

        if alias in self._clients:
            client, created = self._clients[alias]
            if time.time() - created < self._max_age and self._is_alive(client):
                return client
            # Stale or dead — close and reconnect
            try:
                client.close()
            except OSError:
                pass
            del self._clients[alias]

        client = self._connect(host)
        self._clients[alias] = (client, time.time())
        return client

    def _connect(self, host: HostConfig) -> paramiko.SSHClient:
        try:
            import paramiko as _paramiko
        except ImportError as exc:
            raise SSHError(
                "paramiko is required for SSH connections. Install it with: pip install paramiko"
            ) from exc

        client = _paramiko.SSHClient()
        client.set_missing_host_key_policy(_paramiko.AutoAddPolicy())

        try:
            if host.auth == AuthMethod.key:
                kwargs: dict = {
                    "hostname": host.hostname,
                    "port": host.port,
                    "username": host.username,
                    "timeout": 10,
                }
                if host.key_file:
                    kwargs["key_filename"] = host.key_file

                # Check vault for key passphrase
                if self._vault:
                    passphrase = self._vault.get(f"ssh:{host.alias}:passphrase")
                    if passphrase:
                        kwargs["passphrase"] = passphrase

                client.connect(**kwargs)

            elif host.auth == AuthMethod.password:
                if not self._vault:
                    raise SSHError(f"Vault required for password auth on {host.alias}")
                password = self._vault.get(f"ssh:{host.alias}:password")
                if not password:
                    raise SSHError(f"No password in vault for ssh:{host.alias}:password")
                client.connect(
                    hostname=host.hostname,
                    port=host.port,
                    username=host.username,
                    password=password,
                    timeout=10,
                )

            elif host.auth == AuthMethod.agent:
                client.connect(
                    hostname=host.hostname,
                    port=host.port,
                    username=host.username,
                    allow_agent=True,
                    timeout=10,
                )

        except _paramiko.AuthenticationException as exc:
            raise SSHError(f"Authentication failed for {host.alias}: {exc}") from exc
        except _paramiko.SSHException as exc:
            raise SSHError(f"SSH error connecting to {host.alias}: {exc}") from exc
        except OSError as exc:
            raise SSHError(f"Connection failed for {host.alias}: {exc}") from exc

        return client

    @staticmethod
    def _is_alive(client: paramiko.SSHClient) -> bool:
        transport = client.get_transport()
        return transport is not None and transport.is_active()

    def close(self, alias: str) -> None:
        if alias in self._clients:
            client, _ = self._clients.pop(alias)
            try:
                client.close()
            except OSError:
                pass

    def close_all(self) -> None:
        for alias in list(self._clients):
            self.close(alias)

    def __enter__(self) -> ConnectionPool:
        return self

    def __exit__(self, *exc) -> None:
        self.close_all()
