"""Telegram attachment ingestion — download, extract, and describe photos/documents."""

from __future__ import annotations

import logging
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from msg_gateway.telegram.api import TelegramApi
from msg_gateway.telegram.types import Message

logger = logging.getLogger(__name__)

# Supported document MIME types for text extraction
_TEXT_MIMES = {
    "text/plain",
    "text/csv",
    "text/html",
    "text/markdown",
    "application/json",
    "application/xml",
    "text/xml",
}
_PDF_MIMES = {"application/pdf"}
_IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# Max file size for download (20 MB — Telegram Bot API limit)
MAX_FILE_SIZE = 20 * 1024 * 1024


class AttachmentHandler:
    """Download and process Telegram file attachments."""

    def __init__(self, api: TelegramApi):
        self._api = api
        self._token = api._token

    def process_message(self, msg: Message) -> str | None:
        """Process attachments in a message. Returns extracted text/description or None."""
        if msg.photo:
            return self._handle_photo(msg)
        if msg.document:
            return self._handle_document(msg)
        return None

    def _handle_photo(self, msg: Message) -> str | None:
        """Download the largest photo and return a description."""
        if not msg.photo:
            return None

        # Telegram sends multiple sizes — pick the largest
        best = max(msg.photo, key=lambda p: p.file_size or (p.width * p.height))
        if not best.file_id:
            return None

        path = self._download_file(best.file_id)
        if not path:
            return "[Could not download photo]"

        try:
            description = self._describe_image(path)
            caption = msg.caption or ""
            if caption:
                return f"[Photo: {description}]\nCaption: {caption}"
            return f"[Photo: {description}]"
        finally:
            path.unlink(missing_ok=True)

    def _handle_document(self, msg: Message) -> str | None:
        """Download a document and extract its text content."""
        doc = msg.document
        if not doc or not doc.file_id:
            return None

        mime = doc.mime_type or ""
        file_name = doc.file_name or "unknown"

        # Check if it's an image sent as document
        if mime in _IMAGE_MIMES:
            path = self._download_file(doc.file_id)
            if not path:
                return f"[Could not download image document: {file_name}]"
            try:
                description = self._describe_image(path)
                caption = msg.caption or ""
                if caption:
                    return f"[Image document '{file_name}': {description}]\nCaption: {caption}"
                return f"[Image document '{file_name}': {description}]"
            finally:
                path.unlink(missing_ok=True)

        # Text-based documents
        if mime in _TEXT_MIMES:
            path = self._download_file(doc.file_id)
            if not path:
                return f"[Could not download document: {file_name}]"
            try:
                content = path.read_text(errors="replace")[:10000]
                caption = msg.caption or ""
                if caption:
                    return f"[Document '{file_name}' content:]\n{content}\nCaption: {caption}"
                return f"[Document '{file_name}' content:]\n{content}"
            finally:
                path.unlink(missing_ok=True)

        # PDF documents
        if mime in _PDF_MIMES:
            path = self._download_file(doc.file_id)
            if not path:
                return f"[Could not download PDF: {file_name}]"
            try:
                text = self._extract_pdf_text(path)
                caption = msg.caption or ""
                if caption:
                    return f"[PDF '{file_name}' content:]\n{text}\nCaption: {caption}"
                return f"[PDF '{file_name}' content:]\n{text}"
            finally:
                path.unlink(missing_ok=True)

        # Unsupported type
        caption = msg.caption or ""
        if caption:
            return f"[Unsupported document type: {file_name} ({mime})]\nCaption: {caption}"
        return f"[Unsupported document type: {file_name} ({mime})]"

    def _download_file(self, file_id: str) -> Path | None:
        """Download a file from Telegram and return its local path."""
        resp = self._api.get_file(file_id)
        if not resp.ok or not resp.result:
            logger.error("getFile failed for %s: %s", file_id, resp.description)
            return None

        file_path = resp.result.get("file_path", "")
        if not file_path:
            logger.error("No file_path in getFile response for %s", file_id)
            return None

        download_url = f"https://api.telegram.org/file/bot{self._token}/{file_path}"
        try:
            with urllib.request.urlopen(download_url, timeout=30) as resp_data:
                data = resp_data.read(MAX_FILE_SIZE + 1)
                if len(data) > MAX_FILE_SIZE:
                    logger.warning("File %s exceeds max size", file_id)
                    return None

            # Determine suffix from file_path
            suffix = Path(file_path).suffix or ".bin"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(data)
            tmp.close()
            return Path(tmp.name)

        except (urllib.error.URLError, OSError) as exc:
            logger.error("Failed to download file %s: %s", file_id, exc)
            return None

    def _describe_image(self, path: Path) -> str:
        """Describe an image using available LLM or return a placeholder."""
        try:
            import base64

            from superpowers.llm_provider import get_default_provider

            # Read image and encode as base64
            image_data = path.read_bytes()
            b64 = base64.b64encode(image_data).decode()

            # Determine mime type from suffix
            suffix = path.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            mime = mime_map.get(suffix, "image/jpeg")

            prompt = (
                f"[Image: data:{mime};base64,{b64}]\n"
                "Describe this image concisely in 1-2 sentences. "
                "Focus on the main subject and any text visible."
            )
            provider = get_default_provider(role="chat")
            result = provider.invoke(prompt)
            if result.strip():
                return result.strip()[:500]
        except (FileNotFoundError, RuntimeError, OSError):
            pass

        return "image received (description unavailable)"

    def _extract_pdf_text(self, path: Path) -> str:
        """Extract text from a PDF file."""
        # Try pdftotext (poppler-utils)
        try:
            import subprocess

            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()[:10000]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try PyPDF2 if available
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(path))
            text_parts = []
            for page in reader.pages[:20]:  # Max 20 pages
                text_parts.append(page.extract_text() or "")
            text = "\n".join(text_parts).strip()
            if text:
                return text[:10000]
        except (ImportError, Exception):
            pass

        return "(PDF text extraction unavailable)"
