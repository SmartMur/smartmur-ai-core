"""LLM provider abstraction layer.

Supports CLI-based providers (Claude, generic), SDK-based providers (OpenAI),
and HTTP-based providers (Ollama).  Includes a FallbackProvider that tries a
primary provider first, then retries with a fallback on failure, and a
ProviderRegistry for configurable multi-provider fallback chains.

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

    # Multi-provider fallback chain (via LLM_PROVIDERS env var)
    from superpowers.llm_provider import ProviderRegistry
    reg = ProviderRegistry()
    p = reg.get()  # returns first available from the chain
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.request
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


class OllamaProvider(LLMProvider):
    """Invokes Ollama's local HTTP API (``/api/generate``).

    Communicates with the Ollama server via ``urllib.request`` (stdlib only).
    Default base URL is ``http://localhost:11434``, overridable via
    ``OLLAMA_BASE_URL`` env var or the *base_url* constructor argument.
    Default model is ``llama3``, overridable via ``OLLAMA_MODEL`` env var.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: int = 300,
    ) -> None:
        self._base_url = (
            base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self._default_model = default_model or os.environ.get("OLLAMA_MODEL", "llama3")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    def invoke(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        url = f"{self._base_url}/api/generate"
        payload: dict = {
            "model": model or self._default_model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama API request failed: {exc}") from exc
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Ollama API returned HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(f"Ollama API request timed out after {self._timeout}s") from exc

        response_text = body.get("response", "")
        if not response_text and body.get("error"):
            raise RuntimeError(f"Ollama error: {body['error']}")
        return response_text

    def available(self) -> bool:
        """Check if the Ollama server is reachable by hitting ``/api/tags``."""
        url = f"{self._base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5):
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
            return False


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
    "ollama": OllamaProvider,
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


# ---------------------------------------------------------------------------
# ProviderRegistry — configurable multi-provider fallback chain
# ---------------------------------------------------------------------------


class ProviderRegistry:
    """Manages a named set of LLM providers with a configurable fallback chain.

    The fallback order is read from ``LLM_PROVIDERS`` env var (comma-separated
    provider names, e.g. ``"claude,ollama,openai"``).  When no env var is set
    the default chain is ``["claude"]``.

    Usage::

        reg = ProviderRegistry()
        reg.list_providers()        # [("claude", True), ("ollama", False), ...]
        p = reg.get()               # first available provider from the chain
        p = reg.get("ollama")       # explicit provider by name
        reg.set_default("ollama")   # override default at runtime
    """

    def __init__(self, chain: list[str] | None = None) -> None:
        if chain is not None:
            self._chain = [normalise_provider_name(n) for n in chain if n.strip()]
        else:
            raw = os.environ.get("LLM_PROVIDERS", "claude")
            self._chain = [
                normalise_provider_name(n) for n in raw.split(",") if n.strip()
            ]
        self._providers: dict[str, LLMProvider] = {}
        self._default: str | None = None
        # Pre-instantiate known providers
        for name in self._chain:
            self._providers[name] = get_provider(name)

    @property
    def chain(self) -> list[str]:
        """Return the current fallback chain order."""
        return list(self._chain)

    def add(self, name: str, provider: LLMProvider | None = None) -> None:
        """Add a provider to the registry.

        If *provider* is ``None``, instantiate from the global factory.
        """
        canonical = normalise_provider_name(name)
        self._providers[canonical] = provider or get_provider(canonical)
        if canonical not in self._chain:
            self._chain.append(canonical)

    def remove(self, name: str) -> None:
        """Remove a provider from the registry and fallback chain."""
        canonical = normalise_provider_name(name)
        self._providers.pop(canonical, None)
        if canonical in self._chain:
            self._chain.remove(canonical)
        if self._default == canonical:
            self._default = None

    def get(self, name: str | None = None) -> LLMProvider:
        """Return a provider by *name*, or the first available from the chain.

        Parameters
        ----------
        name:
            Explicit provider name.  If ``None``, returns the configured
            default (if set) or walks the fallback chain and returns the
            first provider whose ``available()`` returns ``True``.

        Raises
        ------
        RuntimeError
            If no provider is available.
        KeyError
            If the named provider is not in the registry.
        """
        if name is not None:
            canonical = normalise_provider_name(name)
            if canonical not in self._providers:
                raise KeyError(f"Provider not registered: {canonical}")
            return self._providers[canonical]

        # Default override
        if self._default and self._default in self._providers:
            return self._providers[self._default]

        # Walk the chain, return first available
        for pname in self._chain:
            provider = self._providers.get(pname)
            if provider and provider.available():
                return provider

        # Nothing available — return the first in the chain anyway
        # (caller will get an error on invoke)
        if self._chain and self._chain[0] in self._providers:
            return self._providers[self._chain[0]]

        raise RuntimeError("No LLM providers are registered")

    def set_default(self, name: str) -> None:
        """Override the default provider (bypasses availability check)."""
        canonical = normalise_provider_name(name)
        if canonical not in self._providers:
            raise KeyError(f"Provider not registered: {canonical}")
        self._default = canonical

    def clear_default(self) -> None:
        """Clear the default override — resume using the fallback chain."""
        self._default = None

    def list_providers(self) -> list[tuple[str, bool]]:
        """Return ``(name, available)`` for every provider in chain order.

        Providers registered but not in the chain are appended at the end.
        """
        seen: set[str] = set()
        result: list[tuple[str, bool]] = []

        for pname in self._chain:
            provider = self._providers.get(pname)
            avail = provider.available() if provider else False
            result.append((pname, avail))
            seen.add(pname)

        for pname, provider in self._providers.items():
            if pname not in seen:
                result.append((pname, provider.available()))

        return result
