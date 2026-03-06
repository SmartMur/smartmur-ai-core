"""CLI commands for Security Sentinel: claw security scan|report|fix."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group("security")
def security_group() -> None:
    """Security Sentinel — brutal security scanning and patching."""


@security_group.command("scan")
@click.option("--project-root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Project root to scan (default: cwd)")
@click.option("--format", "output_format", type=click.Choice(["markdown", "json", "sarif"]),
              default="markdown", help="Output format")
@click.option("--offline", is_flag=True, help="Skip OSV API queries")
@click.option("--skip-docker", is_flag=True, help="Skip Docker checks")
@click.option("--skip-code", is_flag=True, help="Skip static analysis")
@click.option("--skip-deps", is_flag=True, help="Skip dependency CVE scan")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None,
              help="Write report to file")
def scan_cmd(
    project_root: Path | None,
    output_format: str,
    offline: bool,
    skip_docker: bool,
    skip_code: bool,
    skip_deps: bool,
    output: Path | None,
) -> None:
    """Run a full security scan."""
    from superpowers.security_sentinel import run_scan

    with console.status("[bold green]Running Security Sentinel scan..."):
        text, exit_code = run_scan(
            project_root,
            offline=offline,
            skip_docker=skip_docker,
            skip_code=skip_code,
            skip_deps=skip_deps,
            output_format=output_format,
        )

    if output:
        output.write_text(text)
        console.print(f"[green]Report written to {output}")
    else:
        console.print(text)

    if exit_code == 0:
        console.print("\n[bold green]All clear.")
    elif exit_code == 1:
        console.print("\n[bold yellow]Warnings found.")
    else:
        console.print("\n[bold red]Critical/high severity findings detected!")

    raise SystemExit(exit_code)


@security_group.command("report")
@click.option("--format", "output_format", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Output format")
def report_cmd(output_format: str) -> None:
    """Show the last security scan report."""
    from superpowers.security_sentinel import get_last_report

    text = get_last_report(output_format)
    if text is None:
        console.print("[yellow]No previous report found. Run 'claw security scan' first.")
        raise SystemExit(1)
    console.print(text)


@security_group.command("fix")
@click.option("--project-root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Project root (default: cwd)")
@click.option("--apply", is_flag=True, help="Actually apply fixes (default is dry-run)")
def fix_cmd(project_root: Path | None, apply: bool) -> None:
    """Auto-apply safe security fixes (dependency upgrades)."""
    from superpowers.security_sentinel import auto_fix

    with console.status("[bold green]Analyzing fixes..."):
        result = auto_fix(project_root, dry_run=not apply)

    console.print(result)
