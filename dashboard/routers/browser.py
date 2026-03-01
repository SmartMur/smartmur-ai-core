"""Browser: list profiles."""

from __future__ import annotations

from fastapi import APIRouter

from dashboard.deps import get_browser_profiles
from dashboard.models import BrowserProfileOut

router = APIRouter()


@router.get("/profiles", response_model=list[BrowserProfileOut])
def list_profiles():
    pm = get_browser_profiles()
    return [BrowserProfileOut(name=name) for name in pm.list_profiles()]
