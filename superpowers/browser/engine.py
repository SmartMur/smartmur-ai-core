"""Core Playwright wrapper for browser automation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from superpowers.browser.base import BrowserConfig, BrowserError, PageResult

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page, Playwright

try:
    from playwright.sync_api import Error as PlaywrightError
except ImportError:  # pragma: no cover
    PlaywrightError = RuntimeError  # type: ignore[assignment,misc]


class BrowserEngine:
    def __init__(
        self,
        config: BrowserConfig | None = None,
        profiles_dir: Path | None = None,
    ):
        self._config = config or BrowserConfig()
        if profiles_dir is None:
            from superpowers.config import get_data_dir

            profiles_dir = get_data_dir() / "browser" / "profiles"
        self._profiles_dir = profiles_dir
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def start(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserError(
                "playwright is required for browser automation. "
                "Install it with: pip install playwright && playwright install chromium"
            ) from exc

        self._playwright = sync_playwright().start()

        user_data_dir = self._profiles_dir / self._config.profile_name
        user_data_dir.mkdir(parents=True, exist_ok=True)

        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=self._config.headless,
            viewport={
                "width": self._config.viewport_width,
                "height": self._config.viewport_height,
            },
        )
        self._context.set_default_timeout(self._config.timeout)

        # Use existing page or create one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()

    def stop(self) -> None:
        if self._context:
            try:
                self._context.close()
            except (PlaywrightError, OSError, RuntimeError, Exception):  # noqa: BLE001
                # Playwright.Error is a direct Exception subclass
                pass
            self._context = None
            self._page = None
        if self._playwright:
            try:
                self._playwright.stop()
            except (PlaywrightError, OSError, RuntimeError, Exception):  # noqa: BLE001
                # Playwright.Error is a direct Exception subclass
                pass
            self._playwright = None

    def __enter__(self) -> BrowserEngine:
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def _ensure_page(self) -> Page:
        if self._page is None:
            raise BrowserError("Browser not started. Call start() or use as context manager.")
        return self._page

    def goto(self, url: str) -> PageResult:
        page = self._ensure_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded")
            ok = response is not None and response.ok if response else True
            return PageResult(
                url=page.url,
                title=page.title(),
                ok=ok,
            )
        except (PlaywrightError, RuntimeError, OSError, TimeoutError, ValueError) as exc:
            return PageResult(
                url=url,
                title="",
                ok=False,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            # Playwright.Error is a direct Exception subclass — no standard
            # exception type covers all browser navigation failures
            return PageResult(
                url=url,
                title="",
                ok=False,
                error=str(exc),
            )

    def screenshot(self, path: str | None = None) -> str:
        page = self._ensure_page()
        if path is None:
            fd, path = tempfile.mkstemp(suffix=".png", prefix="claw-screenshot-")
            import os

            os.close(fd)
        page.screenshot(path=path, full_page=True)
        return path

    def screenshot_element(self, selector: str, path: str | None = None) -> str:
        page = self._ensure_page()
        if path is None:
            fd, path = tempfile.mkstemp(suffix=".png", prefix="claw-element-")
            import os

            os.close(fd)
        element = page.locator(selector).first
        element.screenshot(path=path)
        return path

    def extract_text(self, selector: str = "body") -> str:
        page = self._ensure_page()
        return page.locator(selector).first.inner_text()

    def extract_table(self, selector: str = "table") -> list[list[str]]:
        page = self._ensure_page()
        rows: list[list[str]] = []
        table = page.locator(selector).first
        tr_elements = table.locator("tr")
        count = tr_elements.count()
        for i in range(count):
            row = tr_elements.nth(i)
            cells = row.locator("th, td")
            cell_count = cells.count()
            row_data = [cells.nth(j).inner_text() for j in range(cell_count)]
            rows.append(row_data)
        return rows

    def fill_form(self, fields: dict[str, str]) -> None:
        page = self._ensure_page()
        for selector, value in fields.items():
            page.fill(selector, value)

    def click(self, selector: str) -> None:
        page = self._ensure_page()
        page.click(selector)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except (PlaywrightError, TimeoutError, RuntimeError, Exception):  # noqa: BLE001
            # Playwright.Error is a direct Exception subclass
            pass

    def evaluate(self, js: str) -> str:
        page = self._ensure_page()
        result = page.evaluate(js)
        return str(result)

    @property
    def current_url(self) -> str:
        page = self._ensure_page()
        return page.url

    @property
    def current_title(self) -> str:
        page = self._ensure_page()
        return page.title()
