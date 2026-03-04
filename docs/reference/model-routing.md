# Model Routing

## Overview

The model routing layer provides a provider abstraction for invoking language models. Claude and generic providers shell out to CLI binaries; OpenAI/ChatGPT uses the OpenAI Python SDK.

Two environment variables control which model is used:

- `CHAT_MODEL` -- the provider used for interactive chat and ad-hoc prompts (default: `claude`).
- `JOB_MODEL` -- the provider used for background jobs and cron tasks (default: `claude`).

Individual cron jobs can override the model on a per-job basis via the `llm_model` field.

## Architecture

```
                 +--------------------------+
                 | get_default_provider()   |
                 | role="chat" or "job"     |
                 +------------+-------------+
                              |
                 reads CHAT_MODEL or JOB_MODEL
                              |
                 +------------v-------------+
                 | get_provider_with_fallback() |
                 +------------+-------------+
                              |
              +---------------+-------------------------+
              |                                         |
     +--------v---------+                     +---------v---------+
     | Primary provider |                     | OpenAI fallback   |
     | (claude/openai/  |                     | (if enabled)      |
     | custom/generic)  |                     |                   |
     +------------------+                     +-------------------+
```

`get_provider()` looks up the name in a registry of known providers. If the name is not registered, it falls back to `GenericProvider`, which wraps any CLI binary that accepts a prompt argument. `chatgpt` and `gpt` are aliases for `openai`.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_MODEL` | `claude` | Provider name for interactive/chat use |
| `JOB_MODEL` | `claude` | Provider name for background jobs and cron |
| `OPENAI_API_KEY` | `""` | Enables OpenAI provider and fallback |
| `OPENAI_MODEL` | `gpt-4o` | Default model name for OpenAI provider |
| `LLM_FALLBACK` | `true` | Enables Claude primary -> OpenAI fallback |

Set these in `.env` or export them in your shell:

```bash
# .env
CHAT_MODEL=claude
JOB_MODEL=ollama
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
LLM_FALLBACK=true
```

### Per-Job Model Override

Cron jobs support a `llm_model` field that overrides `JOB_MODEL` for that specific job. When set, the job subprocess receives the override as the `LLM_MODEL` environment variable.

```json
{
  "daily-summary": {
    "type": "claude",
    "prompt": "Summarize today's logs.",
    "schedule": "daily at 18:00",
    "llm_model": "ollama",
    "enabled": true
  }
}
```

The resolution order is:

1. Per-job `llm_model` field (if non-empty).
2. `JOB_MODEL` environment variable.
3. Default: `"claude"`.

## Built-In Providers

### ClaudeProvider

Invokes the `claude` CLI in headless prompt mode.

| Detail | Value |
|--------|-------|
| Binary | `claude` |
| Invocation | `claude -p "<prompt>" --output-format text` |
| Model flag | `--model <name>` (optional) |
| Timeout | 600 seconds |

### OpenAIProvider (`openai` / `chatgpt` / `gpt`)

Invokes the OpenAI Chat Completions API using the `openai` Python package.

| Detail | Value |
|--------|-------|
| Auth | `OPENAI_API_KEY` |
| Invocation | `OpenAI().chat.completions.create(...)` |
| Default model | `OPENAI_MODEL` (default `gpt-4o`) |

### FallbackProvider

If `LLM_FALLBACK=true` and `OPENAI_API_KEY` is set, non-OpenAI providers are automatically wrapped so failures in the primary provider retry with OpenAI.

### GenericProvider

Wraps any CLI tool that accepts a prompt string. Used as a fallback for provider names not in the registry.

| Detail | Value |
|--------|-------|
| Binary | Configurable (e.g., `ollama`, `llama-cli`) |
| Default prompt flag | `-p` |
| Model flag | `--model <name>` (optional) |
| Timeout | 600 seconds |

The prompt flag can be customized:

```python
from superpowers.llm_provider import GenericProvider

# ollama uses "run" instead of "-p"
provider = GenericProvider("ollama", prompt_flag="run")
```

## Python API

### Quick Start

```python
from superpowers.llm_provider import get_provider, get_default_provider

# Explicit provider by name
p = get_provider("claude")
if p.available():
    answer = p.invoke("Summarize this log file")

# ChatGPT alias resolves to OpenAI provider
p = get_provider("chatgpt")
answer = p.invoke("Summarize this log file")

# Default provider for the "chat" role (reads CHAT_MODEL)
p = get_default_provider(role="chat")
answer = p.invoke("What services are running?")

# Default provider for the "job" role (reads JOB_MODEL)
p = get_default_provider(role="job")
answer = p.invoke("Analyze the backup report.")
```

### Registering a Custom Provider

```python
from superpowers.llm_provider import LLMProvider, register_provider

class MyProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "my-llm"

    def invoke(self, prompt: str, *, model: str | None = None) -> str:
        # Shell out to your CLI
        ...

    def available(self) -> bool:
        return shutil.which("my-llm") is not None

register_provider("my-llm", MyProvider)
```

After registration, `get_provider("my-llm")` returns an instance of `MyProvider` instead of falling back to `GenericProvider`.

### Checking Availability

```python
p = get_provider("claude")
if not p.available():
    print("claude CLI not found on PATH")
```

The `available()` method uses `shutil.which()` to check whether the binary exists.

### Model Override Per Invocation

```python
p = get_provider("claude")
answer = p.invoke("Explain this error", model="claude-3-haiku-20240307")
```

The `model` parameter is passed to the CLI via `--model`. Not all providers support it.

## Integration with Cron Jobs

When the cron engine executes a job, it builds the subprocess environment with:

```python
env["LLM_MODEL"] = job.llm_model or os.environ.get("JOB_MODEL", "claude")
```

Scripts and skills running inside a cron job can read `$LLM_MODEL` to know which provider to use.

### Example: Cron Job with Model Override

```bash
claw cron add nightly-analysis \
  --type claude \
  --prompt "Analyze today's container logs for anomalies." \
  --schedule "daily at 23:00" \
  --llm-model ollama
```

This job uses `ollama` regardless of what `JOB_MODEL` is set to globally.

## Examples

### Use Claude for Chat, Ollama for Background Jobs

```bash
# .env
CHAT_MODEL=claude
JOB_MODEL=ollama
```

Interactive prompts go through Claude (with optional OpenAI fallback), while cron/background jobs use `ollama run`.

### Claude Primary + ChatGPT Fallback

```bash
# .env
CHAT_MODEL=claude
JOB_MODEL=claude
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
LLM_FALLBACK=true
```

If Claude is unavailable or errors, calls automatically retry through OpenAI.

### Single Provider for Everything

```bash
# .env (or just leave unset for defaults)
CHAT_MODEL=claude
JOB_MODEL=claude
```

### Mixed: Global Ollama with One Job Using Claude

```bash
# .env
JOB_MODEL=ollama
```

```json
{
  "critical-analysis": {
    "type": "claude",
    "prompt": "Deep analysis of security logs.",
    "schedule": "daily at 02:00",
    "llm_model": "claude"
  }
}
```

## Troubleshooting

**"claude CLI exited with code 1"** -- The `claude` binary returned an error. Check that you are authenticated (`claude auth status`) and that the model name is valid.

**"OPENAI_API_KEY is not set"** -- Set `OPENAI_API_KEY` to enable `openai/chatgpt` provider usage and fallback.

**"FileNotFoundError"** -- The provider binary is not on `$PATH`. Install the tool or set `CHAT_MODEL`/`JOB_MODEL` to a binary that exists.

**"<binary> exited with code ..."** -- The generic provider wraps any CLI tool. Verify the tool works standalone: `<binary> -p "hello"`.

**Per-job override not taking effect** -- Ensure the `llm_model` field is set on the job entry in `jobs.json`. An empty string means "use global `JOB_MODEL`".

## Modules

| Module | Path | Purpose |
|--------|------|---------|
| `llm_provider` | `superpowers/llm_provider.py` | Provider abstraction, factory, registration |
| `config` | `superpowers/config.py` | Loads `CHAT_MODEL` and `JOB_MODEL` from `.env` |
| `cron_engine` | `superpowers/cron_engine.py` | Per-job model override and `LLM_MODEL` env injection |
