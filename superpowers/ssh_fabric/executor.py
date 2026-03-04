"""SSH command executor — runs commands across resolved host targets."""

from __future__ import annotations

from superpowers.ssh_fabric.base import CommandResult, HostConfig, SSHError
from superpowers.ssh_fabric.hosts import HostRegistry
from superpowers.ssh_fabric.pool import ConnectionPool


class SSHExecutor:
    def __init__(self, pool: ConnectionPool, hosts: HostRegistry):
        self._pool = pool
        self._hosts = hosts

    def run(self, target: str, command: str, timeout: int = 30) -> list[CommandResult]:
        resolved = self._hosts.resolve(target)
        results: list[CommandResult] = []
        for host in resolved:
            results.append(self._exec_one(host, command, timeout))
        return results

    def _exec_one(self, host: HostConfig, command: str, timeout: int) -> CommandResult:
        try:
            client = self._pool.get_client(host.alias)
            _, stdout_ch, stderr_ch = client.exec_command(command, timeout=timeout)

            stdout = stdout_ch.read().decode(errors="replace")
            stderr = stderr_ch.read().decode(errors="replace")
            exit_code = stdout_ch.channel.recv_exit_status()

            return CommandResult(
                host=host.alias,
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
            )
        except SSHError as exc:
            return CommandResult(
                host=host.alias,
                command=command,
                stdout="",
                stderr="",
                exit_code=-1,
                error=str(exc),
            )
        except (OSError, RuntimeError, KeyError, ValueError, TypeError) as exc:
            return CommandResult(
                host=host.alias,
                command=command,
                stdout="",
                stderr="",
                exit_code=-1,
                error=f"Unexpected error: {exc}",
            )
