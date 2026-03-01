"""Memory: CRUD, search, stats, decay."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dashboard.deps import get_memory_store
from dashboard.models import MemoryCreateRequest, MemoryEntryOut, MemoryStatsOut

router = APIRouter()


def _entry_to_out(e) -> MemoryEntryOut:
    return MemoryEntryOut(
        id=e.id,
        category=e.category.value,
        key=e.key,
        value=e.value,
        tags=e.tags,
        project=e.project,
        created_at=e.created_at,
        accessed_at=e.accessed_at,
        access_count=e.access_count,
    )


@router.get("", response_model=list[MemoryEntryOut])
def list_memories(category: str | None = None, project: str | None = None, limit: int = 50):
    store = get_memory_store()
    entries = store.list_memories(category=category, project=project, limit=limit)
    return [_entry_to_out(e) for e in entries]


@router.get("/stats", response_model=MemoryStatsOut)
def memory_stats():
    store = get_memory_store()
    stats = store.stats()
    return MemoryStatsOut(**stats)


@router.get("/search", response_model=list[MemoryEntryOut])
def search_memories(q: str, category: str | None = None, limit: int = 20):
    store = get_memory_store()
    results = store.search(q, category=category, limit=limit)
    return [_entry_to_out(e) for e in results]


@router.post("", response_model=MemoryEntryOut, status_code=201)
def create_memory(req: MemoryCreateRequest):
    store = get_memory_store()
    try:
        entry = store.remember(
            key=req.key,
            value=req.value,
            category=req.category,
            tags=req.tags,
            project=req.project,
        )
        return _entry_to_out(entry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{key}", response_model=MemoryEntryOut)
def recall_memory(key: str, category: str | None = None):
    store = get_memory_store()
    entry = store.recall(key, category=category)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _entry_to_out(entry)


@router.delete("/{key}", status_code=204)
def forget_memory(key: str, category: str | None = None):
    store = get_memory_store()
    deleted = store.forget(key, category=category)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")


@router.post("/decay")
def trigger_decay(days: int = 90):
    store = get_memory_store()
    count = store.decay(days=days)
    return {"removed": count, "days_threshold": days}
