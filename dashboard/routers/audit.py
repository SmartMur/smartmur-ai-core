"""Audit log: tail and search."""

from __future__ import annotations

from fastapi import APIRouter

from dashboard.deps import get_audit_log
from dashboard.models import AuditEntry

router = APIRouter()


@router.get("/tail", response_model=list[AuditEntry])
def tail_audit(n: int = 20):
    audit = get_audit_log()
    entries = audit.tail(n)
    return [AuditEntry(**e) for e in entries]


@router.get("/search", response_model=list[AuditEntry])
def search_audit(q: str, limit: int = 50):
    audit = get_audit_log()
    entries = audit.search(q, limit=limit)
    return [AuditEntry(**e) for e in entries]
