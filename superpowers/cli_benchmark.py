"""Click subcommands for the benchmark harness."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("benchmark")
def benchmark_group():
    """Run and report on orchestration performance benchmarks."""


@benchmark_group.command("run")
@click.option("--scenario", "-s", default=None, help="Run a specific scenario by name")
@click.option("--parallel", is_flag=True, help="Run scenarios concurrently")
@click.option("--save/--no-save", default=True, show_default=True, help="Save report to disk")
def benchmark_run(scenario: str | None, parallel: bool, save: bool):
    """Run benchmark scenarios and display results."""
    from superpowers.benchmark import SCENARIOS, BenchmarkSuite

    suite = BenchmarkSuite()

    if scenario:
        if scenario not in SCENARIOS:
            console.print(f"[bold red]Unknown scenario:[/bold red] {scenario}")
            console.print(f"Available: {', '.join(sorted(SCENARIOS))}")
            raise SystemExit(1)

        console.print(f"[bold]Running scenario:[/bold] {scenario}")
        result = suite.run_scenario(scenario)

        # Display single result
        table = Table(title=f"Benchmark: {result.name}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        table.add_row("Duration", f"{result.duration_ms:.1f}ms")
        table.add_row("Ops/sec", f"{result.ops_per_sec:.1f}")
        table.add_row("Peak Memory", f"{result.memory_peak_mb:.2f} MB")
        table.add_row("Iterations", str(result.iterations))
        status_style = "green" if result.status == "pass" else "red"
        table.add_row("Status", f"[{status_style}]{result.status}[/{status_style}]")
        if result.error:
            table.add_row("Error", f"[red]{result.error}[/red]")
        console.print(table)
        return

    console.print("[bold]Running all benchmark scenarios...[/bold]")
    if parallel:
        console.print("[dim]Mode: parallel[/dim]")

    if save:
        report, json_path, md_path = suite.run_and_save(parallel=parallel)
        _print_report(report)
        console.print(f"\n[dim]Saved: {json_path}[/dim]")
        console.print(f"[dim]Saved: {md_path}[/dim]")
    else:
        report = suite.run_all(parallel=parallel)
        _print_report(report)

    if not report.all_passed:
        raise SystemExit(1)


@benchmark_group.command("report")
def benchmark_report():
    """Show the last benchmark results."""
    from superpowers.benchmark import BenchmarkSuite

    suite = BenchmarkSuite()
    report = suite.load_last_report()

    if report is None:
        console.print("[dim]No benchmark reports found. Run 'claw benchmark run' first.[/dim]")
        return

    _print_report(report)


@benchmark_group.command("list")
def benchmark_list():
    """List available benchmark scenarios."""
    from superpowers.benchmark import DEFAULT_THRESHOLDS, SCENARIOS

    table = Table(title="Available Benchmark Scenarios")
    table.add_column("Scenario", style="cyan")
    table.add_column("Thresholds")

    for name in sorted(SCENARIOS):
        thresholds = DEFAULT_THRESHOLDS.get(name, {})
        thresh_str = ", ".join(f"{k}={v}" for k, v in thresholds.items()) if thresholds else "-"
        table.add_row(name, thresh_str)

    console.print(table)


def _print_report(report) -> None:
    """Display a benchmark report in the terminal."""
    overall = "[green]PASS[/green]" if report.all_passed else "[red]FAIL[/red]"
    console.print(f"\n[bold]{report.title}[/bold]  {overall}")
    console.print(f"[dim]Duration: {report.total_duration_ms:.1f}ms | Scenarios: {report.scenario_count}[/dim]")

    # Results table
    table = Table()
    table.add_column("Scenario", style="cyan")
    table.add_column("Duration (ms)", justify="right")
    table.add_column("Ops/sec", justify="right")
    table.add_column("Peak MB", justify="right")
    table.add_column("Iterations", justify="right")
    table.add_column("Status")

    for r in report.results:
        status_style = "green" if r.status == "pass" else "red"
        table.add_row(
            r.name,
            f"{r.duration_ms:.1f}",
            f"{r.ops_per_sec:.1f}",
            f"{r.memory_peak_mb:.2f}",
            str(r.iterations),
            f"[{status_style}]{r.status}[/{status_style}]",
        )

    console.print(table)

    # Threshold checks
    if report.threshold_checks:
        console.print("\n[bold]Threshold Checks:[/bold]")
        for tc in report.threshold_checks:
            icon = "[green]PASS[/green]" if tc.passed else "[red]FAIL[/red]"
            console.print(f"  {icon}  {tc.scenario}.{tc.metric}: {tc.message}")

    if not report.thresholds_passed:
        console.print("\n[bold red]Some thresholds exceeded![/bold red]")
