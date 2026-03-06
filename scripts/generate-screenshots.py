#!/usr/bin/env python3
"""generate-screenshots.py — Capture dashboard screenshots for README/docs.

Uses Playwright if available, otherwise falls back to a simple urllib-based
HTML snapshot. Handles the case where the dashboard isn't running.

Usage:
    .venv/bin/python scripts/generate-screenshots.py
    .venv/bin/python scripts/generate-screenshots.py --base-url http://localhost:8200
    .venv/bin/python scripts/generate-screenshots.py --output-dir assets/screenshots
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "assets" / "screenshots"
DEFAULT_BASE_URL = "http://localhost:8200"

# Dashboard routes to capture (path, filename, description)
ROUTES: list[tuple[str, str, str]] = [
    ("/", "dashboard-main.png", "Main dashboard page"),
    ("/login.html", "dashboard-login.png", "Login page"),
    ("/health", "dashboard-health.json", "Health endpoint (JSON)"),
]

# API routes (require auth token)
API_ROUTES: list[tuple[str, str, str]] = [
    ("/api/status", "api-status.json", "System status API"),
    ("/api/skills", "api-skills.json", "Skills list API"),
    ("/api/cron", "api-cron.json", "Cron jobs API"),
]


def check_dashboard_running(base_url: str) -> bool:
    """Check if the dashboard is reachable."""
    try:
        req = urllib.request.Request(f"{base_url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok"
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return False


def get_auth_token(base_url: str) -> str | None:
    """Obtain a JWT token from the dashboard login endpoint."""
    user = os.environ.get("DASHBOARD_USER", "")
    password = os.environ.get("DASHBOARD_PASS", "")
    if not user or not password:
        print("  [SKIP] DASHBOARD_USER/DASHBOARD_PASS not set, skipping auth routes")
        return None
    try:
        payload = json.dumps({"username": user, "password": password}).encode()
        req = urllib.request.Request(
            f"{base_url}/auth/login",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("access_token")
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"  [WARN] Could not obtain auth token: {exc}")
        return None


def capture_with_playwright(
    base_url: str, output_dir: Path, token: str | None
) -> None:
    """Use Playwright to take real browser screenshots."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [SKIP] Playwright not installed. Install with: pip install playwright")
        print("         Then run: playwright install chromium")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        for route, filename, desc in ROUTES:
            url = f"{base_url}{route}"
            try:
                print(f"  Capturing {desc} ({url}) ...")
                page.goto(url, wait_until="networkidle", timeout=10000)
                if filename.endswith(".png"):
                    page.screenshot(path=str(output_dir / filename), full_page=True)
                else:
                    content = page.content()
                    (output_dir / filename).write_text(content)
                print(f"    -> Saved {filename}")
            except Exception as exc:
                print(f"    [FAIL] {desc}: {exc}")

        # API routes with auth
        if token:
            for route, filename, desc in API_ROUTES:
                url = f"{base_url}{route}"
                try:
                    print(f"  Fetching {desc} ({url}) ...")
                    resp = page.request.get(
                        url,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    data = resp.json()
                    (output_dir / filename).write_text(
                        json.dumps(data, indent=2) + "\n"
                    )
                    print(f"    -> Saved {filename}")
                except Exception as exc:
                    print(f"    [FAIL] {desc}: {exc}")

        browser.close()


def capture_with_urllib(base_url: str, output_dir: Path, token: str | None) -> None:
    """Fallback: fetch pages as raw HTML/JSON using urllib."""
    print("  Using urllib fallback (no browser screenshots, just HTML/JSON).")

    for route, filename, desc in ROUTES:
        url = f"{base_url}{route}"
        out_file = filename.replace(".png", ".html")
        try:
            print(f"  Fetching {desc} ({url}) ...")
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                (output_dir / out_file).write_text(content)
                print(f"    -> Saved {out_file}")
        except (urllib.error.URLError, OSError) as exc:
            print(f"    [FAIL] {desc}: {exc}")

    if token:
        headers = {"Authorization": f"Bearer {token}"}
        for route, filename, desc in API_ROUTES:
            url = f"{base_url}{route}"
            try:
                print(f"  Fetching {desc} ({url}) ...")
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    (output_dir / filename).write_text(
                        json.dumps(data, indent=2) + "\n"
                    )
                    print(f"    -> Saved {filename}")
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                print(f"    [FAIL] {desc}: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture dashboard screenshots for docs"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Dashboard base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--force-urllib",
        action="store_true",
        help="Force urllib fallback even if Playwright is available",
    )
    args = parser.parse_args(argv)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Screenshot generator")
    print(f"  Dashboard URL: {args.base_url}")
    print(f"  Output dir:    {output_dir}")
    print()

    if not check_dashboard_running(args.base_url):
        print(
            f"[SKIP] Dashboard is not running at {args.base_url}. "
            f"Start it with: claw dashboard --port 8200"
        )
        print("No screenshots captured.")
        return 1

    print("[OK] Dashboard is running.")
    token = get_auth_token(args.base_url)

    use_playwright = not args.force_urllib
    if use_playwright:
        try:
            import playwright  # noqa: F401

            capture_with_playwright(args.base_url, output_dir, token)
        except ImportError:
            print("  Playwright not available, using urllib fallback.")
            capture_with_urllib(args.base_url, output_dir, token)
    else:
        capture_with_urllib(args.base_url, output_dir, token)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
