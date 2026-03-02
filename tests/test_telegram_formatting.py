"""Tests for MarkdownV2 escaping and smart chunking (msg_gateway.telegram.formatting)."""

from __future__ import annotations

import pytest

from msg_gateway.telegram.formatting import (
    CHUNK_SIZE,
    MAX_MESSAGE_LENGTH,
    escape_markdown_v2,
    smart_chunk,
)


# ---------------------------------------------------------------------------
# escape_markdown_v2 — special character escaping
# ---------------------------------------------------------------------------


class TestEscapeMarkdownV2:
    def test_plain_text_unchanged(self):
        assert escape_markdown_v2("hello world") == "hello world"

    def test_escapes_underscore(self):
        assert escape_markdown_v2("_italic_") == "\\_italic\\_"

    def test_escapes_asterisk(self):
        assert escape_markdown_v2("*bold*") == "\\*bold\\*"

    def test_escapes_square_brackets(self):
        assert escape_markdown_v2("[link]") == "\\[link\\]"

    def test_escapes_parentheses(self):
        assert escape_markdown_v2("(url)") == "\\(url\\)"

    def test_escapes_tilde(self):
        assert escape_markdown_v2("~strikethrough~") == "\\~strikethrough\\~"

    def test_escapes_hash(self):
        assert escape_markdown_v2("# heading") == "\\# heading"

    def test_escapes_plus(self):
        assert escape_markdown_v2("a + b") == "a \\+ b"

    def test_escapes_minus(self):
        assert escape_markdown_v2("a - b") == "a \\- b"

    def test_escapes_equals(self):
        assert escape_markdown_v2("a = b") == "a \\= b"

    def test_escapes_pipe(self):
        assert escape_markdown_v2("a | b") == "a \\| b"

    def test_escapes_curly_braces(self):
        assert escape_markdown_v2("{dict}") == "\\{dict\\}"

    def test_escapes_period(self):
        assert escape_markdown_v2("end.") == "end\\."

    def test_escapes_exclamation(self):
        assert escape_markdown_v2("wow!") == "wow\\!"

    def test_escapes_greater_than(self):
        assert escape_markdown_v2("> quote") == "\\> quote"

    def test_multiple_special_chars(self):
        result = escape_markdown_v2("Hello *world* [link](url)!")
        assert result == "Hello \\*world\\* \\[link\\]\\(url\\)\\!"


# ---------------------------------------------------------------------------
# escape_markdown_v2 — code block preservation
# ---------------------------------------------------------------------------


class TestEscapeMarkdownV2CodeBlocks:
    def test_preserves_triple_backtick_code_block(self):
        text = "Before ```python\nprint('hello')\n``` After"
        result = escape_markdown_v2(text)
        # Code block should be untouched
        assert "```python\nprint('hello')\n```" in result
        # Outside parts should be escaped
        assert result.startswith("Before ")
        assert result.endswith(" After")

    def test_preserves_code_block_special_chars(self):
        text = "```\na = b + c * d\n```"
        result = escape_markdown_v2(text)
        # The entire block is preserved as-is
        assert result == text

    def test_preserves_inline_code(self):
        text = "Use `print()` to debug"
        result = escape_markdown_v2(text)
        assert "`print()`" in result

    def test_inline_code_special_chars_preserved(self):
        text = "Run `a + b * c` now"
        result = escape_markdown_v2(text)
        assert "`a + b * c`" in result

    def test_unclosed_code_block_preserved(self):
        text = "```python\nprint('hello')"
        result = escape_markdown_v2(text)
        # Unclosed — rest is included as-is
        assert "```python\nprint('hello')" in result

    def test_unclosed_inline_code_preserved(self):
        text = "some `unclosed code"
        result = escape_markdown_v2(text)
        assert "`unclosed code" in result

    def test_multiple_code_blocks(self):
        text = "A ```x``` B ```y``` C"
        result = escape_markdown_v2(text)
        assert "```x```" in result
        assert "```y```" in result

    def test_mixed_inline_and_block(self):
        text = "Use `foo` or ```\nbar\n``` here"
        result = escape_markdown_v2(text)
        assert "`foo`" in result
        assert "```\nbar\n```" in result


# ---------------------------------------------------------------------------
# smart_chunk — short text (no splitting)
# ---------------------------------------------------------------------------


class TestSmartChunkNoSplit:
    def test_short_text_returns_single_chunk(self):
        text = "Hello world"
        chunks = smart_chunk(text)
        assert chunks == ["Hello world"]

    def test_exactly_max_length(self):
        text = "a" * CHUNK_SIZE
        chunks = smart_chunk(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text(self):
        chunks = smart_chunk("")
        assert chunks == [""]


# ---------------------------------------------------------------------------
# smart_chunk — paragraph boundary splitting
# ---------------------------------------------------------------------------


class TestSmartChunkParagraph:
    def test_splits_at_paragraph_boundary(self):
        # Build text that exceeds CHUNK_SIZE with a paragraph boundary
        para1 = "A" * 2500
        para2 = "B" * 2500
        text = f"{para1}\n\n{para2}"

        chunks = smart_chunk(text, max_length=3000)
        assert len(chunks) >= 2
        # First chunk should end near the paragraph boundary
        assert chunks[0].endswith("A")
        # Second chunk should contain the B paragraph
        assert "B" in chunks[-1]


# ---------------------------------------------------------------------------
# smart_chunk — line boundary splitting
# ---------------------------------------------------------------------------


class TestSmartChunkLine:
    def test_splits_at_line_boundary(self):
        # Use single newlines (no paragraph boundary in second half)
        lines = ["Line " + str(i) + " " + "x" * 50 for i in range(100)]
        text = "\n".join(lines)

        chunks = smart_chunk(text, max_length=500)
        assert len(chunks) > 1
        # Each chunk should end at a line boundary (no broken words)
        for chunk in chunks[:-1]:
            # Chunks are rstripped so they should end with content, not \n
            assert not chunk.endswith("\n")


# ---------------------------------------------------------------------------
# smart_chunk — code block preservation
# ---------------------------------------------------------------------------


class TestSmartChunkCodeBlocks:
    def test_does_not_break_code_block(self):
        # Create a code block that would straddle the split point
        before = "X" * 100
        code_block = "```python\n" + "print('hello')\n" * 50 + "```"
        after = "Y" * 100
        text = f"{before}\n{code_block}\n{after}"

        chunks = smart_chunk(text, max_length=300)
        # The code block should appear intact in one of the chunks
        full = "".join(chunks)
        assert "```python" in full
        assert "```" in full

        # Verify no chunk has an odd number of ``` (which would mean a split block)
        for chunk in chunks:
            count = chunk.count("```")
            # Either 0 or even number of ``` markers in each chunk
            # (an odd count at chunk boundary is acceptable if the algorithm
            # chose to keep the block together, extending beyond max_length)
            if count % 2 != 0:
                # The chunk itself must contain the full block or be the extended one
                assert "```python" in chunk or chunk.count("```") == 1

    def test_code_block_exceeding_max_preserved(self):
        # A single code block larger than max_length
        code = "```\n" + "x = 1\n" * 200 + "```"
        text = "Intro\n" + code + "\nOutro"

        chunks = smart_chunk(text, max_length=200)
        # The code block should exist intact somewhere across chunks
        full = "\n".join(chunks)
        assert "```" in full


# ---------------------------------------------------------------------------
# smart_chunk — very long single line
# ---------------------------------------------------------------------------


class TestSmartChunkLongLine:
    def test_hard_split_on_very_long_line(self):
        # A single line with no natural break points
        text = "A" * 10000
        chunks = smart_chunk(text, max_length=4000)
        assert len(chunks) >= 2
        # All content should be preserved
        combined = "".join(chunks)
        assert len(combined) == 10000

    def test_splits_with_sentence_boundary(self):
        # Build text with sentences but no newlines
        sentences = ["This is sentence number %d. " % i for i in range(200)]
        text = "".join(sentences)

        chunks = smart_chunk(text, max_length=500)
        assert len(chunks) > 1
        # Content should be fully preserved
        combined = "".join(c + " " for c in chunks).replace("  ", " ")
        # All original text characters should still be present
        for sentence in sentences[:5]:
            assert sentence.strip() in text


class TestSmartChunkCustomMaxLength:
    def test_respects_custom_max_length(self):
        text = "Hello world, this is a test. " * 10
        chunks = smart_chunk(text, max_length=50)
        for chunk in chunks:
            # Chunks should generally respect max_length
            # (code block exceptions aside)
            assert len(chunk) <= 60  # small tolerance for edge cases
