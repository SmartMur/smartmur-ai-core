"""Tests for browser automation module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from superpowers.browser.base import BrowserConfig, BrowserError, ElementData, PageResult
from superpowers.browser.engine import BrowserEngine
from superpowers.browser.profiles import ProfileManager

# ---------------------------------------------------------------------------
# TestBrowserConfig
# ---------------------------------------------------------------------------


class TestBrowserConfig:
    def test_defaults(self):
        cfg = BrowserConfig()
        assert cfg.headless is True
        assert cfg.profile_name == "default"
        assert cfg.timeout == 30000
        assert cfg.viewport_width == 1280
        assert cfg.viewport_height == 720

    def test_custom_values(self):
        cfg = BrowserConfig(
            headless=False,
            profile_name="mysite",
            timeout=60000,
            viewport_width=1920,
            viewport_height=1080,
        )
        assert cfg.headless is False
        assert cfg.profile_name == "mysite"
        assert cfg.timeout == 60000
        assert cfg.viewport_width == 1920
        assert cfg.viewport_height == 1080


# ---------------------------------------------------------------------------
# TestPageResult
# ---------------------------------------------------------------------------


class TestPageResult:
    def test_defaults(self):
        r = PageResult(url="https://example.com", title="Example")
        assert r.url == "https://example.com"
        assert r.title == "Example"
        assert r.screenshot_path == ""
        assert r.content == ""
        assert r.ok is True
        assert r.error == ""

    def test_error_result(self):
        r = PageResult(url="https://bad.com", title="", ok=False, error="timeout")
        assert r.ok is False
        assert r.error == "timeout"

    def test_with_screenshot(self):
        r = PageResult(
            url="https://example.com",
            title="Example",
            screenshot_path="/tmp/shot.png",
        )
        assert r.screenshot_path == "/tmp/shot.png"

    def test_with_content(self):
        r = PageResult(
            url="https://example.com",
            title="Example",
            content="<html>hello</html>",
        )
        assert r.content == "<html>hello</html>"


# ---------------------------------------------------------------------------
# TestElementData
# ---------------------------------------------------------------------------


class TestElementData:
    def test_defaults(self):
        e = ElementData(tag="div", text="hello")
        assert e.tag == "div"
        assert e.text == "hello"
        assert e.attributes == {}

    def test_with_attributes(self):
        e = ElementData(tag="a", text="click me", attributes={"href": "/page", "class": "link"})
        assert e.attributes["href"] == "/page"
        assert e.attributes["class"] == "link"

    def test_empty_text(self):
        e = ElementData(tag="br", text="")
        assert e.text == ""


# ---------------------------------------------------------------------------
# TestBrowserError
# ---------------------------------------------------------------------------


class TestBrowserError:
    def test_is_exception(self):
        exc = BrowserError("something broke")
        assert isinstance(exc, Exception)
        assert str(exc) == "something broke"


# ---------------------------------------------------------------------------
# TestProfileManager
# ---------------------------------------------------------------------------


class TestProfileManager:
    def test_list_empty(self, tmp_path):
        pm = ProfileManager(profiles_dir=tmp_path / "profiles")
        assert pm.list_profiles() == []

    def test_list_profiles(self, tmp_path):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "default").mkdir()
        (profiles_dir / "work").mkdir()
        (profiles_dir / "personal").mkdir()

        pm = ProfileManager(profiles_dir=profiles_dir)
        result = pm.list_profiles()
        assert result == ["default", "personal", "work"]

    def test_list_ignores_files(self, tmp_path):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "default").mkdir()
        (profiles_dir / "some_file.txt").write_text("not a profile")

        pm = ProfileManager(profiles_dir=profiles_dir)
        assert pm.list_profiles() == ["default"]

    def test_delete_profile(self, tmp_path):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        profile = profiles_dir / "old"
        profile.mkdir()
        (profile / "cookies.db").write_text("data")

        pm = ProfileManager(profiles_dir=profiles_dir)
        pm.delete_profile("old")
        assert not profile.exists()

    def test_delete_nonexistent_raises(self, tmp_path):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        pm = ProfileManager(profiles_dir=profiles_dir)
        with pytest.raises(BrowserError, match="Profile not found"):
            pm.delete_profile("ghost")

    def test_profile_path_creates_directory(self, tmp_path):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        pm = ProfileManager(profiles_dir=profiles_dir)
        path = pm.profile_path("newprofile")

        assert path.exists()
        assert path.is_dir()
        assert path.name == "newprofile"

    def test_profile_path_existing(self, tmp_path):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "existing").mkdir()

        pm = ProfileManager(profiles_dir=profiles_dir)
        path = pm.profile_path("existing")
        assert path.exists()

    def test_constructor_creates_profiles_dir(self, tmp_path):
        profiles_dir = tmp_path / "new_profiles_dir"
        assert not profiles_dir.exists()

        ProfileManager(profiles_dir=profiles_dir)
        assert profiles_dir.exists()


# ---------------------------------------------------------------------------
# Playwright mocking helpers
# ---------------------------------------------------------------------------


def _mock_playwright():
    """Build a mock playwright sync_api module."""
    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_page.title.return_value = "Example Domain"

    mock_response = MagicMock()
    mock_response.ok = True

    mock_page.goto.return_value = mock_response

    mock_context = MagicMock()
    mock_context.pages = [mock_page]

    mock_browser_type = MagicMock()
    mock_browser_type.launch_persistent_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium = mock_browser_type

    mock_sync_playwright = MagicMock()
    mock_sync_playwright.return_value.start.return_value = mock_pw

    return mock_sync_playwright, mock_pw, mock_context, mock_page


# ---------------------------------------------------------------------------
# TestBrowserEngine
# ---------------------------------------------------------------------------


class TestBrowserEngine:
    def test_start_stop(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                engine = BrowserEngine(profiles_dir=tmp_path)
                engine.start()

                assert engine._page is mock_page
                assert engine._playwright is mock_pw

                engine.stop()
                mock_ctx.close.assert_called_once()
                mock_pw.stop.assert_called_once()

    def test_context_manager(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    assert engine._page is mock_page

                mock_ctx.close.assert_called_once()

    def test_goto_success(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    result = engine.goto("https://example.com")

        assert result.ok is True
        assert result.url == "https://example.com"
        assert result.title == "Example Domain"
        mock_page.goto.assert_called_with("https://example.com", wait_until="domcontentloaded")

    def test_goto_failure(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_page.goto.side_effect = Exception("net::ERR_CONNECTION_REFUSED")

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    result = engine.goto("https://bad.com")

        assert result.ok is False
        assert "ERR_CONNECTION_REFUSED" in result.error

    def test_goto_response_not_ok(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_response = MagicMock()
        mock_response.ok = False
        mock_page.goto.return_value = mock_response

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    result = engine.goto("https://example.com/404")

        assert result.ok is False

    def test_screenshot_default_path(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    path = engine.screenshot()

        assert path.endswith(".png")
        assert "claw-screenshot" in path
        mock_page.screenshot.assert_called_once()

    def test_screenshot_custom_path(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        output = str(tmp_path / "shot.png")

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    path = engine.screenshot(output)

        assert path == output
        mock_page.screenshot.assert_called_once_with(path=output, full_page=True)

    def test_screenshot_element(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_locator = MagicMock()
        mock_page.locator.return_value.first = mock_locator

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    path = engine.screenshot_element("#main")

        assert path.endswith(".png")
        mock_page.locator.assert_called_with("#main")
        mock_locator.screenshot.assert_called_once()

    def test_screenshot_element_custom_path(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_locator = MagicMock()
        mock_page.locator.return_value.first = mock_locator
        output = str(tmp_path / "elem.png")

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    path = engine.screenshot_element("#main", path=output)

        assert path == output
        mock_locator.screenshot.assert_called_once_with(path=output)

    def test_extract_text(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_page.locator.return_value.first.inner_text.return_value = "Hello World"

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    text = engine.extract_text("h1")

        assert text == "Hello World"
        mock_page.locator.assert_called_with("h1")

    def test_extract_text_default_selector(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_page.locator.return_value.first.inner_text.return_value = "page body"

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    engine.extract_text()

        mock_page.locator.assert_called_with("body")

    def test_extract_table(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()

        # Build mock table structure
        mock_table = MagicMock()
        mock_tr_locator = MagicMock()
        mock_tr_locator.count.return_value = 3

        # Row 0: headers
        header_cells = MagicMock()
        header_cells.count.return_value = 2
        header_cells.nth.side_effect = lambda j: MagicMock(
            inner_text=MagicMock(return_value=["Name", "Age"][j])
        )

        # Row 1
        row1_cells = MagicMock()
        row1_cells.count.return_value = 2
        row1_cells.nth.side_effect = lambda j: MagicMock(
            inner_text=MagicMock(return_value=["Alice", "30"][j])
        )

        # Row 2
        row2_cells = MagicMock()
        row2_cells.count.return_value = 2
        row2_cells.nth.side_effect = lambda j: MagicMock(
            inner_text=MagicMock(return_value=["Bob", "25"][j])
        )

        mock_rows = [MagicMock(), MagicMock(), MagicMock()]
        mock_rows[0].locator.return_value = header_cells
        mock_rows[1].locator.return_value = row1_cells
        mock_rows[2].locator.return_value = row2_cells

        mock_tr_locator.nth.side_effect = lambda i: mock_rows[i]
        mock_table.locator.return_value = mock_tr_locator

        mock_page.locator.return_value.first = mock_table

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    rows = engine.extract_table("table.data")

        assert len(rows) == 3
        assert rows[0] == ["Name", "Age"]
        assert rows[1] == ["Alice", "30"]
        assert rows[2] == ["Bob", "25"]

    def test_extract_table_default_selector(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_table = MagicMock()
        mock_tr = MagicMock()
        mock_tr.count.return_value = 0
        mock_table.locator.return_value = mock_tr
        mock_page.locator.return_value.first = mock_table

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    rows = engine.extract_table()

        assert rows == []
        mock_page.locator.assert_called_with("table")

    def test_fill_form(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    engine.fill_form({"#user": "admin", "#pass": "secret"})

        mock_page.fill.assert_any_call("#user", "admin")
        mock_page.fill.assert_any_call("#pass", "secret")
        assert mock_page.fill.call_count == 2

    def test_click(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    engine.click("#submit")

        mock_page.click.assert_called_once_with("#submit")
        mock_page.wait_for_load_state.assert_called_once_with("domcontentloaded", timeout=5000)

    def test_click_wait_timeout_ignored(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_page.wait_for_load_state.side_effect = Exception("timeout")

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    engine.click("#btn")  # should not raise

        mock_page.click.assert_called_once_with("#btn")

    def test_evaluate(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_page.evaluate.return_value = 42

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    result = engine.evaluate("document.querySelectorAll('a').length")

        assert result == "42"
        mock_page.evaluate.assert_called_once_with("document.querySelectorAll('a').length")

    def test_evaluate_string_result(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_page.evaluate.return_value = "Example Domain"

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    result = engine.evaluate("document.title")

        assert result == "Example Domain"

    def test_current_url(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_page.url = "https://example.com/page"

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    assert engine.current_url == "https://example.com/page"

    def test_current_title(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_page.title.return_value = "My Page"

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                with BrowserEngine(profiles_dir=tmp_path) as engine:
                    assert engine.current_title == "My Page"

    def test_ensure_page_raises_when_not_started(self):
        engine = BrowserEngine()
        with pytest.raises(BrowserError, match="Browser not started"):
            engine._ensure_page()

    def test_playwright_import_error(self, tmp_path):
        engine = BrowserEngine(profiles_dir=tmp_path)

        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            with pytest.raises(BrowserError, match="playwright is required"):
                engine.start()

    def test_config_passed_to_launch(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        config = BrowserConfig(
            headless=False,
            profile_name="mysite",
            timeout=60000,
            viewport_width=1920,
            viewport_height=1080,
        )

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                engine = BrowserEngine(config=config, profiles_dir=tmp_path)
                engine.start()

        launch_kwargs = mock_pw.chromium.launch_persistent_context.call_args
        assert launch_kwargs[1]["headless"] is False
        assert launch_kwargs[1]["viewport"] == {"width": 1920, "height": 1080}
        assert str(tmp_path / "mysite") in launch_kwargs[1]["user_data_dir"]
        mock_ctx.set_default_timeout.assert_called_once_with(60000)

        engine.stop()

    def test_stop_idempotent(self, tmp_path):
        engine = BrowserEngine(profiles_dir=tmp_path)
        # Calling stop when not started should not raise
        engine.stop()
        engine.stop()

    def test_new_page_created_when_no_pages(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_ctx.pages = []  # No existing pages
        new_page = MagicMock()
        mock_ctx.new_page.return_value = new_page

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                engine = BrowserEngine(profiles_dir=tmp_path)
                engine.start()

        assert engine._page is new_page
        mock_ctx.new_page.assert_called_once()

        engine.stop()

    def test_stop_handles_close_exceptions(self, tmp_path):
        mock_sync, mock_pw, mock_ctx, mock_page = _mock_playwright()
        mock_ctx.close.side_effect = Exception("already closed")
        mock_pw.stop.side_effect = Exception("already stopped")

        with patch("superpowers.browser.engine.sync_playwright", mock_sync, create=True):
            with patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(sync_playwright=mock_sync),
                },
            ):
                engine = BrowserEngine(profiles_dir=tmp_path)
                engine.start()
                engine.stop()  # Should not raise

        assert engine._context is None
        assert engine._playwright is None
