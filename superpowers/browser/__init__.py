"""Browser automation — Playwright-based navigation, screenshots, and DOM extraction."""

from superpowers.browser.base import BrowserConfig, BrowserError, ElementData, PageResult
from superpowers.browser.engine import BrowserEngine
from superpowers.browser.profiles import ProfileManager

__all__ = [
    "BrowserConfig",
    "BrowserEngine",
    "BrowserError",
    "ElementData",
    "PageResult",
    "ProfileManager",
]
