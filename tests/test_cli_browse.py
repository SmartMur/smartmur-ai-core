"""Tests for CLI browse subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_browse import (
    browse_group,
)


def _make_engine_mock(ok=True, title="Test Page", url="https://example.com"):
    """Return a MagicMock that behaves like BrowserEngine with context manager."""
    engine = MagicMock()
    engine.__enter__ = MagicMock(return_value=engine)
    engine.__exit__ = MagicMock(return_value=False)

    result = MagicMock()
    result.ok = ok
    result.title = title
    result.url = url
    result.error = "navigation failed" if not ok else ""
    engine.goto.return_value = result

    engine.screenshot.return_value = "/tmp/screenshot.png"
    engine.screenshot_element.return_value = "/tmp/element.png"
    engine.extract_text.return_value = "Hello World"
    engine.extract_table.return_value = [["Name", "Value"], ["a", "1"], ["b", "2"]]
    engine.evaluate.return_value = "42"
    return engine


# --- browse open ---


@patch("superpowers.cli_browse._engine")
def test_browse_open_happy_path(mock_engine_fn):
    engine = _make_engine_mock()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["open", "https://example.com"])
    assert result.exit_code == 0
    assert "Test Page" in result.output
    assert "https://example.com" in result.output
    assert "screenshot.png" in result.output


@patch("superpowers.cli_browse._engine")
def test_browse_open_navigation_failure(mock_engine_fn):
    engine = _make_engine_mock(ok=False)
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["open", "https://bad.example.com"])
    assert result.exit_code != 0
    assert "Error" in result.output


@patch("superpowers.cli_browse._engine")
def test_browse_open_browser_error(mock_engine_fn):
    from superpowers.browser.base import BrowserError

    engine = MagicMock()
    engine.__enter__ = MagicMock(side_effect=BrowserError("cannot start"))
    engine.__exit__ = MagicMock(return_value=False)
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["open", "https://example.com"])
    assert result.exit_code != 0
    assert "cannot start" in result.output


@patch("superpowers.cli_browse._engine")
def test_browse_open_with_profile_and_headed(mock_engine_fn):
    engine = _make_engine_mock()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(
        browse_group, ["open", "https://example.com", "--profile", "work", "--headed"]
    )
    assert result.exit_code == 0
    mock_engine_fn.assert_called_once_with("work", True)


# --- browse screenshot ---


@patch("superpowers.cli_browse._engine")
def test_browse_screenshot_full_page(mock_engine_fn):
    engine = _make_engine_mock()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["screenshot", "https://example.com"])
    assert result.exit_code == 0
    assert "Saved" in result.output
    engine.screenshot.assert_called_once_with(path=None)


@patch("superpowers.cli_browse._engine")
def test_browse_screenshot_with_selector(mock_engine_fn):
    engine = _make_engine_mock()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(
        browse_group, ["screenshot", "https://example.com", "-s", "#main", "-o", "out.png"]
    )
    assert result.exit_code == 0
    engine.screenshot_element.assert_called_once_with("#main", path="out.png")


@patch("superpowers.cli_browse._engine")
def test_browse_screenshot_navigation_error(mock_engine_fn):
    engine = _make_engine_mock(ok=False)
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["screenshot", "https://bad.com"])
    assert result.exit_code != 0


# --- browse extract ---


@patch("superpowers.cli_browse._engine")
def test_browse_extract_default_selector(mock_engine_fn):
    engine = _make_engine_mock()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["extract", "https://example.com"])
    assert result.exit_code == 0
    assert "Hello World" in result.output
    engine.extract_text.assert_called_once_with("body")


@patch("superpowers.cli_browse._engine")
def test_browse_extract_custom_selector(mock_engine_fn):
    engine = _make_engine_mock()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["extract", "https://example.com", "-s", "h1"])
    assert result.exit_code == 0
    engine.extract_text.assert_called_once_with("h1")


# --- browse table ---


@patch("superpowers.cli_browse._engine")
def test_browse_table_with_data(mock_engine_fn):
    engine = _make_engine_mock()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["table", "https://example.com/data"])
    assert result.exit_code == 0
    assert "Name" in result.output
    assert "Value" in result.output


@patch("superpowers.cli_browse._engine")
def test_browse_table_no_data(mock_engine_fn):
    engine = _make_engine_mock()
    engine.extract_table.return_value = []
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["table", "https://example.com/data"])
    assert result.exit_code == 0
    assert "No table data found" in result.output


# --- browse js ---


@patch("superpowers.cli_browse._engine")
def test_browse_js_happy(mock_engine_fn):
    engine = _make_engine_mock()
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["js", "https://example.com", "document.title"])
    assert result.exit_code == 0
    assert "42" in result.output
    engine.evaluate.assert_called_once_with("document.title")


@patch("superpowers.cli_browse._engine")
def test_browse_js_navigation_error(mock_engine_fn):
    engine = _make_engine_mock(ok=False)
    mock_engine_fn.return_value = engine
    runner = CliRunner()
    result = runner.invoke(browse_group, ["js", "https://example.com", "1+1"])
    assert result.exit_code != 0


# --- browse profiles ---


@patch("superpowers.cli_browse.ProfileManager")
def test_browse_profiles_list(mock_pm_cls):
    pm = MagicMock()
    pm.list_profiles.return_value = ["default", "work"]
    mock_pm_cls.return_value = pm
    runner = CliRunner()
    result = runner.invoke(browse_group, ["profiles"])
    assert result.exit_code == 0
    assert "default" in result.output
    assert "work" in result.output


@patch("superpowers.cli_browse.ProfileManager")
def test_browse_profiles_empty(mock_pm_cls):
    pm = MagicMock()
    pm.list_profiles.return_value = []
    mock_pm_cls.return_value = pm
    runner = CliRunner()
    result = runner.invoke(browse_group, ["profiles"])
    assert result.exit_code == 0
    assert "No browser profiles saved" in result.output


@patch("superpowers.cli_browse.ProfileManager")
def test_browse_profiles_delete_ok(mock_pm_cls):
    pm = MagicMock()
    mock_pm_cls.return_value = pm
    runner = CliRunner()
    result = runner.invoke(browse_group, ["profiles", "delete", "old"])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    pm.delete_profile.assert_called_once_with("old")


@patch("superpowers.cli_browse.ProfileManager")
def test_browse_profiles_delete_error(mock_pm_cls):
    from superpowers.browser.base import BrowserError

    pm = MagicMock()
    pm.delete_profile.side_effect = BrowserError("not found")
    mock_pm_cls.return_value = pm
    runner = CliRunner()
    result = runner.invoke(browse_group, ["profiles", "delete", "missing"])
    assert result.exit_code != 0
    assert "not found" in result.output
