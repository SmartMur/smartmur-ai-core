"""Click subcommands for browser automation."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from superpowers.browser.base import BrowserConfig, BrowserError
from superpowers.browser.engine import BrowserEngine
from superpowers.browser.profiles import ProfileManager

console = Console()


def _engine(profile: str, headed: bool) -> BrowserEngine:
    config = BrowserConfig(
        headless=not headed,
        profile_name=profile,
    )
    return BrowserEngine(config=config)


@click.group("browse")
def browse_group():
    """Browser automation — navigate, screenshot, extract data."""


@browse_group.command("open")
@click.argument("url")
@click.option("--profile", default="default", help="Browser profile name.")
@click.option("--headed", is_flag=True, help="Run in headed (visible) mode.")
def browse_open(url: str, profile: str, headed: bool):
    """Open a URL and print page info.

    Example: claw browse open https://example.com
    """
    try:
        with _engine(profile, headed) as engine:
            result = engine.goto(url)
            if not result.ok:
                console.print(f"[bold red]Error:[/bold red] {result.error}")
                raise SystemExit(1)

            screenshot_path = engine.screenshot()
            console.print(f"[cyan]Title:[/cyan] {result.title}")
            console.print(f"[cyan]URL:[/cyan]   {result.url}")
            console.print(f"[cyan]Screenshot:[/cyan] {screenshot_path}")
    except BrowserError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@browse_group.command("screenshot")
@click.argument("url")
@click.option("--selector", "-s", default=None, help="CSS selector for element screenshot.")
@click.option("--output", "-o", default=None, help="Output file path.")
@click.option("--profile", default="default", help="Browser profile name.")
@click.option("--headed", is_flag=True, help="Run in headed (visible) mode.")
def browse_screenshot(
    url: str, selector: str | None, output: str | None, profile: str, headed: bool
):
    """Navigate to a URL and take a screenshot.

    Examples:
      claw browse screenshot https://example.com
      claw browse screenshot https://example.com --selector "#main" --output page.png
    """
    try:
        with _engine(profile, headed) as engine:
            result = engine.goto(url)
            if not result.ok:
                console.print(f"[bold red]Error:[/bold red] {result.error}")
                raise SystemExit(1)

            if selector:
                path = engine.screenshot_element(selector, path=output)
            else:
                path = engine.screenshot(path=output)

            console.print(f"[bold green]Saved:[/bold green] {path}")
    except BrowserError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@browse_group.command("extract")
@click.argument("url")
@click.option("--selector", "-s", default="body", help="CSS selector to extract text from.")
@click.option("--profile", default="default", help="Browser profile name.")
@click.option("--headed", is_flag=True, help="Run in headed (visible) mode.")
def browse_extract(url: str, selector: str, profile: str, headed: bool):
    """Extract text content from a web page.

    Examples:
      claw browse extract https://example.com
      claw browse extract https://example.com --selector "h1"
    """
    try:
        with _engine(profile, headed) as engine:
            result = engine.goto(url)
            if not result.ok:
                console.print(f"[bold red]Error:[/bold red] {result.error}")
                raise SystemExit(1)

            text = engine.extract_text(selector)
            console.print(text)
    except BrowserError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@browse_group.command("table")
@click.argument("url")
@click.option("--selector", "-s", default="table", help="CSS selector for the table.")
@click.option("--profile", default="default", help="Browser profile name.")
@click.option("--headed", is_flag=True, help="Run in headed (visible) mode.")
def browse_table(url: str, selector: str, profile: str, headed: bool):
    """Extract a table from a web page and display it.

    Examples:
      claw browse table https://example.com/data
      claw browse table https://example.com --selector "#results"
    """
    try:
        with _engine(profile, headed) as engine:
            result = engine.goto(url)
            if not result.ok:
                console.print(f"[bold red]Error:[/bold red] {result.error}")
                raise SystemExit(1)

            rows = engine.extract_table(selector)

        if not rows:
            console.print("[dim]No table data found.[/dim]")
            return

        table = Table(title="Extracted Table")

        # Use first row as headers
        for col in rows[0]:
            table.add_column(col, style="cyan")

        for row in rows[1:]:
            table.add_row(*row)

        console.print(table)
    except BrowserError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@browse_group.command("js")
@click.argument("url")
@click.argument("script")
@click.option("--profile", default="default", help="Browser profile name.")
@click.option("--headed", is_flag=True, help="Run in headed (visible) mode.")
def browse_js(url: str, script: str, profile: str, headed: bool):
    """Navigate to a URL and evaluate JavaScript.

    Examples:
      claw browse js https://example.com "document.title"
      claw browse js https://example.com "document.querySelectorAll('a').length"
    """
    try:
        with _engine(profile, headed) as engine:
            result = engine.goto(url)
            if not result.ok:
                console.print(f"[bold red]Error:[/bold red] {result.error}")
                raise SystemExit(1)

            output = engine.evaluate(script)
            console.print(output)
    except BrowserError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)


@browse_group.group("profiles", invoke_without_command=True)
@click.pass_context
def browse_profiles(ctx):
    """Manage browser profiles."""
    if ctx.invoked_subcommand is not None:
        return

    pm = ProfileManager()
    profiles = pm.list_profiles()

    if not profiles:
        console.print("[dim]No browser profiles saved.[/dim]")
        return

    table = Table(title="Browser Profiles")
    table.add_column("Profile", style="cyan")

    for name in profiles:
        table.add_row(name)

    console.print(table)


@browse_profiles.command("delete")
@click.argument("name")
def browse_profiles_delete(name: str):
    """Delete a saved browser profile.

    Example: claw browse profiles delete myprofile
    """
    pm = ProfileManager()
    try:
        pm.delete_profile(name)
        console.print(f"[bold green]Deleted:[/bold green] profile '{name}'")
    except BrowserError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1)
