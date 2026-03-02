"""MarkdownV2 escaping and smart message chunking."""

from __future__ import annotations

import re

# Characters that must be escaped in MarkdownV2 (outside code blocks)
_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"

# Telegram message length limit
MAX_MESSAGE_LENGTH = 4096
# Safe chunk size (leave room for continuation markers)
CHUNK_SIZE = 4000


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2.

    Preserves content inside code blocks (``` and `).
    """
    parts: list[str] = []
    i = 0
    while i < len(text):
        # Triple backtick code block
        if text[i:i + 3] == "```":
            end = text.find("```", i + 3)
            if end == -1:
                # Unclosed block — include rest as-is
                parts.append(text[i:])
                break
            parts.append(text[i:end + 3])
            i = end + 3
            continue

        # Inline code
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end == -1:
                parts.append(text[i:])
                break
            parts.append(text[i:end + 1])
            i = end + 1
            continue

        # Escape special chars outside code
        if text[i] in _ESCAPE_CHARS:
            parts.append(f"\\{text[i]}")
        else:
            parts.append(text[i])
        i += 1

    return "".join(parts)


def smart_chunk(text: str, max_length: int = CHUNK_SIZE) -> list[str]:
    """Split text into chunks that respect code block boundaries.

    - Never breaks inside a code block
    - Prefers splitting at paragraph boundaries (double newline)
    - Falls back to line boundaries, then hard split
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Find the best split point within max_length
        candidate = remaining[:max_length]

        # Check if we're inside a code block
        # Count opening/closing ``` pairs in the candidate
        open_blocks = len(re.findall(r"```", candidate))
        if open_blocks % 2 != 0:
            # We're inside a code block — find its end
            block_end = remaining.find("```", candidate.rfind("```") + 3)
            if block_end != -1 and block_end + 3 <= len(remaining):
                # Include the full code block even if it exceeds max_length
                split_at = block_end + 3
                # Look for a newline after the closing ```
                nl = remaining.find("\n", split_at)
                if nl != -1 and nl < split_at + 10:
                    split_at = nl + 1
            else:
                # Can't find end — fall through to normal splitting
                split_at = _find_split_point(candidate)
        else:
            split_at = _find_split_point(candidate)

        chunk = remaining[:split_at].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip("\n")

    return chunks if chunks else [text]


def _find_split_point(text: str) -> int:
    """Find the best split point in text, preferring paragraph > line > hard."""
    # Try paragraph boundary (double newline)
    idx = text.rfind("\n\n")
    if idx > len(text) // 2:
        return idx + 2

    # Try line boundary
    idx = text.rfind("\n")
    if idx > len(text) // 2:
        return idx + 1

    # Try sentence boundary
    for sep in (". ", "! ", "? "):
        idx = text.rfind(sep)
        if idx > len(text) // 2:
            return idx + len(sep)

    # Hard split at max_length
    return len(text)
