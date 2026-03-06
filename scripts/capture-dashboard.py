#!/usr/bin/env python3
"""Capture dashboard screenshots/snapshots.

Uses urllib to fetch and save HTML snapshots and API JSON when Playwright
browsers are not available (missing system libs).
"""

from __future__ import annotations

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "http://localhost:8200"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "screenshots"
USERNAME = "admin"
PASSWORD = "BCDCdRGMKdRMawM2omIc0NVkIVlQPJMI"


def build_opener() -> urllib.request.OpenerDirector:
    """Build an opener that handles cookies (for session auth)."""
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def login(opener: urllib.request.OpenerDirector) -> bool:
    """Authenticate and store the session cookie."""
    payload = json.dumps({"username": USERNAME, "password": PASSWORD}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener.open(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                print("  Logged in successfully.")
                return True
            print(f"  Login failed: {data.get('error')}")
            return False
    except (urllib.error.URLError, OSError) as exc:
        print(f"  Login error: {exc}")
        return False


def fetch_page(
    opener: urllib.request.OpenerDirector, path: str, filename: str, desc: str
) -> None:
    """Fetch a page and save its content."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, method="GET")
        with opener.open(req, timeout=10) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            outpath = OUTPUT_DIR / filename
            outpath.write_text(content)
            size = len(content)
            print(f"    -> Saved {filename} ({size:,} bytes)")
    except (urllib.error.URLError, OSError) as exc:
        print(f"    [FAIL] {desc}: {exc}")


def fetch_json(
    opener: urllib.request.OpenerDirector, path: str, filename: str, desc: str
) -> None:
    """Fetch a JSON API endpoint and save formatted output."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, method="GET")
        with opener.open(req, timeout=10) as resp:
            raw = resp.read()
            data = json.loads(raw)
            outpath = OUTPUT_DIR / filename
            outpath.write_text(json.dumps(data, indent=2) + "\n")
            print(f"    -> Saved {filename}")
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"    [FAIL] {desc}: {exc}")


def try_playwright(opener_cookie_value: str | None) -> bool:
    """Attempt Playwright-based screenshots. Returns True if successful."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 900})

            # Inject session cookie if we have one
            if opener_cookie_value:
                context.add_cookies([{
                    "name": "claw_session",
                    "value": opener_cookie_value,
                    "domain": "localhost",
                    "path": "/",
                }])

            page = context.new_page()

            # Login page
            page.goto(f"{BASE_URL}/login.html", wait_until="networkidle", timeout=15000)
            page.screenshot(path=str(OUTPUT_DIR / "01-login.png"), full_page=True)
            print("    -> Saved 01-login.png (Playwright)")

            # Login
            page.fill("#username", USERNAME)
            page.fill("#password", PASSWORD)
            page.click('button[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/", timeout=10000)
            page.wait_for_load_state("networkidle", timeout=10000)
            page.wait_for_timeout(1500)

            # Main dashboard
            page.screenshot(path=str(OUTPUT_DIR / "02-dashboard-main.png"), full_page=True)
            print("    -> Saved 02-dashboard-main.png (Playwright)")

            # Nav sections
            nav_links = page.query_selector_all("nav a, .nav-link, .sidebar a, [data-section]")
            if nav_links:
                seen = set()
                idx = 3
                for link in nav_links:
                    text = (link.inner_text() or "").strip()
                    if not text or text in seen or text.lower() in ("login", "logout", "sign out"):
                        continue
                    seen.add(text)
                    try:
                        link.click()
                        page.wait_for_timeout(1000)
                        slug = text.lower().replace(" ", "-").replace("/", "-")[:30]
                        fname = f"{idx:02d}-{slug}.png"
                        page.screenshot(path=str(OUTPUT_DIR / fname), full_page=True)
                        print(f"    -> Saved {fname} ({text})")
                        idx += 1
                    except Exception:
                        pass

            browser.close()
            return True
    except Exception as exc:
        print(f"  Playwright failed ({exc}), falling back to HTML snapshots.")
        return False


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Dashboard screenshot capture")
    print(f"  URL:    {BASE_URL}")
    print(f"  Output: {OUTPUT_DIR}")
    print()

    # Check health
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("status") != "ok":
                print("[FAIL] Dashboard health check failed.")
                return
    except Exception as exc:
        print(f"[FAIL] Dashboard not reachable: {exc}")
        return

    print("[OK] Dashboard is running.")

    # Try Playwright first
    print("\n[1] Attempting Playwright screenshots...")
    if try_playwright(None):
        print("\n  Playwright screenshots captured successfully.")
    else:
        print("\n  Falling back to HTML/JSON snapshots.")

    # Always capture HTML snapshots + API JSON (useful even if Playwright worked)
    opener = build_opener()

    print("\n[2] Capturing HTML snapshots...")

    # Public pages (no auth needed)
    pages_public = [
        ("/login.html", "login-page.html", "Login page"),
        ("/health", "health.json", "Health endpoint"),
    ]
    for path, fname, desc in pages_public:
        print(f"  Fetching {desc}...")
        if fname.endswith(".json"):
            fetch_json(opener, path, fname, desc)
        else:
            fetch_page(opener, path, fname, desc)

    # Login for authenticated pages
    print("\n[3] Authenticating...")
    if not login(opener):
        print("  Could not authenticate. Skipping protected pages.")
        print("\nDone.")
        return

    # Main dashboard (authenticated)
    print("\n[4] Capturing authenticated pages...")
    auth_pages = [
        ("/", "dashboard-main.html", "Main dashboard"),
    ]
    for path, fname, desc in auth_pages:
        print(f"  Fetching {desc}...")
        fetch_page(opener, path, fname, desc)

    # API endpoints
    print("\n[5] Capturing API snapshots...")
    api_endpoints = [
        ("/api/status", "api-status.json", "System status"),
        ("/api/skills", "api-skills.json", "Skills list"),
        ("/api/cron", "api-cron.json", "Cron jobs"),
        ("/api/memory", "api-memory.json", "Memory store"),
        ("/api/workflows", "api-workflows.json", "Workflows"),
        ("/api/agents", "api-agents.json", "Agents"),
    ]
    for path, fname, desc in api_endpoints:
        print(f"  Fetching {desc}...")
        fetch_json(opener, path, fname, desc)

    print("\nDone. All snapshots saved to assets/screenshots/")


if __name__ == "__main__":
    main()
