import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def get_data_dir() -> Path:
    """Return the configured data directory.

    Reads ``SUPERPOWERS_DATA_DIR`` (preferred) or the legacy
    ``CLAUDE_SUPERPOWERS_DATA_DIR`` env var.  Falls back to
    ``~/.claude-superpowers`` when neither is set.

    This is intentionally a plain function so it can be called safely at
    module level without circular imports.
    """
    env_val = os.environ.get("SUPERPOWERS_DATA_DIR") or os.environ.get(
        "CLAUDE_SUPERPOWERS_DATA_DIR"
    )
    if env_val:
        return Path(env_val)
    return Path.home() / ".claude-superpowers"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader — no external dependency required."""
    if not path.is_file():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass
class Settings:
    # LLM
    anthropic_api_key: str = ""

    # Messaging
    slack_bot_token: str = ""
    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""
    discord_bot_token: str = ""
    smtp_host: str = ""
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_port: int = 587
    smtp_from: str = ""

    # Infrastructure
    redis_url: str = "redis://localhost:6379/0"

    # Vault
    vault_identity_file: str = ""

    # Dashboard (MUST be set via DASHBOARD_USER / DASHBOARD_PASS env vars)
    dashboard_user: str = ""
    dashboard_pass: str = ""

    # Home Automation
    home_assistant_url: str = ""
    home_assistant_token: str = ""

    # Telegram Bot (Phase 9)
    allowed_chat_ids: str = ""  # Comma-separated allowlist
    telegram_session_ttl: int = 3600  # Session history TTL in seconds
    telegram_max_history: int = 20  # Max messages per chat session
    telegram_max_per_chat: int = 2  # Max concurrent jobs per chat
    telegram_max_global: int = 5  # Max concurrent jobs globally
    telegram_queue_overflow: int = 10  # Max queued jobs before rejecting

    # XDG-style paths
    data_dir: Path = field(default_factory=get_data_dir)

    @classmethod
    def load(cls, dotenv_path: Path | None = None) -> "Settings":
        """Load settings from .env file and environment variables."""
        if dotenv_path is None:
            dotenv_path = Path.cwd() / ".env"
        _load_dotenv(dotenv_path)

        data_dir = get_data_dir()
        vault_identity = _env("VAULT_IDENTITY_FILE", str(data_dir / "vault.key"))

        return cls(
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            slack_bot_token=_env("SLACK_BOT_TOKEN"),
            telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
            telegram_default_chat_id=_env("TELEGRAM_DEFAULT_CHAT_ID"),
            discord_bot_token=_env("DISCORD_BOT_TOKEN"),
            smtp_host=_env("SMTP_HOST"),
            smtp_user=_env("SMTP_USER"),
            smtp_pass=_env("SMTP_PASS"),
            smtp_port=int(_env("SMTP_PORT", "587")),
            smtp_from=_env("SMTP_FROM"),
            redis_url=_env("REDIS_URL", "redis://localhost:6379/0"),
            vault_identity_file=vault_identity,
            dashboard_user=_env("DASHBOARD_USER"),
            dashboard_pass=_env("DASHBOARD_PASS"),
            home_assistant_url=_env("HOME_ASSISTANT_URL"),
            home_assistant_token=_env("HOME_ASSISTANT_TOKEN"),
            allowed_chat_ids=_env("ALLOWED_CHAT_IDS"),
            telegram_session_ttl=int(_env("TELEGRAM_SESSION_TTL", "3600")),
            telegram_max_history=int(_env("TELEGRAM_MAX_HISTORY", "20")),
            telegram_max_per_chat=int(_env("TELEGRAM_MAX_PER_CHAT", "2")),
            telegram_max_global=int(_env("TELEGRAM_MAX_GLOBAL", "5")),
            telegram_queue_overflow=int(_env("TELEGRAM_QUEUE_OVERFLOW", "10")),
            data_dir=data_dir,
        )

    def ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "skills").mkdir(exist_ok=True)
        (self.data_dir / "cron").mkdir(exist_ok=True)
        (self.data_dir / "vault").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        (self.data_dir / "msg").mkdir(exist_ok=True)
        (self.data_dir / "ssh").mkdir(exist_ok=True)
        (self.data_dir / "watcher").mkdir(exist_ok=True)
        (self.data_dir / "browser").mkdir(exist_ok=True)
        (self.data_dir / "browser" / "profiles").mkdir(exist_ok=True)
        (self.data_dir / "memory").mkdir(exist_ok=True)
        (self.data_dir / "workflows").mkdir(exist_ok=True)
