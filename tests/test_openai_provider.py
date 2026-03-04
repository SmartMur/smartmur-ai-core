"""Tests for OpenAI provider, FallbackProvider, and factory fallback behavior."""

from __future__ import annotations

import os
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from superpowers.llm_provider import (
    ClaudeProvider,
    FallbackProvider,
    OpenAIProvider,
    get_default_provider,
    get_provider,
)


def _make_openai_mock():
    """Create a mock openai module with OpenAI client."""
    mock_module = ModuleType("openai")
    mock_client_cls = MagicMock()
    mock_module.OpenAI = mock_client_cls
    return mock_module, mock_client_cls


# ======================================================================
# OpenAIProvider
# ======================================================================


class TestOpenAIProvider:
    """OpenAIProvider invokes the OpenAI Python SDK."""

    def test_name(self):
        p = OpenAIProvider(api_key="sk-test")
        assert p.name == "openai"

    def test_available_with_key(self):
        p = OpenAIProvider(api_key="sk-test")
        assert p.available() is True

    def test_not_available_without_key(self):
        p = OpenAIProvider(api_key="")
        assert p.available() is False

    def test_available_from_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env"}):
            p = OpenAIProvider()
            assert p.available() is True

    def test_default_model(self):
        p = OpenAIProvider(api_key="sk-test")
        assert p._default_model == "gpt-4o"

    def test_model_from_env(self):
        with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4o-mini"}):
            p = OpenAIProvider(api_key="sk-test")
            assert p._default_model == "gpt-4o-mini"

    def test_model_from_constructor(self):
        p = OpenAIProvider(api_key="sk-test", default_model="gpt-3.5-turbo")
        assert p._default_model == "gpt-3.5-turbo"

    def test_invoke_success(self):
        """invoke() calls openai.OpenAI().chat.completions.create()."""
        mock_module, mock_client_cls = _make_openai_mock()
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from OpenAI"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )
        mock_client_cls.return_value = mock_client

        with patch.dict(sys.modules, {"openai": mock_module}):
            p = OpenAIProvider(api_key="sk-test")
            result = p.invoke("Say hello")

        assert result == "Hello from OpenAI"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    def test_invoke_with_system_prompt(self):
        """System prompt is prepended as a system message."""
        mock_module, mock_client_cls = _make_openai_mock()
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "response"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )
        mock_client_cls.return_value = mock_client

        with patch.dict(sys.modules, {"openai": mock_module}):
            p = OpenAIProvider(api_key="sk-test")
            p.invoke("Hello", system_prompt="You are a butler.")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are a butler."}
        assert messages[1] == {"role": "user", "content": "Hello"}

    def test_invoke_with_model_override(self):
        """Model override takes precedence over default."""
        mock_module, mock_client_cls = _make_openai_mock()
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )
        mock_client_cls.return_value = mock_client

        with patch.dict(sys.modules, {"openai": mock_module}):
            p = OpenAIProvider(api_key="sk-test")
            p.invoke("test", model="gpt-4o-mini")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"

    def test_invoke_raises_without_key(self):
        """invoke() raises RuntimeError when API key is empty."""
        mock_module, _ = _make_openai_mock()
        with patch.dict(sys.modules, {"openai": mock_module}):
            p = OpenAIProvider(api_key="")
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
                p.invoke("test")

    def test_invoke_raises_when_sdk_missing(self):
        """invoke() raises RuntimeError when openai package is not installed."""
        p = OpenAIProvider(api_key="sk-test")
        with patch.dict(sys.modules, {"openai": None}):
            with pytest.raises(RuntimeError, match="openai package is not installed"):
                p.invoke("test")


# ======================================================================
# FallbackProvider
# ======================================================================


class TestFallbackProvider:
    """FallbackProvider tries primary, falls back on failure."""

    def _make_provider(self, name: str, response: str = "ok", fail: bool = False):
        """Create a mock LLMProvider."""
        p = MagicMock()
        p.name = name
        if fail:
            p.invoke.side_effect = RuntimeError(f"{name} failed")
        else:
            p.invoke.return_value = response
        p.available.return_value = not fail
        return p

    def test_primary_succeeds(self):
        """When primary works, fallback is not called."""
        primary = self._make_provider("primary", "primary response")
        fallback = self._make_provider("fallback", "fallback response")
        fb = FallbackProvider(primary, fallback)

        result = fb.invoke("test")
        assert result == "primary response"
        primary.invoke.assert_called_once()
        fallback.invoke.assert_not_called()

    def test_primary_fails_fallback_succeeds(self):
        """When primary fails, fallback is used."""
        primary = self._make_provider("primary", fail=True)
        fallback = self._make_provider("fallback", "fallback response")
        fb = FallbackProvider(primary, fallback)

        result = fb.invoke("test")
        assert result == "fallback response"
        primary.invoke.assert_called_once()
        fallback.invoke.assert_called_once()

    def test_both_fail_raises(self):
        """When both fail, the fallback's exception propagates."""
        primary = self._make_provider("primary", fail=True)
        fallback = self._make_provider("fallback", fail=True)
        fb = FallbackProvider(primary, fallback)

        with pytest.raises(RuntimeError, match="fallback failed"):
            fb.invoke("test")

    def test_file_not_found_triggers_fallback(self):
        """FileNotFoundError on primary triggers fallback."""
        primary = MagicMock()
        primary.name = "primary"
        primary.invoke.side_effect = FileNotFoundError("claude not found")
        fallback = self._make_provider("fallback", "from fallback")
        fb = FallbackProvider(primary, fallback)

        result = fb.invoke("test")
        assert result == "from fallback"

    def test_timeout_triggers_fallback(self):
        """TimeoutError on primary triggers fallback."""
        primary = MagicMock()
        primary.name = "primary"
        primary.invoke.side_effect = TimeoutError("timed out")
        fallback = self._make_provider("fallback", "from fallback")
        fb = FallbackProvider(primary, fallback)

        result = fb.invoke("test")
        assert result == "from fallback"

    def test_name(self):
        primary = self._make_provider("claude")
        fallback = self._make_provider("openai")
        fb = FallbackProvider(primary, fallback)
        assert fb.name == "claude+openai"

    def test_available_primary_only(self):
        primary = self._make_provider("primary")
        primary.available.return_value = True
        fallback = self._make_provider("fallback")
        fallback.available.return_value = False
        fb = FallbackProvider(primary, fallback)
        assert fb.available() is True

    def test_available_fallback_only(self):
        primary = self._make_provider("primary")
        primary.available.return_value = False
        fallback = self._make_provider("fallback")
        fallback.available.return_value = True
        fb = FallbackProvider(primary, fallback)
        assert fb.available() is True

    def test_available_neither(self):
        primary = self._make_provider("primary")
        primary.available.return_value = False
        fallback = self._make_provider("fallback")
        fallback.available.return_value = False
        fb = FallbackProvider(primary, fallback)
        assert fb.available() is False

    def test_system_prompt_forwarded(self):
        """System prompt is forwarded to both primary and fallback."""
        primary = self._make_provider("primary", fail=True)
        fallback = self._make_provider("fallback", "ok")
        fb = FallbackProvider(primary, fallback)

        fb.invoke("test", system_prompt="Be helpful")
        # Primary called with system_prompt
        primary.invoke.assert_called_once_with(
            "test", model=None, system_prompt="Be helpful"
        )
        # Fallback called with system_prompt (model=None since it's a different provider)
        fallback.invoke.assert_called_once_with(
            "test", model=None, system_prompt="Be helpful"
        )

    def test_properties(self):
        primary = self._make_provider("claude")
        fallback = self._make_provider("openai")
        fb = FallbackProvider(primary, fallback)
        assert fb.primary is primary
        assert fb.fallback is fallback


# ======================================================================
# Factory: get_default_provider with fallback
# ======================================================================


class TestFactoryFallback:
    """get_default_provider() returns FallbackProvider when OpenAI key is set."""

    def test_no_openai_key_returns_claude(self):
        """Without OPENAI_API_KEY, factory returns plain ClaudeProvider."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("CHAT_MODEL", None)
            p = get_default_provider(role="chat")
        assert isinstance(p, ClaudeProvider)

    def test_with_openai_key_returns_fallback(self):
        """With OPENAI_API_KEY, factory returns FallbackProvider."""
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test", "LLM_FALLBACK": "true"},
            clear=False,
        ):
            os.environ.pop("CHAT_MODEL", None)
            p = get_default_provider(role="chat")
        assert isinstance(p, FallbackProvider)
        assert isinstance(p.primary, ClaudeProvider)
        assert isinstance(p.fallback, OpenAIProvider)

    def test_fallback_disabled(self):
        """With LLM_FALLBACK=false, factory returns plain provider even with key."""
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test", "LLM_FALLBACK": "false"},
            clear=False,
        ):
            os.environ.pop("CHAT_MODEL", None)
            p = get_default_provider(role="chat")
        assert isinstance(p, ClaudeProvider)
        assert not isinstance(p, FallbackProvider)

    def test_openai_as_primary_no_fallback(self):
        """When CHAT_MODEL=openai, return OpenAIProvider directly (no fallback)."""
        with patch.dict(
            os.environ,
            {"CHAT_MODEL": "openai", "OPENAI_API_KEY": "sk-test"},
            clear=False,
        ):
            p = get_default_provider(role="chat")
        assert isinstance(p, OpenAIProvider)
        assert not isinstance(p, FallbackProvider)

    def test_job_role_with_fallback(self):
        """Job role also gets fallback when configured."""
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test", "LLM_FALLBACK": "true"},
            clear=False,
        ):
            os.environ.pop("JOB_MODEL", None)
            p = get_default_provider(role="job")
        assert isinstance(p, FallbackProvider)

    def test_get_provider_openai(self):
        """get_provider('openai') returns OpenAIProvider."""
        p = get_provider("openai")
        assert isinstance(p, OpenAIProvider)
