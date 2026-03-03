"""LLM provider abstraction layer (Phase F).

Provides a CLI-based interface for invoking language models.  No API SDKs
are used — every provider shells out to a CLI binary.  This keeps the
project local-first and decoupled from any particular vendor's Python client.

Usage::

    from superpowers.llm_provider import get_provider, get_default_provider

    # Explicit provider
    p = get_provider("claude")
    if p.available():
        answer = p.invoke("Summarise this log file")

    # Use whatever CHAT_MODEL / JOB_MODEL is configured
    p = get_default_provider()
"""

from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base class for CLI-based LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this provider (e.g. ``"claude"``)."""

    @abstractmethod
    def invoke(self, prompt: str, *, model: str | None = None) -> str:
        """Run *prompt* through the provider and return the response text.

        Parameters
        ----------
        prompt:
            The text prompt to send.
        model:
            Optional model name override passed to the CLI tool.

        Returns
        -------
        str
            The model's response text (stdout of the CLI command).

        Raises
        ------
        RuntimeError
            If the CLI command exits with a non-zero return code.
        FileNotFoundError
            If the provider binary is not found on ``$PATH``.
        """

    @abstractmethod
    def available(self) -> bool:
        """Return ``True`` if the provider CLI binary is on ``$PATH``."""


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


class ClaudeProvider(LLMProvider):
    """Invokes the ``claude`` CLI (``claude -p <prompt>``)."""

    @property
    def name(self) -> str:
        return "claude"

    def invoke(self, prompt: str, *, model: str | None = None) -> str:
        cmd: list[str] = ["claude", "-p", prompt, "--output-format", "text"]
        if model:
            cmd.extend(["--model", model])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {result.returncode}: "
                f"{result.stderr.strip()}"
            )
        return result.stdout

    def available(self) -> bool:
        return shutil.which("claude") is not None


class GenericProvider(LLMProvider):
    """Wraps any CLI that accepts a prompt argument.

    The *binary* is the executable name and *prompt_flag* is the flag used
    to pass the prompt string (default ``"-p"``).  For example::

        GenericProvider("ollama", prompt_flag="run")

    Would invoke: ``ollama run <prompt>``
    """

    def __init__(self, binary: str, *, prompt_flag: str = "-p") -> None:
        self._binary = binary
        self._prompt_flag = prompt_flag

    @property
    def name(self) -> str:
        return self._binary

    def invoke(self, prompt: str, *, model: str | None = None) -> str:
        cmd: list[str] = [self._binary, self._prompt_flag, prompt]
        if model:
            cmd.extend(["--model", model])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{self._binary} exited with code {result.returncode}: "
                f"{result.stderr.strip()}"
            )
        return result.stdout

    def available(self) -> bool:
        return shutil.which(self._binary) is not None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Registry of known provider names -> constructor callables
_PROVIDERS: dict[str, type[LLMProvider] | callable] = {
    "claude": ClaudeProvider,
}


def register_provider(name: str, factory: type[LLMProvider] | callable) -> None:
    """Register a custom provider factory under *name*."""
    _PROVIDERS[name] = factory


def get_provider(name: str) -> LLMProvider:
    """Return a provider instance for *name*.

    Known names (e.g. ``"claude"``) resolve to built-in classes.
    Unknown names are wrapped automatically with :class:`GenericProvider`.
    """
    factory = _PROVIDERS.get(name)
    if factory is not None:
        return factory()
    # Fall back to GenericProvider for any unknown CLI tool name
    return GenericProvider(name)


def get_default_provider(*, role: str = "chat") -> LLMProvider:
    """Return the provider configured for *role*.

    Parameters
    ----------
    role:
        ``"chat"`` reads ``CHAT_MODEL`` env var (default ``"claude"``).
        ``"job"`` reads ``JOB_MODEL`` env var (default ``"claude"``).
    """
    if role == "job":
        model_name = os.environ.get("JOB_MODEL", "claude")
    else:
        model_name = os.environ.get("CHAT_MODEL", "claude")
    return get_provider(model_name)
