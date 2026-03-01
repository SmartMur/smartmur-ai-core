"""SSH command fabric — remote host management and execution."""

from superpowers.ssh_fabric.base import AuthMethod, CommandResult, HostConfig, SSHError
from superpowers.ssh_fabric.executor import SSHExecutor
from superpowers.ssh_fabric.hosts import HostRegistry
from superpowers.ssh_fabric.pool import ConnectionPool

__all__ = [
    "AuthMethod",
    "CommandResult",
    "ConnectionPool",
    "HostConfig",
    "HostRegistry",
    "SSHError",
    "SSHExecutor",
]
