"""Data types for the memory subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MemoryStoreError(Exception):
    """Raised on memory store failures."""


class MemoryCategory(str, Enum):
    fact = "fact"
    preference = "preference"
    project_context = "project_context"
    conversation_summary = "conversation_summary"


@dataclass
class MemoryEntry:
    id: int
    category: MemoryCategory
    key: str
    value: str
    tags: list[str] = field(default_factory=list)
    project: str = ""
    created_at: str = ""
    accessed_at: str = ""
    access_count: int = 0
