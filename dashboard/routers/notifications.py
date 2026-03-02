"""Notifications center: list, mark read, create from events."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dashboard.deps import get_notifications_db

router = APIRouter()


class NotificationOut(BaseModel):
    id: str
    source: str
    title: str
    detail: str = ""
    level: str = "info"
    read: bool = False
    created_at: float


class NotificationCreate(BaseModel):
    source: str
    title: str
    detail: str = ""
    level: str = "info"


class UnreadCount(BaseModel):
    count: int


@router.get("", response_model=list[NotificationOut])
def list_notifications(limit: int = 50, unread_only: bool = False):
    db = get_notifications_db()
    return db.list(limit=limit, unread_only=unread_only)


@router.get("/unread", response_model=UnreadCount)
def unread_count():
    db = get_notifications_db()
    return UnreadCount(count=db.unread_count())


@router.post("", response_model=NotificationOut, status_code=201)
def create_notification(req: NotificationCreate):
    db = get_notifications_db()
    return db.add(source=req.source, title=req.title, detail=req.detail, level=req.level)


@router.post("/{nid}/read")
def mark_read(nid: str):
    db = get_notifications_db()
    if not db.mark_read(nid):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.post("/read-all")
def mark_all_read():
    db = get_notifications_db()
    count = db.mark_all_read()
    return {"ok": True, "count": count}


@router.delete("/{nid}", status_code=204)
def delete_notification(nid: str):
    db = get_notifications_db()
    if not db.delete(nid):
        raise HTTPException(status_code=404, detail="Notification not found")


@router.get("/feed", response_model=list[NotificationOut])
def notification_feed():
    """Build a feed from audit log entries (last 20) and existing notifications."""
    db = get_notifications_db()
    # Return existing notifications as the feed
    return db.list(limit=30)
