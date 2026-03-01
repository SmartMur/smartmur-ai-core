"""Auto-context injection from memory store."""

from __future__ import annotations

from superpowers.memory.store import MemoryStore


class ContextBuilder:
    """Builds context snippets from stored memories for system prompt injection."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def build_context(self, project: str = "", limit: int = 10) -> str:
        entries = self.store.list_memories(project=project or None, limit=limit)
        if not entries:
            return ""
        lines = ["## Remembered Context", ""]
        for entry in entries:
            tag_str = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            lines.append(f"- **{entry.key}** ({entry.category.value}): {entry.value}{tag_str}")
        lines.append("")
        return "\n".join(lines)

    def inject_hook(self, project: str = "") -> str:
        return self.build_context(project=project)
