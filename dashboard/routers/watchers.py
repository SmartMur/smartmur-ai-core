"""Watchers: list rules."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dashboard.deps import get_watcher_engine
from dashboard.models import WatchRuleOut

router = APIRouter()


@router.get("/rules", response_model=list[WatchRuleOut])
def list_rules():
    we = get_watcher_engine()
    return [
        WatchRuleOut(
            name=r.name,
            path=r.path,
            events=r.events,
            action=r.action.value,
            command=r.command,
            enabled=r.enabled,
        )
        for r in we.list_rules()
    ]


@router.get("/rules/{name}", response_model=WatchRuleOut)
def get_rule(name: str):
    we = get_watcher_engine()
    for r in we.list_rules():
        if r.name == name:
            return WatchRuleOut(
                name=r.name,
                path=r.path,
                events=r.events,
                action=r.action.value,
                command=r.command,
                enabled=r.enabled,
            )
    raise HTTPException(status_code=404, detail="Rule not found")
