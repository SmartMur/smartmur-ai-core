"""Tests for multi-LLM provider support.

Covers:
- OllamaProvider (HTTP-based, mocked urllib)
- ProviderRegistry (chain, add/remove, get, set-default, list)
- Fallback chain behavior
- CLI commands (claw llm list/test/set-default)
- Config loading from env vars
- Error handling (timeout, bad response, provider not found)
"""

from __future__ import annotations

import json
import os
import subprocess
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from superpowers.llm_provider import (
    ClaudeProvider,
    FallbackProvider,
    GenericProvider,
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderRegistry,
    get_default_provider,
    get_provider,
    get_provider_with_fallback,
    normalise_provider_name,
    register_provider,
)


# ======================================================================
# OllamaProvider
# ======================================================================


class TestOllamaProvider:
    """OllamaProvider calls Ollama's HTTP API."""

    def test_name(self):
        p = OllamaProvider()
        assert p.name == "ollama"

    def test_default_base_url(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OLLAMA_BASE_URL", None)
            p = OllamaProvider()
        assert p._base_url == "http://localhost:11434"

    def test_base_url_from_env(self):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://myhost:8080"}):
            p = OllamaProvider()
        assert p._base_url == "http://myhost:8080"

    def test_base_url_strips_trailing_slash(self):
        p = OllamaProvider(base_url="http://localhost:11434/")
        assert p._base_url == "http://localhost:11434"

    def test_base_url_from_constructor(self):
        p = OllamaProvider(base_url="http://custom:9999")
        assert p._base_url == "http://custom:9999"

    def test_default_model(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OLLAMA_MODEL", None)
            p = OllamaProvider()
        assert p._default_model == "llama3"

    def test_model_from_env(self):
        with patch.dict(os.environ, {"OLLAMA_MODEL": "mistral"}):
            p = OllamaProvider()
        assert p._default_model == "mistral"

    def test_model_from_constructor(self):
        p = OllamaProvider(default_model="codellama")
        assert p._default_model == "codellama"

    def test_invoke_success(self):
        """invoke() sends POST to /api/generate and returns the response text."""
        response_body = json.dumps({"response": "Hello from Ollama!"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            p = OllamaProvider(base_url="http://localhost:11434", default_model="llama3")
            result = p.invoke("Say hello")

        assert result == "Hello from Ollama!"
        # Verify the request
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.full_url == "http://localhost:11434/api/generate"
        assert req.method == "POST"
        body = json.loads(req.data)
        assert body["model"] == "llama3"
        assert body["prompt"] == "Say hello"
        assert body["stream"] is False

    def test_invoke_with_model_override(self):
        """Model kwarg overrides the default model."""
        response_body = json.dumps({"response": "OK"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            p = OllamaProvider(default_model="llama3")
            p.invoke("test", model="mistral")

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        assert body["model"] == "mistral"

    def test_invoke_with_system_prompt(self):
        """System prompt is passed in the payload."""
        response_body = json.dumps({"response": "OK"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            p = OllamaProvider()
            p.invoke("test", system_prompt="Be helpful")

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        assert body["system"] == "Be helpful"

    def test_invoke_no_system_prompt_omitted(self):
        """When no system prompt, 'system' key is not in payload."""
        response_body = json.dumps({"response": "OK"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            p = OllamaProvider()
            p.invoke("test")

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        assert "system" not in body

    def test_invoke_url_error(self):
        """URLError raises RuntimeError."""
        import urllib.error

        with patch(
            "superpowers.llm_provider.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            p = OllamaProvider()
            with pytest.raises(RuntimeError, match="Ollama API request failed"):
                p.invoke("test")

    def test_invoke_ollama_error_field(self):
        """When response has an error field and no response, raises RuntimeError."""
        response_body = json.dumps({"error": "model not found"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp):
            p = OllamaProvider()
            with pytest.raises(RuntimeError, match="model not found"):
                p.invoke("test")

    def test_invoke_empty_response_no_error(self):
        """Empty response without error field returns empty string."""
        response_body = json.dumps({"response": ""}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp):
            p = OllamaProvider()
            result = p.invoke("test")
        assert result == ""

    def test_available_server_reachable(self):
        """available() returns True when /api/tags responds."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp):
            p = OllamaProvider()
            assert p.available() is True

    def test_available_server_unreachable(self):
        """available() returns False when server is unreachable."""
        import urllib.error

        with patch(
            "superpowers.llm_provider.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            p = OllamaProvider()
            assert p.available() is False

    def test_available_server_timeout(self):
        """available() returns False on timeout."""
        with patch(
            "superpowers.llm_provider.urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            p = OllamaProvider()
            assert p.available() is False

    def test_custom_timeout(self):
        p = OllamaProvider(timeout=60)
        assert p._timeout == 60


# ======================================================================
# ProviderRegistry
# ======================================================================


class TestProviderRegistry:
    """ProviderRegistry manages providers with configurable fallback chain."""

    def test_default_chain_from_env(self):
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude,ollama,openai"}):
            reg = ProviderRegistry()
        assert reg.chain == ["claude", "ollama", "openai"]

    def test_default_chain_no_env(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLM_PROVIDERS", None)
            reg = ProviderRegistry()
        assert reg.chain == ["claude"]

    def test_chain_from_constructor(self):
        reg = ProviderRegistry(chain=["ollama", "claude"])
        assert reg.chain == ["ollama", "claude"]

    def test_chain_normalises_names(self):
        reg = ProviderRegistry(chain=["ChatGPT", "Claude"])
        assert reg.chain == ["openai", "claude"]

    def test_chain_filters_empty(self):
        reg = ProviderRegistry(chain=["claude", "", "ollama"])
        assert reg.chain == ["claude", "ollama"]

    def test_list_providers(self):
        reg = ProviderRegistry(chain=["claude", "ollama"])
        # Mock availability
        with patch.object(ClaudeProvider, "available", return_value=True), \
             patch.object(OllamaProvider, "available", return_value=False):
            result = reg.list_providers()
        assert result == [("claude", True), ("ollama", False)]

    def test_get_by_name(self):
        reg = ProviderRegistry(chain=["claude", "ollama"])
        p = reg.get("claude")
        assert isinstance(p, ClaudeProvider)

    def test_get_by_name_normalised(self):
        reg = ProviderRegistry(chain=["openai"])
        p = reg.get("chatgpt")
        assert isinstance(p, OpenAIProvider)

    def test_get_unknown_raises_key_error(self):
        reg = ProviderRegistry(chain=["claude"])
        with pytest.raises(KeyError, match="not registered"):
            reg.get("nonexistent")

    def test_get_first_available(self):
        """get() with no name returns first available from chain."""
        reg = ProviderRegistry(chain=["claude", "ollama"])
        with patch.object(ClaudeProvider, "available", return_value=False), \
             patch.object(OllamaProvider, "available", return_value=True):
            p = reg.get()
        assert isinstance(p, OllamaProvider)

    def test_get_all_unavailable_returns_first(self):
        """When all providers are unavailable, returns first in chain."""
        reg = ProviderRegistry(chain=["claude", "ollama"])
        with patch.object(ClaudeProvider, "available", return_value=False), \
             patch.object(OllamaProvider, "available", return_value=False):
            p = reg.get()
        assert isinstance(p, ClaudeProvider)

    def test_get_empty_registry_raises(self):
        reg = ProviderRegistry(chain=[])
        # Remove any providers that might have been added
        reg._providers.clear()
        reg._chain.clear()
        with pytest.raises(RuntimeError, match="No LLM providers"):
            reg.get()

    def test_set_default(self):
        reg = ProviderRegistry(chain=["claude", "ollama"])
        reg.set_default("ollama")
        # Now get() should return ollama even if claude is available
        p = reg.get()
        assert isinstance(p, OllamaProvider)

    def test_set_default_unknown_raises(self):
        reg = ProviderRegistry(chain=["claude"])
        with pytest.raises(KeyError, match="not registered"):
            reg.set_default("nonexistent")

    def test_clear_default(self):
        reg = ProviderRegistry(chain=["claude", "ollama"])
        reg.set_default("ollama")
        reg.clear_default()
        # Now should fall back to chain order
        with patch.object(ClaudeProvider, "available", return_value=True):
            p = reg.get()
        assert isinstance(p, ClaudeProvider)

    def test_add_provider(self):
        reg = ProviderRegistry(chain=["claude"])
        assert "ollama" not in reg.chain
        reg.add("ollama")
        assert "ollama" in reg.chain
        p = reg.get("ollama")
        assert isinstance(p, OllamaProvider)

    def test_add_custom_provider(self):
        reg = ProviderRegistry(chain=["claude"])
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "custom"
        reg.add("custom", mock_provider)
        assert "custom" in reg.chain
        assert reg.get("custom") is mock_provider

    def test_add_duplicate_no_double(self):
        """Adding a provider already in chain doesn't duplicate it."""
        reg = ProviderRegistry(chain=["claude"])
        reg.add("claude")
        assert reg.chain.count("claude") == 1

    def test_remove_provider(self):
        reg = ProviderRegistry(chain=["claude", "ollama"])
        reg.remove("ollama")
        assert "ollama" not in reg.chain
        with pytest.raises(KeyError):
            reg.get("ollama")

    def test_remove_default_clears_it(self):
        reg = ProviderRegistry(chain=["claude", "ollama"])
        reg.set_default("ollama")
        reg.remove("ollama")
        assert reg._default is None

    def test_remove_nonexistent_is_noop(self):
        reg = ProviderRegistry(chain=["claude"])
        reg.remove("nonexistent")  # should not raise


# ======================================================================
# OllamaProvider in global registry
# ======================================================================


class TestOllamaInGlobalRegistry:
    """Ollama is registered in the global _PROVIDERS dict."""

    def test_get_provider_ollama(self):
        p = get_provider("ollama")
        assert isinstance(p, OllamaProvider)

    def test_normalise_ollama(self):
        assert normalise_provider_name("ollama") == "ollama"
        assert normalise_provider_name("Ollama") == "ollama"
        assert normalise_provider_name("  OLLAMA  ") == "ollama"


# ======================================================================
# Fallback chain behavior
# ======================================================================


class TestFallbackChain:
    """Test fallback behavior with multiple providers."""

    def test_claude_falls_back_to_ollama(self):
        """When Claude fails, falls back to Ollama via FallbackProvider."""
        claude = ClaudeProvider()
        ollama = OllamaProvider()
        fb = FallbackProvider(claude, ollama)

        response_body = json.dumps({"response": "Ollama fallback"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("subprocess.run", side_effect=FileNotFoundError("claude not found")), \
             patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp):
            result = fb.invoke("test")

        assert result == "Ollama fallback"

    def test_fallback_name(self):
        fb = FallbackProvider(ClaudeProvider(), OllamaProvider())
        assert fb.name == "claude+ollama"

    def test_fallback_available_primary(self):
        fb = FallbackProvider(ClaudeProvider(), OllamaProvider())
        with patch.object(ClaudeProvider, "available", return_value=True):
            assert fb.available() is True

    def test_fallback_available_fallback_only(self):
        fb = FallbackProvider(ClaudeProvider(), OllamaProvider())
        with patch.object(ClaudeProvider, "available", return_value=False), \
             patch.object(OllamaProvider, "available", return_value=True):
            assert fb.available() is True

    def test_registry_chain_fallback(self):
        """ProviderRegistry walks the chain to find first available."""
        reg = ProviderRegistry(chain=["claude", "ollama", "openai"])
        with patch.object(ClaudeProvider, "available", return_value=False), \
             patch.object(OllamaProvider, "available", return_value=True):
            p = reg.get()
        assert isinstance(p, OllamaProvider)


# ======================================================================
# Config loading
# ======================================================================


class TestConfigLoading:
    """Test provider config from environment variables."""

    def test_llm_providers_env(self):
        with patch.dict(os.environ, {"LLM_PROVIDERS": "ollama,openai,claude"}):
            reg = ProviderRegistry()
        assert reg.chain == ["ollama", "openai", "claude"]

    def test_ollama_base_url_env(self):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://gpu-server:11434"}):
            p = OllamaProvider()
        assert p._base_url == "http://gpu-server:11434"

    def test_ollama_model_env(self):
        with patch.dict(os.environ, {"OLLAMA_MODEL": "phi3"}):
            p = OllamaProvider()
        assert p._default_model == "phi3"

    def test_settings_loads_llm_fields(self):
        """Settings.load() picks up existing LLM config fields."""
        from pathlib import Path
        from superpowers.config import Settings

        with patch.dict(os.environ, {"CHAT_MODEL": "ollama", "JOB_MODEL": "claude"}, clear=True):
            s = Settings.load(dotenv_path=Path("/nonexistent/.env"))
        assert s.chat_model == "ollama"
        assert s.job_model == "claude"


# ======================================================================
# CLI commands
# ======================================================================


class TestCLILlmList:
    """claw llm list — show providers and status."""

    def test_list_shows_providers(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude,ollama"}), \
             patch.object(ClaudeProvider, "available", return_value=True), \
             patch.object(OllamaProvider, "available", return_value=False):
            result = runner.invoke(llm_group, ["list"])

        assert result.exit_code == 0
        assert "claude" in result.output
        assert "ollama" in result.output

    def test_list_empty(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        # Even with just one provider, it should show something
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude"}), \
             patch.object(ClaudeProvider, "available", return_value=False):
            result = runner.invoke(llm_group, ["list"])
        assert result.exit_code == 0


class TestCLILlmTest:
    """claw llm test — send test prompt."""

    def test_test_success(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude"}), \
             patch.object(ClaudeProvider, "available", return_value=True), \
             patch.object(ClaudeProvider, "invoke", return_value="Hello!"):
            result = runner.invoke(llm_group, ["test", "claude"])

        assert result.exit_code == 0
        assert "Hello!" in result.output

    def test_test_failure(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude"}), \
             patch.object(ClaudeProvider, "available", return_value=True), \
             patch.object(ClaudeProvider, "invoke", side_effect=RuntimeError("CLI not found")):
            result = runner.invoke(llm_group, ["test", "claude"])

        assert result.exit_code == 1
        assert "Failed" in result.output

    def test_test_unknown_provider(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude"}):
            result = runner.invoke(llm_group, ["test", "nonexistent"])

        assert result.exit_code == 1

    def test_test_default_provider(self):
        """Running 'claw llm test' with no arg uses first available."""
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude"}), \
             patch.object(ClaudeProvider, "available", return_value=True), \
             patch.object(ClaudeProvider, "invoke", return_value="Hi"):
            result = runner.invoke(llm_group, ["test"])

        assert result.exit_code == 0

    def test_test_custom_prompt(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude"}), \
             patch.object(ClaudeProvider, "available", return_value=True), \
             patch.object(ClaudeProvider, "invoke", return_value="42") as mock_invoke:
            result = runner.invoke(llm_group, ["test", "claude", "-p", "What is 6*7?"])

        assert result.exit_code == 0
        mock_invoke.assert_called_once_with("What is 6*7?")


class TestCLILlmSetDefault:
    """claw llm set-default — set default provider."""

    def test_set_default_success(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude,ollama"}):
            result = runner.invoke(llm_group, ["set-default", "ollama"])

        assert result.exit_code == 0
        assert "ollama" in result.output

    def test_set_default_unknown(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude"}):
            result = runner.invoke(llm_group, ["set-default", "nonexistent"])

        assert result.exit_code == 1

    def test_set_default_updates_env(self):
        from superpowers.cli_llm import llm_group

        runner = CliRunner()
        with patch.dict(os.environ, {"LLM_PROVIDERS": "claude,ollama"}):
            result = runner.invoke(llm_group, ["set-default", "ollama"])
            assert result.exit_code == 0
            # Check that env was updated with ollama first
            assert os.environ["LLM_PROVIDERS"].startswith("ollama")


# ======================================================================
# Error handling
# ======================================================================


class TestErrorHandling:
    """Edge cases and error handling."""

    def test_ollama_timeout_in_invoke(self):
        """Timeout during invoke raises RuntimeError."""
        with patch(
            "superpowers.llm_provider.urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            p = OllamaProvider()
            with pytest.raises(RuntimeError, match="timed out"):
                p.invoke("test")

    def test_ollama_bad_json_response(self):
        """Non-JSON response raises an error."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("superpowers.llm_provider.urllib.request.urlopen", return_value=mock_resp):
            p = OllamaProvider()
            with pytest.raises((json.JSONDecodeError, RuntimeError)):
                p.invoke("test")

    def test_registry_get_preserves_provider_instances(self):
        """Registry reuses the same provider instances."""
        reg = ProviderRegistry(chain=["claude"])
        p1 = reg.get("claude")
        p2 = reg.get("claude")
        assert p1 is p2

    def test_provider_with_fallback_ollama(self):
        """get_provider_with_fallback works for ollama too."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "LLM_FALLBACK": "true"}):
            p = get_provider_with_fallback("ollama")
        assert isinstance(p, FallbackProvider)
        assert isinstance(p.primary, OllamaProvider)
        assert isinstance(p.fallback, OpenAIProvider)
