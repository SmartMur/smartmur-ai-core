import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Default credential values that MUST NOT be used in production
_INSECURE_DEFAULTS = frozenset(
    {
        "admin",
        "password",
        "changeme",
        "secret",
        "test",
        "default",
        "12345",
        "123456",
        "root",
        "pass",
        "user",
    }
)


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
    dashboard_secret: str = ""  # JWT signing secret; auto-generated if empty

    # Home Automation
    home_assistant_url: str = ""
    home_assistant_token: str = ""

    # Job Orchestration (Phase D)
    allowed_auto_merge_paths: list[str] = field(
        default_factory=lambda: [
            "docs/*",
            "*.md",
            "tests/*",
            "skills/*/skill.yaml",
        ]
    )

    # Model routing (Phase F)
    chat_model: str = "claude"  # Model/provider for interactive chat
    job_model: str = "claude"  # Model/provider for background cron/workflow jobs

    # OpenAI fallback
    openai_api_key: str = ""  # OPENAI_API_KEY — enables fallback
    openai_model: str = "gpt-4o"  # OPENAI_MODEL — default model for OpenAI
    llm_fallback: bool = True  # LLM_FALLBACK — auto-fallback when OpenAI key is set

    # Telegram Bot (Phase 9)
    allowed_chat_ids: str = ""  # Comma-separated allowlist
    telegram_session_ttl: int = 3600  # Session history TTL in seconds
    telegram_max_history: int = 20  # Max messages per chat session
    telegram_max_per_chat: int = 2  # Max concurrent jobs per chat
    telegram_max_global: int = 5  # Max concurrent jobs globally
    telegram_queue_overflow: int = 10  # Max queued jobs before rejecting
    telegram_mode: str = "polling"  # "webhook" or "polling"
    telegram_webhook_secret: str = ""  # Secret for webhook validation
    telegram_webhook_url: str = ""  # Public URL for webhook endpoint
    telegram_admin_chat_id: str = ""  # Admin chat ID for access request notifications

    # Security (Phase G)
    force_https: bool = False  # Default false for dev; true if ENVIRONMENT=production
    webhook_require_signature: bool = True  # Fail-closed webhook validation
    rate_limit_per_ip: int = 60  # Max requests per minute per IP
    rate_limit_per_user: int = 120  # Max requests per minute per authenticated user
    environment: str = "development"  # "development" or "production"

    # XDG-style paths
    data_dir: Path = field(default_factory=get_data_dir)

    @classmethod
    def _vault_get(cls, key: str, data_dir: Path) -> str:
        """Try to read a secret from the encrypted vault.

        Returns the value if the vault is available and the key exists,
        otherwise returns empty string.  Never raises — vault is optional.
        """
        try:
            from superpowers.vault import Vault

            v = Vault(
                vault_path=data_dir / "vault.enc", identity_file=data_dir / "age-identity.txt"
            )
            if v.vault_path.exists() and v.identity_file.exists():
                val = v.get(key)
                return val if val else ""
        except (ImportError, OSError, RuntimeError, ValueError):
            pass
        return ""

    @classmethod
    def load(cls, dotenv_path: Path | None = None) -> "Settings":
        """Load settings from .env file, environment variables, and vault.

        Resolution order for sensitive fields: env var first, then vault
        fallback.  Non-secret fields are env-only.
        """
        if dotenv_path is None:
            dotenv_path = Path.cwd() / ".env"
        _load_dotenv(dotenv_path)

        data_dir = get_data_dir()
        vault_identity = _env("VAULT_IDENTITY_FILE", str(data_dir / "vault.key"))

        # For sensitive fields, try env var first, then vault
        def _secret(env_key: str) -> str:
            val = _env(env_key)
            if val:
                return val
            return cls._vault_get(env_key, data_dir)

        return cls(
            anthropic_api_key=_secret("ANTHROPIC_API_KEY"),
            slack_bot_token=_secret("SLACK_BOT_TOKEN"),
            telegram_bot_token=_secret("TELEGRAM_BOT_TOKEN"),
            telegram_default_chat_id=_secret("TELEGRAM_DEFAULT_CHAT_ID"),
            discord_bot_token=_secret("DISCORD_BOT_TOKEN"),
            smtp_host=_env("SMTP_HOST"),
            smtp_user=_secret("SMTP_USER"),
            smtp_pass=_secret("SMTP_PASS"),
            smtp_port=int(_env("SMTP_PORT", "587")),
            smtp_from=_env("SMTP_FROM"),
            redis_url=_env("REDIS_URL", "redis://localhost:6379/0"),
            vault_identity_file=vault_identity,
            dashboard_user=_env("DASHBOARD_USER"),
            dashboard_pass=_secret("DASHBOARD_PASS"),
            dashboard_secret=_secret("DASHBOARD_SECRET"),
            home_assistant_url=_env("HOME_ASSISTANT_URL"),
            home_assistant_token=_secret("HOME_ASSISTANT_TOKEN"),
            chat_model=_env("CHAT_MODEL", "claude"),
            job_model=_env("JOB_MODEL", "claude"),
            openai_api_key=_secret("OPENAI_API_KEY"),
            openai_model=_env("OPENAI_MODEL", "gpt-4o"),
            llm_fallback=_env("LLM_FALLBACK", "true").lower() not in ("false", "0", "no"),
            allowed_chat_ids=_env("ALLOWED_CHAT_IDS"),
            telegram_session_ttl=int(_env("TELEGRAM_SESSION_TTL", "3600")),
            telegram_max_history=int(_env("TELEGRAM_MAX_HISTORY", "20")),
            telegram_max_per_chat=int(_env("TELEGRAM_MAX_PER_CHAT", "2")),
            telegram_max_global=int(_env("TELEGRAM_MAX_GLOBAL", "5")),
            telegram_queue_overflow=int(_env("TELEGRAM_QUEUE_OVERFLOW", "10")),
            telegram_mode=_env("TELEGRAM_MODE", "polling"),
            telegram_webhook_secret=_env("TELEGRAM_WEBHOOK_SECRET"),
            telegram_webhook_url=_env("TELEGRAM_WEBHOOK_URL"),
            telegram_admin_chat_id=_env("TELEGRAM_ADMIN_CHAT_ID"),
            environment=_env("ENVIRONMENT", "development"),
            force_https=_env("FORCE_HTTPS", "").lower() in ("true", "1", "yes")
            or _env("ENVIRONMENT", "development").lower() == "production",
            webhook_require_signature=_env("WEBHOOK_REQUIRE_SIGNATURE", "true").lower()
            not in ("false", "0", "no"),
            rate_limit_per_ip=int(_env("RATE_LIMIT_PER_IP", "60")),
            rate_limit_per_user=int(_env("RATE_LIMIT_PER_USER", "120")),
            data_dir=data_dir,
        )

    def validate_security(self) -> list[str]:
        """Validate security configuration and return a list of warnings.

        This should be called at application startup.  Each warning is a
        human-readable string describing a security concern.  An empty list
        means all checks passed.
        """
        warnings: list[str] = []

        # Dashboard credentials must be set and non-trivial
        if not self.dashboard_user and not self.dashboard_pass:
            warnings.append(
                "DASHBOARD_USER and DASHBOARD_PASS are not set. "
                "Dashboard authentication will reject all requests."
            )
        elif not self.dashboard_user:
            warnings.append("DASHBOARD_USER is not set.")
        elif not self.dashboard_pass:
            warnings.append("DASHBOARD_PASS is not set.")

        if self.dashboard_user and self.dashboard_user.lower() in _INSECURE_DEFAULTS:
            warnings.append(
                f"DASHBOARD_USER is set to an insecure default value "
                f"'{self.dashboard_user}'. Use a unique username."
            )
        if self.dashboard_pass and self.dashboard_pass.lower() in _INSECURE_DEFAULTS:
            warnings.append(
                "DASHBOARD_PASS is set to an insecure default value. "
                "Generate a strong password with: "
                'python3 -c "import secrets; print(secrets.token_urlsafe(24))"'
            )

        # HTTPS enforcement
        if self.environment == "production" and not self.force_https:
            warnings.append(
                "ENVIRONMENT=production but FORCE_HTTPS is not enabled. "
                "Set FORCE_HTTPS=true or use a TLS-terminating reverse proxy."
            )

        # Webhook signature validation
        if not self.webhook_require_signature:
            warnings.append(
                "WEBHOOK_REQUIRE_SIGNATURE is disabled. Inbound webhooks will NOT be verified."
            )

        for w in warnings:
            logger.warning("Security: %s", w)

        return warnings

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
