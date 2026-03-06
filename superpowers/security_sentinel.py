"""Security Sentinel CLI integration — wraps skills/security-sentinel/run.py for `claw security` commands."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "security-sentinel"
RUN_SCRIPT = SKILL_DIR / "run.py"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "reports"


@click.group("security")
def security_cli():
    """Security Sentinel — CVE scanning, code analysis, Docker hardening."""
    pass


@security_cli.command("scan")
@click.option("--format", "fmt", type=click.Choice(["json", "markdown", "text"]), default="text")
@click.option("--output", "output_path", type=click.Path(), default=None)
@click.option("--project-root", type=click.Path(exists=True), default=".")
def scan(fmt: str, output_path: str | None, project_root: str):
    """Run a full security scan."""
    if not RUN_SCRIPT.exists():
        console.print("[red]Security Sentinel skill not found.[/red]")
        sys.exit(1)

    cmd = [sys.executable, str(RUN_SCRIPT), "--format", fmt, "--project-root", project_root]
    if output_path:
        cmd.extend(["--output", output_path])

    console.print("[bold]Running Security Sentinel scan...[/bold]")
    result = subprocess.run(cmd, capture_output=fmt != "text", text=True)

    if fmt != "text" and output_path:
        console.print(f"[green]Report written to {output_path}[/green]")
    elif fmt != "text" and result.stdout:
        console.print(result.stdout)

    if result.returncode == 2:
        console.print("[bold red]CRITICAL findings detected![/bold red]")
    elif result.returncode == 1:
        console.print("[yellow]Warnings found.[/yellow]")
    else:
        console.print("[green]All clear.[/green]")

    sys.exit(result.returncode)


@security_cli.command("report")
def report():
    """Display the latest security scan report."""
    reports = sorted(REPORTS_DIR.glob("cve-audit-*.md"), reverse=True)
    if not reports:
        console.print("[yellow]No reports found. Run `claw security scan` first.[/yellow]")
        return
    console.print(f"[bold]Latest report:[/bold] {reports[0].name}\n")
    console.print(reports[0].read_text())


@security_cli.command("fix")
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--project-root", type=click.Path(exists=True), default=".")
def fix(dry_run: bool, project_root: str):
    """Auto-apply safe dependency fixes."""
    console.print("[bold]Scanning for auto-fixable issues...[/bold]")

    cmd = [sys.executable, str(RUN_SCRIPT), "--format", "json", "--project-root", project_root]
    result = subprocess.run(cmd, capture_output=True, text=True)

    try:
        data = json.loads(result.stdout) if result.stdout else {"findings": []}
    except json.JSONDecodeError:
        console.print("[red]Failed to parse scan results.[/red]")
        return

    fixable = [f for f in data.get("findings", []) if f.get("fix")]
    if not fixable:
        console.print("[green]No auto-fixable issues found.[/green]")
        return

    table = Table(title="Auto-fixable Issues")
    table.add_column("Severity", style="bold")
    table.add_column("Finding")
    table.add_column("Fix")
    for f in fixable:
        sev = f["severity"]
        style = {"CRITICAL": "red", "HIGH": "bright_red", "MEDIUM": "yellow"}.get(sev, "white")
        table.add_row(f"[{style}]{sev}[/{style}]", f["title"], f["fix"])
    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run — no changes applied.[/yellow]")
        return

    pyproject = Path(project_root) / "pyproject.toml"
    if not pyproject.exists():
        console.print("[yellow]No pyproject.toml found.[/yellow]")
        return

    content = pyproject.read_text()
    applied = 0
    for f in fixable:
        fix_text = f.get("fix", "")
        if "upgrade" in fix_text.lower() and ">=" in fix_text:
            parts = fix_text.split()
            for i, p in enumerate(parts):
                if ">=" in p:
                    pkg = parts[i - 2] if i >= 2 else parts[1]
                    new_ver = p.strip('"').strip("'")
                    pattern = rf'"{re.escape(pkg)}>=[^"]*"'
                    replacement = f'"{pkg}{new_ver}"'
                    new_content = re.sub(pattern, replacement, content)
                    if new_content != content:
                        content = new_content
                        applied += 1
                        console.print(f"  [green]Fixed:[/green] {pkg} -> {new_ver}")
                    break

    if applied > 0:
        pyproject.write_text(content)
        console.print(f"\n[green]{applied} dependency fixes applied to pyproject.toml[/green]")
