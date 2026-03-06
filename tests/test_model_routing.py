"""Tests for Phase F — Model Split & Overrides.

Covers:
- F1: CHAT_MODEL / JOB_MODEL config loading
- F2: Per-job llm_model override in cron engine
- F3: LLMProvider interface, ClaudeProvider, GenericProvider, factory
- F4: Integration (env propagation through job execution)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from superpowers.config import Settings
from superpowers.cron_engine import CronEngine, Job, JobType
from superpowers.llm_provider import (
    ClaudeProvider,
    GenericProvider,
    LLMProvider,
    OllamaProvider,
    get_default_provider,
    get_provider,
    register_provider,
)

# ======================================================================
# F1: Config loading — CHAT_MODEL / JOB_MODEL
# ======================================================================


class TestConfigModelFields:
    """CHAT_MODEL and JOB_MODEL are loaded from env / .env."""

    def test_defaults(self):
        """Without env vars, both default to 'claude'."""
        with patch.dict(os.environ, {}, clear=True):
            # Bypass .env loading by supplying a nonexistent path
            s = Settings.load(dotenv_path=Path("/nonexistent/.env"))
        assert s.chat_model == "claude"
        assert s.job_model == "claude"

    def test_custom_values_from_env(self):
        """Env vars override defaults."""
        with patch.dict(
            os.environ,
            {"CHAT_MODEL": "ollama", "JOB_MODEL": "llama-cli"},
            clear=True,
        ):
            s = Settings.load(dotenv_path=Path("/nonexistent/.env"))
        assert s.chat_model == "ollama"
        assert s.job_model == "llama-cli"

    def test_from_dotenv_file(self, tmp_path):
        """Settings can be read from a .env file."""
        dotenv = tmp_path / ".env"
        dotenv.write_text("CHAT_MODEL=gpt-cli\nJOB_MODEL=local-llm\n")
        with patch.dict(os.environ, {}, clear=True):
            s = Settings.load(dotenv_path=dotenv)
        assert s.chat_model == "gpt-cli"
        assert s.job_model == "local-llm"

    def test_env_overrides_dotenv(self, tmp_path):
        """Explicit env vars take precedence over .env file values."""
        dotenv = tmp_path / ".env"
        dotenv.write_text("CHAT_MODEL=from-file\n")
        with patch.dict(os.environ, {"CHAT_MODEL": "from-env"}, clear=True):
            s = Settings.load(dotenv_path=dotenv)
        assert s.chat_model == "from-env"


# ======================================================================
# F2: Per-job model override in cron engine
# ======================================================================


class TestJobLlmModelField:
    """Job dataclass supports the llm_model field."""

    def test_default_empty(self):
        job = Job(
            id="j1",
            name="test",
            schedule="every 1h",
            job_type=JobType.shell,
            command="echo hi",
        )
        assert job.llm_model == ""

    def test_explicit_model(self):
        job = Job(
            id="j2",
            name="test",
            schedule="every 1h",
            job_type=JobType.shell,
            command="echo hi",
            llm_model="llama3",
        )
        assert job.llm_model == "llama3"

    def test_roundtrip_dict(self):
        job = Job(
            id="j3",
            name="custom-model",
            schedule="every 2h",
            job_type=JobType.claude,
            command="summarize",
            llm_model="gpt-4o",
        )
        d = job.to_dict()
        assert d["llm_model"] == "gpt-4o"
        restored = Job.from_dict(d)
        assert restored.llm_model == "gpt-4o"

    def test_json_persistence(self, tmp_path):
        """llm_model survives save/reload through jobs.json."""
        jobs_file = tmp_path / "cron" / "jobs.json"
        e1 = CronEngine(jobs_file=jobs_file, data_dir=tmp_path / "cron")
        e1.start()
        j = e1.add_job(
            "with-model",
            "every 1h",
            "shell",
            "echo test",
            llm_model="custom-model",
        )
        e1.stop()

        # Reload
        e2 = CronEngine(jobs_file=jobs_file, data_dir=tmp_path / "cron")
        reloaded = e2.get_job(j.id)
        assert reloaded.llm_model == "custom-model"
        e2.stop()

    def test_json_schema_includes_field(self, tmp_path):
        """The raw JSON on disk includes the llm_model key."""
        jobs_file = tmp_path / "cron" / "jobs.json"
        e = CronEngine(jobs_file=jobs_file, data_dir=tmp_path / "cron")
        e.start()
        e.add_job("schema-check", "every 1h", "shell", "true", llm_model="mymodel")
        e.stop()

        raw = json.loads(jobs_file.read_text())
        assert len(raw) == 1
        assert raw[0]["llm_model"] == "mymodel"


class TestJobEnvPropagation:
    """_job_env correctly sets LLM_MODEL for subprocesses."""

    @pytest.fixture
    def engine(self, tmp_path):
        e = CronEngine(
            jobs_file=tmp_path / "cron" / "jobs.json",
            data_dir=tmp_path / "cron",
        )
        e.start()
        yield e
        e.stop()

    def test_per_job_override_in_env(self, engine):
        """When llm_model is set, LLM_MODEL env reflects it."""
        job = Job(
            id="e1",
            name="test",
            schedule="every 1h",
            job_type=JobType.shell,
            command="echo hi",
            llm_model="local-llm",
        )
        env = engine._job_env(job)
        assert env["LLM_MODEL"] == "local-llm"

    def test_fallback_to_job_model_env(self, engine):
        """Without per-job override, falls back to JOB_MODEL env var."""
        job = Job(
            id="e2",
            name="test",
            schedule="every 1h",
            job_type=JobType.shell,
            command="echo hi",
        )
        with patch.dict(os.environ, {"JOB_MODEL": "ollama"}):
            env = engine._job_env(job)
        assert env["LLM_MODEL"] == "ollama"

    def test_fallback_to_claude_default(self, engine):
        """Without any config, defaults to 'claude'."""
        job = Job(
            id="e3",
            name="test",
            schedule="every 1h",
            job_type=JobType.shell,
            command="echo hi",
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JOB_MODEL", None)
            env = engine._job_env(job)
        assert env["LLM_MODEL"] == "claude"

    def test_shell_job_receives_llm_model(self, engine, tmp_path):
        """Shell job subprocess receives LLM_MODEL in its environment."""
        job = engine.add_job(
            "env-check",
            "every 1h",
            "shell",
            "env",
            llm_model="test-model",
        )
        engine._execute_job(job.id)
        updated = engine.get_job(job.id)
        assert updated.last_status == "ok"
        log = Path(updated.last_output_file).read_text()
        assert "LLM_MODEL=test-model" in log


# ======================================================================
# F3: LLM Provider interface & factory
# ======================================================================


class TestLLMProviderInterface:
    """LLMProvider ABC enforces the interface contract."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_concrete_must_implement_all(self):
        """A subclass missing methods cannot be instantiated."""

        class Incomplete(LLMProvider):
            @property
            def name(self):
                return "incomplete"

        with pytest.raises(TypeError):
            Incomplete()


class TestClaudeProvider:
    """ClaudeProvider invokes 'claude -p' via subprocess."""

    def test_name(self):
        p = ClaudeProvider()
        assert p.name == "claude"

    @patch("superpowers.llm_provider.subprocess.run")
    def test_invoke_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Hello from Claude\n",
            stderr="",
        )
        p = ClaudeProvider()
        result = p.invoke("Say hello")
        assert result == "Hello from Claude\n"
        mock_run.assert_called_once()
        args = mock_run.call_args
        cmd = args[0][0]
        assert cmd[:2] == ["claude", "-p"]
        assert "Say hello" in cmd

    @patch("superpowers.llm_provider.subprocess.run")
    def test_invoke_with_model_override(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="response",
            stderr="",
        )
        p = ClaudeProvider()
        p.invoke("test", model="claude-3-sonnet")
        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "claude-3-sonnet" in cmd

    @patch("superpowers.llm_provider.subprocess.run")
    def test_invoke_with_system_prompt(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="response",
            stderr="",
        )
        p = ClaudeProvider()
        p.invoke("test", system_prompt="You are helpful.")
        cmd = mock_run.call_args[0][0]
        assert "--system-prompt" in cmd
        assert "You are helpful." in cmd

    @patch("superpowers.llm_provider.subprocess.run")
    def test_invoke_failure_raises(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error: auth failed",
        )
        p = ClaudeProvider()
        with pytest.raises(RuntimeError, match="exited with code 1"):
            p.invoke("test prompt")

    @patch("superpowers.llm_provider.shutil.which", return_value="/usr/bin/claude")
    def test_available_true(self, mock_which):
        assert ClaudeProvider().available() is True
        mock_which.assert_called_with("claude")

    @patch("superpowers.llm_provider.shutil.which", return_value=None)
    def test_available_false(self, mock_which):
        assert ClaudeProvider().available() is False


class TestGenericProvider:
    """GenericProvider wraps arbitrary CLI tools."""

    def test_name_is_binary(self):
        p = GenericProvider("ollama")
        assert p.name == "ollama"

    @patch("superpowers.llm_provider.subprocess.run")
    def test_invoke_default_flag(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ollama response",
            stderr="",
        )
        p = GenericProvider("ollama")
        result = p.invoke("Explain quantum computing")
        assert result == "ollama response"
        cmd = mock_run.call_args[0][0]
        assert cmd == ["ollama", "-p", "Explain quantum computing"]

    @patch("superpowers.llm_provider.subprocess.run")
    def test_invoke_custom_flag(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ok",
            stderr="",
        )
        p = GenericProvider("my-llm", prompt_flag="--prompt")
        p.invoke("hello")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["my-llm", "--prompt", "hello"]

    @patch("superpowers.llm_provider.subprocess.run")
    def test_invoke_with_model_override(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ok",
            stderr="",
        )
        p = GenericProvider("ollama")
        p.invoke("prompt", model="llama3")
        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "llama3" in cmd

    @patch("superpowers.llm_provider.subprocess.run")
    def test_invoke_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=127,
            stdout="",
            stderr="command not found",
        )
        p = GenericProvider("bad-tool")
        with pytest.raises(RuntimeError, match="bad-tool exited with code 127"):
            p.invoke("test")

    @patch("superpowers.llm_provider.shutil.which", return_value="/usr/local/bin/ollama")
    def test_available_true(self, mock_which):
        assert GenericProvider("ollama").available() is True
        mock_which.assert_called_with("ollama")

    @patch("superpowers.llm_provider.shutil.which", return_value=None)
    def test_available_false(self, mock_which):
        assert GenericProvider("ollama").available() is False


class TestProviderFactory:
    """get_provider() and get_default_provider() factory functions."""

    def test_get_claude(self):
        p = get_provider("claude")
        assert isinstance(p, ClaudeProvider)
        assert p.name == "claude"

    def test_get_unknown_returns_generic(self):
        p = get_provider("my-custom-llm")
        assert isinstance(p, GenericProvider)
        assert p.name == "my-custom-llm"

    def test_register_custom_provider(self):
        class DummyProvider(LLMProvider):
            @property
            def name(self):
                return "dummy"

            def invoke(self, prompt, *, model=None, system_prompt=None):
                return "dummy response"

            def available(self):
                return True

        register_provider("dummy", DummyProvider)
        p = get_provider("dummy")
        assert isinstance(p, DummyProvider)
        assert p.invoke("test") == "dummy response"

    def test_default_provider_chat(self):
        with patch.dict(os.environ, {"CHAT_MODEL": "claude"}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            p = get_default_provider(role="chat")
        assert isinstance(p, ClaudeProvider)

    def test_default_provider_job(self):
        with patch.dict(os.environ, {"JOB_MODEL": "ollama"}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            p = get_default_provider(role="job")
        assert isinstance(p, OllamaProvider)
        assert p.name == "ollama"

    def test_default_provider_fallback(self):
        """Without env vars, defaults to claude."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHAT_MODEL", None)
            os.environ.pop("OPENAI_API_KEY", None)
            p = get_default_provider(role="chat")
        assert isinstance(p, ClaudeProvider)

    def test_default_provider_job_fallback(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JOB_MODEL", None)
            os.environ.pop("OPENAI_API_KEY", None)
            p = get_default_provider(role="job")
        assert isinstance(p, ClaudeProvider)
