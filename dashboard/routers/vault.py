"""Vault: key listing and status (no secret values exposed)."""

from __future__ import annotations

from fastapi import APIRouter

from dashboard.deps import get_vault
from dashboard.models import VaultStatus

router = APIRouter()


@router.get("/status", response_model=VaultStatus)
def vault_status():
    v = get_vault()
    initialized = v.vault_path.exists()
    key_count = 0
    if initialized:
        try:
            keys = v.list_keys()
            key_count = len(keys)
        except Exception:
            pass
    return VaultStatus(initialized=initialized, key_count=key_count)


@router.get("/keys", response_model=list[str])
def vault_keys():
    v = get_vault()
    if not v.vault_path.exists():
        return []
    try:
        return v.list_keys()
    except Exception:
        return []
