"""Competitive benchmark harness for orchestration performance.

Measures and reports on DAG execution throughput, policy engine evaluation
latency, orchestration end-to-end time, and report generation speed.
Results are structured and can be compared against configurable baselines.
"""

from __future__ import annotations

import json
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    """Structured result from a single benchmark scenario."""

    name: str
    duration_ms: float = 0.0
    ops_per_sec: float = 0.0
    memory_peak_mb: float = 0.0
    iterations: int = 0
    status: str = "pass"  # "pass", "fail", "error"
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThresholdCheck:
    """Result of comparing a scenario against a baseline threshold."""

    scenario: str
    metric: str
    actual: float
    threshold: float
    passed: bool
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# BenchmarkReport
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkReport:
    """Aggregates benchmark results into a structured report."""

    title: str = "Benchmark Report"
    started_at: str = ""
    finished_at: str = ""
    results: list[ScenarioResult] = field(default_factory=list)
    threshold_checks: list[ThresholdCheck] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def total_duration_ms(self) -> float:
        return sum(r.duration_ms for r in self.results)

    @property
    def all_passed(self) -> bool:
        return all(r.status == "pass" for r in self.results)

    @property
    def thresholds_passed(self) -> bool:
        if not self.threshold_checks:
            return True
        return all(tc.passed for tc in self.threshold_checks)

    @property
    def scenario_count(self) -> int:
        return len(self.results)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_duration_ms": self.total_duration_ms,
            "all_passed": self.all_passed,
            "thresholds_passed": self.thresholds_passed,
            "scenario_count": self.scenario_count,
            "results": [r.to_dict() for r in self.results],
            "threshold_checks": [tc.to_dict() for tc in self.threshold_checks],
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_markdown(self) -> str:
        lines: list[str] = []
        overall = "PASS" if self.all_passed and self.thresholds_passed else "FAIL"
        lines.append(f"# [{overall}] {self.title}")
        lines.append("")

        # Meta table
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        if self.started_at:
            lines.append(f"| Started | {self.started_at} |")
        if self.finished_at:
            lines.append(f"| Finished | {self.finished_at} |")
        lines.append(f"| Total Duration | {self.total_duration_ms:.1f}ms |")
        lines.append(f"| Scenarios | {self.scenario_count} |")
        lines.append(f"| All Passed | {self.all_passed} |")
        lines.append("")

        # Scenario results
        lines.append("## Scenario Results")
        lines.append("")
        lines.append("| Scenario | Duration (ms) | Ops/sec | Peak Memory (MB) | Iterations | Status |")
        lines.append("|----------|--------------|---------|-------------------|------------|--------|")
        for r in self.results:
            lines.append(
                f"| {r.name} | {r.duration_ms:.1f} | {r.ops_per_sec:.1f} | "
                f"{r.memory_peak_mb:.2f} | {r.iterations} | {r.status} |"
            )
        lines.append("")

        # Threshold checks
        if self.threshold_checks:
            lines.append("## Threshold Checks")
            lines.append("")
            lines.append("| Scenario | Metric | Actual | Threshold | Result |")
            lines.append("|----------|--------|--------|-----------|--------|")
            for tc in self.threshold_checks:
                result_str = "PASS" if tc.passed else "FAIL"
                lines.append(
                    f"| {tc.scenario} | {tc.metric} | {tc.actual:.2f} | "
                    f"{tc.threshold:.2f} | {result_str} |"
                )
            lines.append("")

        # Errors
        errors = [r for r in self.results if r.error]
        if errors:
            lines.append("## Errors")
            lines.append("")
            for r in errors:
                lines.append(f"- **{r.name}**: {r.error}")
            lines.append("")

        return "\n".join(lines)

    def save(self, output_dir: Path) -> tuple[Path, Path]:
        """Persist report as JSON + Markdown. Returns (json_path, md_path)."""
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        json_path = output_dir / f"benchmark-{ts}.json"
        md_path = output_dir / f"benchmark-{ts}.md"
        json_path.write_text(self.to_json())
        md_path.write_text(self.to_markdown())

        # Also write latest
        latest_json = output_dir / "benchmark-latest.json"
        latest_md = output_dir / "benchmark-latest.md"
        latest_json.write_text(self.to_json())
        latest_md.write_text(self.to_markdown())

        return json_path, md_path


# ---------------------------------------------------------------------------
# Scenario helpers
# ---------------------------------------------------------------------------


def _measure(
    fn: Callable[[], Any],
    iterations: int = 1,
    name: str = "",
) -> ScenarioResult:
    """Run a callable ``iterations`` times, measuring time and memory.

    Returns a populated ScenarioResult.
    """
    tracemalloc.start()
    start = time.perf_counter()

    error = ""
    status = "pass"
    try:
        for _ in range(iterations):
            fn()
    except Exception as exc:
        error = str(exc)
        status = "error"

    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    duration_ms = elapsed * 1000
    ops = iterations / elapsed if elapsed > 0 else 0.0
    peak_mb = peak / (1024 * 1024)

    return ScenarioResult(
        name=name,
        duration_ms=duration_ms,
        ops_per_sec=ops,
        memory_peak_mb=peak_mb,
        iterations=iterations,
        status=status,
        error=error,
    )


# ---------------------------------------------------------------------------
# Built-in scenarios
# ---------------------------------------------------------------------------


def scenario_dag_throughput(fan_out: int = 50, iterations: int = 3) -> ScenarioResult:
    """Measure DAG execution throughput with fan-out parallel tasks."""
    from superpowers.dag_executor import DAGExecutor

    def _run_once():
        dag = DAGExecutor()
        # Root node
        dag.add_node("root", "Root", action=lambda: "root-done")
        # Fan-out nodes depending on root
        for i in range(fan_out):
            dag.add_node(
                f"task-{i}",
                f"Task {i}",
                action=lambda: sum(range(100)),
                depends_on=["root"],
            )
        # Collector depending on all fan-out nodes
        all_tasks = [f"task-{i}" for i in range(fan_out)]
        dag.add_node("collector", "Collector", action=lambda: "done", depends_on=all_tasks)
        dag.execute(max_workers=8)

    return _measure(_run_once, iterations=iterations, name="dag_throughput")


def scenario_policy_evaluation(iterations: int = 1000) -> ScenarioResult:
    """Measure policy engine command evaluation latency."""
    from superpowers.policy_engine import PolicyEngine

    engine = PolicyEngine()
    commands = [
        "ls -la /tmp",
        "rm -rf /",
        "git push --force main",
        "docker system prune",
        "echo hello",
        "python script.py",
        "cat /etc/passwd",
        "curl https://example.com",
        "DROP TABLE users",
        "chmod 777 /",
    ]

    idx = 0

    def _run_once():
        nonlocal idx
        cmd = commands[idx % len(commands)]
        idx += 1
        engine.check_command(cmd)

    return _measure(_run_once, iterations=iterations, name="policy_evaluation")


def scenario_orchestration_e2e(iterations: int = 3) -> ScenarioResult:
    """Measure orchestration end-to-end time with a simple workflow."""
    from superpowers.dag_executor import DAGExecutor

    def _run_once():
        dag = DAGExecutor()
        # Simulate a 5-step sequential pipeline
        prev = None
        for i in range(5):
            deps = [prev] if prev else []
            node_id = f"step-{i}"
            dag.add_node(node_id, f"Step {i}", action=lambda: "ok", depends_on=deps)
            prev = node_id
        dag.execute(max_workers=2)

    return _measure(_run_once, iterations=iterations, name="orchestration_e2e")


def scenario_report_generation(iterations: int = 50) -> ScenarioResult:
    """Measure report generation speed (JSON + Markdown)."""
    from superpowers.reporting import Report, ReportFormatter, ReportItem, ReportSection

    # Build a moderately complex report
    sections = []
    for i in range(5):
        items = [
            ReportItem(label=f"Check {j}", value=f"Value {j}", status="ok")
            for j in range(10)
        ]
        sections.append(
            ReportSection(heading=f"Section {i}", content=f"Content for section {i}", items=items)
        )

    report = Report(
        title="Benchmark Test Report",
        command="claw benchmark run",
        status="pass",
        sections=sections,
        metadata={"version": "1.0", "host": "test"},
    )
    report.finish()

    def _run_once():
        ReportFormatter.to_json(report)
        ReportFormatter.to_markdown(report)

    return _measure(_run_once, iterations=iterations, name="report_generation")


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, Callable[[], ScenarioResult]] = {
    "dag_throughput": scenario_dag_throughput,
    "policy_evaluation": scenario_policy_evaluation,
    "orchestration_e2e": scenario_orchestration_e2e,
    "report_generation": scenario_report_generation,
}

# Default thresholds: scenario -> {metric: max_allowed_value}
DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    "dag_throughput": {"duration_ms": 10000.0, "memory_peak_mb": 100.0},
    "policy_evaluation": {"duration_ms": 5000.0, "ops_per_sec": 100.0},
    "orchestration_e2e": {"duration_ms": 5000.0},
    "report_generation": {"duration_ms": 5000.0, "ops_per_sec": 10.0},
}


# ---------------------------------------------------------------------------
# BenchmarkSuite
# ---------------------------------------------------------------------------


class BenchmarkSuite:
    """Run timed benchmark scenarios and produce structured reports.

    Usage::

        suite = BenchmarkSuite()
        report = suite.run_all()
        print(report.to_markdown())
    """

    def __init__(
        self,
        scenarios: dict[str, Callable[[], ScenarioResult]] | None = None,
        thresholds: dict[str, dict[str, float]] | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self._scenarios = dict(scenarios or SCENARIOS)
        self._thresholds = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
        if output_dir is None:
            from superpowers.config import get_data_dir

            output_dir = get_data_dir() / "benchmarks"
        self._output_dir = output_dir

    @property
    def scenario_names(self) -> list[str]:
        return sorted(self._scenarios.keys())

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def set_threshold(self, scenario: str, metric: str, value: float) -> None:
        """Set or update a threshold for a scenario metric."""
        if scenario not in self._thresholds:
            self._thresholds[scenario] = {}
        self._thresholds[scenario][metric] = value

    def get_thresholds(self) -> dict[str, dict[str, float]]:
        """Return a copy of all thresholds."""
        return {k: dict(v) for k, v in self._thresholds.items()}

    def run_scenario(self, name: str) -> ScenarioResult:
        """Run a single named scenario."""
        if name not in self._scenarios:
            return ScenarioResult(
                name=name,
                status="error",
                error=f"Unknown scenario: {name}",
            )
        try:
            return self._scenarios[name]()
        except Exception as exc:
            return ScenarioResult(
                name=name,
                status="error",
                error=str(exc),
            )

    def run_all(self, parallel: bool = False) -> BenchmarkReport:
        """Run all registered scenarios and return a report.

        Parameters
        ----------
        parallel:
            If True, run scenarios concurrently via ThreadPoolExecutor.
        """
        started_at = datetime.now(UTC).isoformat()
        results: list[ScenarioResult] = []

        if parallel:
            with ThreadPoolExecutor(max_workers=len(self._scenarios)) as pool:
                futures = {
                    pool.submit(self.run_scenario, name): name
                    for name in sorted(self._scenarios)
                }
                for future in as_completed(futures):
                    results.append(future.result())
        else:
            for name in sorted(self._scenarios):
                results.append(self.run_scenario(name))

        finished_at = datetime.now(UTC).isoformat()

        # Check thresholds
        checks = self._check_thresholds(results)

        report = BenchmarkReport(
            title="Orchestration Benchmark Report",
            started_at=started_at,
            finished_at=finished_at,
            results=results,
            threshold_checks=checks,
            metadata={"parallel": parallel, "scenario_count": len(results)},
        )

        return report

    def run_and_save(self, parallel: bool = False) -> tuple[BenchmarkReport, Path, Path]:
        """Run all scenarios, save the report, and return (report, json_path, md_path)."""
        report = self.run_all(parallel=parallel)
        json_path, md_path = report.save(self._output_dir)
        return report, json_path, md_path

    def _check_thresholds(self, results: list[ScenarioResult]) -> list[ThresholdCheck]:
        """Compare results against configured thresholds."""
        checks: list[ThresholdCheck] = []
        for result in results:
            if result.name not in self._thresholds:
                continue
            for metric, threshold in self._thresholds[result.name].items():
                actual = getattr(result, metric, None)
                if actual is None:
                    continue

                # For ops_per_sec, higher is better (actual must exceed threshold)
                if metric == "ops_per_sec":
                    passed = actual >= threshold
                    msg = f"{actual:.2f} >= {threshold:.2f}" if passed else f"{actual:.2f} < {threshold:.2f}"
                else:
                    # For duration_ms, memory_peak_mb: lower is better
                    passed = actual <= threshold
                    msg = f"{actual:.2f} <= {threshold:.2f}" if passed else f"{actual:.2f} > {threshold:.2f}"

                checks.append(
                    ThresholdCheck(
                        scenario=result.name,
                        metric=metric,
                        actual=actual,
                        threshold=threshold,
                        passed=passed,
                        message=msg,
                    )
                )
        return checks

    def load_last_report(self) -> BenchmarkReport | None:
        """Load the most recent benchmark report from disk."""
        latest = self._output_dir / "benchmark-latest.json"
        if not latest.is_file():
            return None
        try:
            data = json.loads(latest.read_text())
            return _report_from_dict(data)
        except (json.JSONDecodeError, OSError, KeyError):
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _report_from_dict(data: dict) -> BenchmarkReport:
    """Reconstruct a BenchmarkReport from a dict."""
    results = [ScenarioResult(**r) for r in data.get("results", [])]
    checks = [ThresholdCheck(**tc) for tc in data.get("threshold_checks", [])]
    return BenchmarkReport(
        title=data.get("title", "Benchmark Report"),
        started_at=data.get("started_at", ""),
        finished_at=data.get("finished_at", ""),
        results=results,
        threshold_checks=checks,
        metadata=data.get("metadata", {}),
    )
