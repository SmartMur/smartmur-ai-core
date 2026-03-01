"""Base classes for browser automation."""

from __future__ import annotations

from dataclasses import dataclass, field


class BrowserError(Exception):
    """Raised when a browser operation fails."""


@dataclass
class BrowserConfig:
    headless: bool = True
    profile_name: str = "default"
    timeout: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720


@dataclass
class PageResult:
    url: str
    title: str
    screenshot_path: str = ""
    content: str = ""
    ok: bool = True
    error: str = ""


@dataclass
class ElementData:
    tag: str
    text: str
    attributes: dict = field(default_factory=dict)
