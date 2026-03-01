from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def audit_tail(limit: int = 20) -> str:
        """Show the most recent audit log entries.

        Args:
            limit: Number of entries to return (default 20).
        """
        try:
            from superpowers.audit import AuditLog

            log = AuditLog()
            entries = log.tail(limit)
            if not entries:
                return "Audit log is empty."

            lines = [f"Last {len(entries)} audit entries:"]
            for e in entries:
                ts = e.get("ts", "?")
                action = e.get("action", "?")
                detail = e.get("detail", "")
                source = e.get("source", "")
                src = f" [{source}]" if source else ""
                lines.append(f"  {ts}  {action}{src}  {detail}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Error reading audit log: {exc}"

    @mcp.tool()
    def audit_search(query: str, limit: int = 50) -> str:
        """Search the audit log for entries matching a query string.

        Args:
            query: Case-insensitive search term to match against log entries.
            limit: Maximum number of results to return (default 50).
        """
        try:
            from superpowers.audit import AuditLog

            log = AuditLog()
            entries = log.search(query, limit)
            if not entries:
                return f"No audit entries matching '{query}'."

            lines = [f"{len(entries)} match(es) for '{query}':"]
            for e in entries:
                ts = e.get("ts", "?")
                action = e.get("action", "?")
                detail = e.get("detail", "")
                source = e.get("source", "")
                src = f" [{source}]" if source else ""
                lines.append(f"  {ts}  {action}{src}  {detail}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Error searching audit log: {exc}"
