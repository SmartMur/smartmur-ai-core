from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def remember(
        key: str,
        value: str,
        category: str = "fact",
        tags: str = "",
        project: str = "",
    ) -> str:
        """Store a memory with a key, value, category, and optional tags.

        Categories: fact, preference, project_context, conversation_summary.
        Tags: comma-separated string (e.g. "network,ssh,homelab").
        """
        from superpowers.memory.store import MemoryStore

        store = MemoryStore()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        try:
            entry = store.remember(
                key=key,
                value=value,
                category=category,
                tags=tag_list,
                project=project,
            )
            return (
                f"Stored memory [{entry.category.value}] {entry.key} = {entry.value}"
                f" (id={entry.id}, tags={entry.tags}, project={entry.project!r})"
            )
        except (OSError, ValueError, KeyError) as exc:
            return f"Error storing memory: {exc}"

    @mcp.tool()
    def recall(key: str, category: str = "", project: str = "") -> str:
        """Retrieve a memory by its exact key. Returns the stored value or 'not found'."""
        from superpowers.memory.store import MemoryStore

        store = MemoryStore()
        try:
            entry = store.recall(
                key=key,
                category=category or None,
                project=project or None,
            )
            if entry is None:
                return f"Not found: {key!r}"
            tag_str = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            return (
                f"[{entry.category.value}] {entry.key} = {entry.value}{tag_str}\n"
                f"  project={entry.project!r}  accessed={entry.access_count}x  "
                f"created={entry.created_at}  last_access={entry.accessed_at}"
            )
        except (OSError, ValueError, KeyError) as exc:
            return f"Error recalling memory: {exc}"

    @mcp.tool()
    def search_memory(
        query: str,
        category: str = "",
        project: str = "",
        limit: int = 20,
    ) -> str:
        """Search memories by substring match on key or value. Returns formatted results."""
        from superpowers.memory.store import MemoryStore

        store = MemoryStore()
        try:
            entries = store.search(
                query=query,
                category=category or None,
                project=project or None,
                limit=limit,
            )
            if not entries:
                return f"No memories found matching {query!r}"
            lines = [f"Found {len(entries)} memor{'y' if len(entries) == 1 else 'ies'}:", ""]
            for e in entries:
                tag_str = f" [{', '.join(e.tags)}]" if e.tags else ""
                lines.append(f"  [{e.category.value}] {e.key} = {e.value}{tag_str}")
            return "\n".join(lines)
        except (OSError, ValueError, KeyError) as exc:
            return f"Error searching memories: {exc}"

    @mcp.tool()
    def forget(key: str, category: str = "") -> str:
        """Delete a memory by key. Returns confirmation or not-found message."""
        from superpowers.memory.store import MemoryStore

        store = MemoryStore()
        try:
            deleted = store.forget(key=key, category=category or None)
            if deleted:
                return f"Deleted memory: {key!r}"
            return f"No memory found with key {key!r}"
        except (OSError, ValueError, KeyError) as exc:
            return f"Error deleting memory: {exc}"

    @mcp.tool()
    def list_memories(
        category: str = "",
        project: str = "",
        limit: int = 50,
    ) -> str:
        """List all memories, optionally filtered by category and project."""
        from superpowers.memory.store import MemoryStore

        store = MemoryStore()
        try:
            entries = store.list_memories(
                category=category or None,
                project=project or None,
                limit=limit,
            )
            if not entries:
                return "No memories stored."
            lines = [
                f"{'ID':>4}  {'Category':<22}  {'Key':<30}  {'Value'}",
                f"{'─' * 4}  {'─' * 22}  {'─' * 30}  {'─' * 40}",
            ]
            for e in entries:
                cat = e.category.value
                val = e.value if len(e.value) <= 60 else e.value[:57] + "..."
                lines.append(f"{e.id:>4}  {cat:<22}  {e.key:<30}  {val}")
            lines.append(f"\nTotal: {len(entries)} memor{'y' if len(entries) == 1 else 'ies'}")
            return "\n".join(lines)
        except (OSError, ValueError, KeyError) as exc:
            return f"Error listing memories: {exc}"

    @mcp.tool()
    def memory_stats() -> str:
        """Return memory database statistics: total count, breakdown by category, date range."""
        from superpowers.memory.store import MemoryStore

        store = MemoryStore()
        try:
            s = store.stats()
            lines = [
                "Memory Store Statistics",
                f"  Total entries: {s['total']}",
            ]
            if s["by_category"]:
                lines.append("  By category:")
                for cat, cnt in sorted(s["by_category"].items()):
                    lines.append(f"    {cat}: {cnt}")
            if s["oldest"]:
                lines.append(f"  Oldest entry: {s['oldest']}")
            if s["newest"]:
                lines.append(f"  Newest entry: {s['newest']}")
            return "\n".join(lines)
        except (OSError, ValueError, KeyError) as exc:
            return f"Error getting stats: {exc}"
