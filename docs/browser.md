# Browser Automation

Playwright-based browser automation for navigating pages, taking screenshots, extracting content, and running JavaScript.

## Prerequisites

```bash
pip install playwright
playwright install chromium
```

## CLI Commands

### Open a URL

```bash
claw browse open https://example.com
claw browse open https://example.com --headed --profile mysite
```

Opens the URL, prints the page title and URL, and saves a screenshot.

### Screenshot

```bash
claw browse screenshot https://example.com
claw browse screenshot https://example.com --selector "#main" --output page.png
```

Takes a full-page screenshot, or a screenshot of a specific element with `--selector`.

### Extract Text

```bash
claw browse extract https://example.com
claw browse extract https://example.com --selector "h1"
```

Extracts inner text from the page body or a specific CSS selector.

### Extract Table

```bash
claw browse table https://example.com/data
claw browse table https://example.com --selector "#results"
```

Parses an HTML table and displays it as a Rich formatted table. First row is used as headers.

### Evaluate JavaScript

```bash
claw browse js https://example.com "document.title"
claw browse js https://example.com "document.querySelectorAll('a').length"
```

Runs JavaScript on the page and prints the result.

### Manage Profiles

```bash
claw browse profiles              # list saved profiles
claw browse profiles delete NAME  # delete a profile
```

## Global Options

All `browse` commands accept:

- `--profile NAME` — Use a named browser profile for persistent sessions (cookies, localStorage). Defaults to `"default"`.
- `--headed` — Launch a visible browser window instead of headless.

## Python API

```python
from superpowers.browser import BrowserConfig, BrowserEngine

config = BrowserConfig(headless=False, profile_name="mysite")

with BrowserEngine(config=config) as engine:
    result = engine.goto("https://example.com")
    print(result.title)

    # Screenshot
    path = engine.screenshot("/tmp/page.png")

    # Extract text
    text = engine.extract_text("h1")

    # Extract table
    rows = engine.extract_table("table.data")

    # Fill a form
    engine.fill_form({"#username": "admin", "#password": "secret"})
    engine.click("#submit")

    # Run JavaScript
    count = engine.evaluate("document.querySelectorAll('a').length")
```

## Profile Management

```python
from superpowers.browser import ProfileManager

pm = ProfileManager()
profiles = pm.list_profiles()        # ["default", "mysite"]
path = pm.profile_path("mysite")     # creates if needed
pm.delete_profile("old-profile")     # removes profile directory
```

## Data Classes

- `BrowserConfig` — headless, profile_name, timeout, viewport_width, viewport_height
- `PageResult` — url, title, screenshot_path, content, ok, error
- `ElementData` — tag, text, attributes
- `BrowserError` — raised on browser operation failures

## File Locations

- Profiles: `~/.claude-superpowers/browser/profiles/`
- Screenshots: temp files by default, or specify `--output`
