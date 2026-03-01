"""Base types for the SSH fabric."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AuthMethod(str, Enum):
    key = "key"
    password = "password"
    agent = "agent"


class SSHError(Exception):
    """Raised when an SSH operation fails."""


@dataclass
class HostConfig:
    alias: str
    hostname: str
    port: int = 22
    username: str = "root"
    auth: AuthMethod = AuthMethod.key
    key_file: str = ""
    groups: list[str] = field(default_factory=lambda: ["all"])
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class CommandResult:
    host: str
    command: str
    stdout: str
    stderr: str
    exit_code: int
    ok: bool = True
    error: str = ""

    def __post_init__(self):
        self.ok = self.exit_code == 0 and not self.error
