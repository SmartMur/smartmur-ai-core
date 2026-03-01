import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


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

    # Home Automation
    home_assistant_url: str = ""
    home_assistant_token: str = ""

    # XDG-style paths
    data_dir: Path = field(default_factory=lambda: Path.home() / ".claude-superpowers")

    @classmethod
    def load(cls, dotenv_path: Path | None = None) -> "Settings":
        """Load settings from .env file and environment variables."""
        if dotenv_path is None:
            dotenv_path = Path.cwd() / ".env"
        _load_dotenv(dotenv_path)

        data_dir = Path(_env("CLAUDE_SUPERPOWERS_DATA_DIR", str(Path.home() / ".claude-superpowers")))
        vault_identity = _env("VAULT_IDENTITY_FILE", str(data_dir / "vault.key"))

        return cls(
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            slack_bot_token=_env("SLACK_BOT_TOKEN"),
            telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
            discord_bot_token=_env("DISCORD_BOT_TOKEN"),
            smtp_host=_env("SMTP_HOST"),
            smtp_user=_env("SMTP_USER"),
            smtp_pass=_env("SMTP_PASS"),
            smtp_port=int(_env("SMTP_PORT", "587")),
            smtp_from=_env("SMTP_FROM"),
            redis_url=_env("REDIS_URL", "redis://localhost:6379/0"),
            vault_identity_file=vault_identity,
            home_assistant_url=_env("HOME_ASSISTANT_URL"),
            home_assistant_token=_env("HOME_ASSISTANT_TOKEN"),
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
