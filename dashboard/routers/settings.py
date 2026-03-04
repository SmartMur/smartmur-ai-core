"""Settings area: cron management, notification profiles, integrations."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from dashboard.deps import (
    get_cron_engine,
    get_profile_manager,
    get_settings,
)

router = APIRouter()


class IntegrationStatus(BaseModel):
    name: str
    configured: bool
    detail: str = ""


class SettingsOverview(BaseModel):
    integrations: list[IntegrationStatus]
    cron_count: int = 0
    profile_count: int = 0


@router.get("/overview", response_model=SettingsOverview)
def settings_overview():
    settings = get_settings()

    integrations = []

    # Check configured integrations
    integrations.append(
        IntegrationStatus(
            name="Telegram",
            configured=bool(settings.telegram_bot_token),
            detail="Bot token configured" if settings.telegram_bot_token else "Not configured",
        )
    )
    integrations.append(
        IntegrationStatus(
            name="Slack",
            configured=bool(settings.slack_bot_token),
            detail="Bot token configured" if settings.slack_bot_token else "Not configured",
        )
    )
    integrations.append(
        IntegrationStatus(
            name="Discord",
            configured=bool(settings.discord_bot_token),
            detail="Bot token configured" if settings.discord_bot_token else "Not configured",
        )
    )
    integrations.append(
        IntegrationStatus(
            name="Email (SMTP)",
            configured=bool(settings.smtp_host),
            detail=f"Host: {settings.smtp_host}" if settings.smtp_host else "Not configured",
        )
    )
    integrations.append(
        IntegrationStatus(
            name="Home Assistant",
            configured=bool(settings.home_assistant_url),
            detail=settings.home_assistant_url if settings.home_assistant_url else "Not configured",
        )
    )
    integrations.append(
        IntegrationStatus(
            name="Redis",
            configured=bool(settings.redis_url),
            detail=settings.redis_url if settings.redis_url else "Not configured",
        )
    )
    integrations.append(
        IntegrationStatus(
            name="Anthropic API",
            configured=bool(settings.anthropic_api_key),
            detail="API key configured" if settings.anthropic_api_key else "Not configured",
        )
    )

    cron_count = 0
    try:
        engine = get_cron_engine()
        cron_count = len(engine.list_jobs())
    except (ImportError, OSError, RuntimeError):
        pass

    profile_count = 0
    try:
        pm = get_profile_manager()
        profile_count = len(pm.list_profiles())
    except (ImportError, OSError, RuntimeError):
        pass

    return SettingsOverview(
        integrations=integrations,
        cron_count=cron_count,
        profile_count=profile_count,
    )


@router.get("/integrations", response_model=list[IntegrationStatus])
def list_integrations():
    overview = settings_overview()
    return overview.integrations
