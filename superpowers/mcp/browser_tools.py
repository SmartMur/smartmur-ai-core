from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def browse_page(url: str, profile: str = "default") -> str:
        """Navigate to a URL and return the page title plus text content (first 2000 chars). Uses headless Chromium."""
        from superpowers.browser.base import BrowserConfig
        from superpowers.browser.engine import BrowserEngine

        try:
            with BrowserEngine(BrowserConfig(headless=True, profile_name=profile)) as engine:
                result = engine.goto(url)
                if not result.ok:
                    return f"Failed to load {url}: {result.error}"
                text = engine.extract_text("body")
                truncated = text[:2000] if len(text) > 2000 else text
                return f"Title: {result.title}\nURL: {result.url}\n\n{truncated}"
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            return f"Error browsing {url}: {exc}"

    @mcp.tool()
    def browse_screenshot(url: str, selector: str = "", profile: str = "default") -> str:
        """Navigate to a URL and take a screenshot. If selector is provided, captures only that element. Returns the screenshot file path."""
        from superpowers.browser.base import BrowserConfig
        from superpowers.browser.engine import BrowserEngine

        try:
            with BrowserEngine(BrowserConfig(headless=True, profile_name=profile)) as engine:
                result = engine.goto(url)
                if not result.ok:
                    return f"Failed to load {url}: {result.error}"
                if selector:
                    path = engine.screenshot_element(selector)
                else:
                    path = engine.screenshot()
                return f"Screenshot saved: {path}"
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            return f"Error taking screenshot of {url}: {exc}"

    @mcp.tool()
    def browse_extract(url: str, selector: str = "body") -> str:
        """Navigate to a URL and extract text content from a CSS selector."""
        from superpowers.browser.base import BrowserConfig
        from superpowers.browser.engine import BrowserEngine

        try:
            with BrowserEngine(BrowserConfig(headless=True, profile_name="default")) as engine:
                result = engine.goto(url)
                if not result.ok:
                    return f"Failed to load {url}: {result.error}"
                text = engine.extract_text(selector)
                return text
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            return f"Error extracting from {url}: {exc}"

    @mcp.tool()
    def browse_extract_table(url: str, selector: str = "table") -> str:
        """Navigate to a URL and extract an HTML table as formatted text."""
        from superpowers.browser.base import BrowserConfig
        from superpowers.browser.engine import BrowserEngine

        try:
            with BrowserEngine(BrowserConfig(headless=True, profile_name="default")) as engine:
                result = engine.goto(url)
                if not result.ok:
                    return f"Failed to load {url}: {result.error}"
                rows = engine.extract_table(selector)
                if not rows:
                    return "No table data found."
                # Calculate column widths for alignment
                col_widths = [
                    max(len(row[i]) if i < len(row) else 0 for row in rows)
                    for i in range(max(len(r) for r in rows))
                ]
                lines = []
                for idx, row in enumerate(rows):
                    padded = [
                        cell.ljust(col_widths[j]) if j < len(col_widths) else cell
                        for j, cell in enumerate(row)
                    ]
                    lines.append("  ".join(padded))
                    if idx == 0:
                        lines.append("  ".join("─" * w for w in col_widths))
                return "\n".join(lines)
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            return f"Error extracting table from {url}: {exc}"

    @mcp.tool()
    def browse_run_js(url: str, script: str) -> str:
        """Navigate to a URL, execute JavaScript, and return the result."""
        from superpowers.browser.base import BrowserConfig
        from superpowers.browser.engine import BrowserEngine

        try:
            with BrowserEngine(BrowserConfig(headless=True, profile_name="default")) as engine:
                result = engine.goto(url)
                if not result.ok:
                    return f"Failed to load {url}: {result.error}"
                js_result = engine.evaluate(script)
                return f"JS result: {js_result}"
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            return f"Error running JS on {url}: {exc}"

    @mcp.tool()
    def browse_fill_and_submit(
        url: str,
        fields: str,
        submit_selector: str = "",
    ) -> str:
        """Navigate to a URL, fill form fields, and optionally click a submit button.

        fields: JSON string mapping CSS selectors to values, e.g. '{"#username": "admin", "#password": "secret"}'.
        submit_selector: CSS selector of the submit button to click after filling.
        """
        from superpowers.browser.base import BrowserConfig
        from superpowers.browser.engine import BrowserEngine

        try:
            field_map = json.loads(fields)
        except json.JSONDecodeError as exc:
            return f"Invalid fields JSON: {exc}"

        if not isinstance(field_map, dict):
            return "fields must be a JSON object mapping selectors to values."

        try:
            with BrowserEngine(BrowserConfig(headless=True, profile_name="default")) as engine:
                result = engine.goto(url)
                if not result.ok:
                    return f"Failed to load {url}: {result.error}"
                engine.fill_form(field_map)
                if submit_selector:
                    engine.click(submit_selector)
                    return (
                        f"Filled {len(field_map)} field(s) and clicked {submit_selector!r}.\n"
                        f"Current URL: {engine.current_url}\n"
                        f"Current title: {engine.current_title}"
                    )
                return f"Filled {len(field_map)} field(s). No submit selector provided."
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            return f"Error filling form on {url}: {exc}"

    @mcp.tool()
    def list_browser_profiles() -> str:
        """List all saved browser profiles (persistent cookie/session storage)."""
        from superpowers.browser.profiles import ProfileManager

        try:
            pm = ProfileManager()
            profiles = pm.list_profiles()
            if not profiles:
                return "No browser profiles found."
            lines = ["Browser profiles:"]
            for p in profiles:
                lines.append(f"  - {p}")
            return "\n".join(lines)
        except (OSError, RuntimeError) as exc:
            return f"Error listing profiles: {exc}"
