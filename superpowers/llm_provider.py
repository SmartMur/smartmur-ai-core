"""LLM provider abstraction layer.

Supports CLI-based providers (Claude, generic) and SDK-based providers (OpenAI).
Includes a FallbackProvider that tries a primary provider first, then retries
with a fallback on failure.

Usage::

    from superpowers.llm_provider import get_provider, get_default_provider

    # Explicit provider
    p = get_provider("claude")
    if p.available():
        answer = p.invoke("Summarise this log file")

    # Use whatever CHAT_MODEL / JOB_MODEL is configured
    p = get_default_provider()

    # With system prompt (for chat / telegram)
    p = get_default_provider(role="chat")
    answer = p.invoke("Hello", system_prompt="You are a helpful assistant.")
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this provider (e.g. ``"claude"``)."""

    @abstractmethod
    def invoke(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Run *prompt* through the provider and return the response text.

        Parameters
        ----------
        prompt:
            The text prompt to send.
        model:
            Optional model name override.
        system_prompt:
            Optional system prompt for providers that support it.

        Returns
        -------
        str
            The model's response text.

        Raises
        ------
        RuntimeError
            If the provider fails to generate a response.
        FileNotFoundError
            If the provider binary is not found on ``$PATH``.
        """

    @abstractmethod
    def available(self) -> bool:
        """Return ``True`` if the provider is usable."""


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


class ClaudeProvider(LLMProvider):
    """Invokes the ``claude`` CLI (``claude -p <prompt>``)."""

    @property
    def name(self) -> str:
        return "claude"

    def invoke(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        cmd: list[str] = ["claude", "-p", prompt, "--output-format", "text"]
        if model:
            cmd.extend(["--model", model])
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {result.returncode}: {result.stderr.strip()}"
            )
        return result.stdout

    def available(self) -> bool:
        return shutil.which("claude") is not None


class OpenAIProvider(LLMProvider):
    """Invokes OpenAI's API via the ``openai`` Python SDK.

    Reads ``OPENAI_API_KEY`` from environment. Default model is ``gpt-4o``,
    overridable via ``OPENAI_MODEL`` env var or the *model* kwarg.
    """

    def __init__(self, *, api_key: str | None = None, default_model: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._default_model = default_model or os.environ.get("OPENAI_MODEL", "gpt-4o")

    @property
    def name(self) -> str:
        return "openai"

    def invoke(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(
                "openai package is not installed — run: pip install openai>=1.0"
            ) from exc

        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        client = openai.OpenAI(api_key=self._api_key)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model or self._default_model,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    def available(self) -> bool:
        return bool(self._api_key)


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

    def invoke(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
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
                f"{self._binary} exited with code {result.returncode}: {result.stderr.strip()}"
            )
        return result.stdout

    def available(self) -> bool:
        return shutil.which(self._binary) is not None


class FallbackProvider(LLMProvider):
    """Wraps a primary provider with a fallback.

    Tries the primary provider first. On ``RuntimeError``, ``FileNotFoundError``,
    or ``TimeoutError``, retries with the fallback provider.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def name(self) -> str:
        return f"{self._primary.name}+{self._fallback.name}"

    @property
    def primary(self) -> LLMProvider:
        return self._primary

    @property
    def fallback(self) -> LLMProvider:
        return self._fallback

    def invoke(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        try:
            return self._primary.invoke(prompt, model=model, system_prompt=system_prompt)
        except (RuntimeError, FileNotFoundError, TimeoutError, subprocess.TimeoutExpired) as exc:
            logger.warning(
                "Primary provider '%s' failed (%s), falling back to '%s'",
                self._primary.name,
                exc,
                self._fallback.name,
            )
            try:
                from superpowers.audit import log as audit_log

                audit_log(
                    "llm_fallback",
                    detail=f"primary={self._primary.name} error={exc} fallback={self._fallback.name}",
                )
            except (ImportError, OSError, ValueError):
                pass
            return self._fallback.invoke(prompt, model=None, system_prompt=system_prompt)

    def available(self) -> bool:
        return self._primary.available() or self._fallback.available()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Friendly aliases used in CLI/chat contexts.
_ALIASES: dict[str, str] = {
    "chatgpt": "openai",
    "gpt": "openai",
}

# Registry of known provider names -> constructor callables
_PROVIDERS: dict[str, type[LLMProvider] | callable] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


def register_provider(name: str, factory: type[LLMProvider] | callable) -> None:
    """Register a custom provider factory under *name*."""
    _PROVIDERS[normalise_provider_name(name)] = factory


def normalise_provider_name(name: str) -> str:
    """Map aliases to canonical provider names."""
    key = name.strip().lower()
    return _ALIASES.get(key, key)


def get_provider(name: str) -> LLMProvider:
    """Return a provider instance for *name*.

    Known names (e.g. ``"claude"``, ``"openai"``) resolve to built-in classes.
    Unknown names are wrapped automatically with :class:`GenericProvider`.
    """
    canonical = normalise_provider_name(name)
    factory = _PROVIDERS.get(canonical)
    if factory is not None:
        return factory()
    # Fall back to GenericProvider for any unknown CLI tool name
    return GenericProvider(canonical)


def _fallback_enabled() -> bool:
    return os.environ.get("LLM_FALLBACK", "true").lower() not in (
        "false",
        "0",
        "no",
    )


def _openai_fallback() -> OpenAIProvider | None:
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key or not _fallback_enabled():
        return None
    return OpenAIProvider(api_key=openai_key)


def get_provider_with_fallback(name: str) -> LLMProvider:
    """Return provider by name and auto-wrap with OpenAI fallback if configured."""
    canonical = normalise_provider_name(name)
    primary = get_provider(canonical)
    if canonical == "openai":
        return primary

    fallback = _openai_fallback()
    if fallback is None:
        return primary
    return FallbackProvider(primary, fallback)


def get_default_provider(*, role: str = "chat") -> LLMProvider:
    """Return the provider configured for *role*, with optional fallback.

    Parameters
    ----------
    role:
        ``"chat"`` reads ``CHAT_MODEL`` env var (default ``"claude"``).
        ``"job"`` reads ``JOB_MODEL`` env var (default ``"claude"``).

    When ``OPENAI_API_KEY`` is set and ``LLM_FALLBACK`` is not ``"false"``,
    wraps the primary provider with a :class:`FallbackProvider` using OpenAI
    as the fallback. If the primary *is* ``"openai"``, no fallback is added.
    """
    if role == "job":
        model_name = os.environ.get("JOB_MODEL", "claude")
    else:
        model_name = os.environ.get("CHAT_MODEL", "claude")
    return get_provider_with_fallback(model_name)
