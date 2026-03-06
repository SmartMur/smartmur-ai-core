"""Tests for the benchmark harness — scenarios, reports, CLI, thresholds."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from superpowers.benchmark import (
    DEFAULT_THRESHOLDS,
    SCENARIOS,
    BenchmarkReport,
    BenchmarkSuite,
    ScenarioResult,
    ThresholdCheck,
    _measure,
    _report_from_dict,
    scenario_dag_throughput,
    scenario_orchestration_e2e,
    scenario_policy_evaluation,
    scenario_report_generation,
)


# ---------------------------------------------------------------------------
# ScenarioResult dataclass
# ---------------------------------------------------------------------------


class TestScenarioResult:
    def test_defaults(self):
        r = ScenarioResult(name="test")
        assert r.name == "test"
        assert r.duration_ms == 0.0
        assert r.ops_per_sec == 0.0
        assert r.memory_peak_mb == 0.0
        assert r.iterations == 0
        assert r.status == "pass"
        assert r.error == ""
        assert r.metadata == {}

    def test_to_dict(self):
        r = ScenarioResult(name="x", duration_ms=100.5, ops_per_sec=10.0)
        d = r.to_dict()
        assert d["name"] == "x"
        assert d["duration_ms"] == 100.5
        assert d["ops_per_sec"] == 10.0

    def test_error_status(self):
        r = ScenarioResult(name="fail", status="error", error="boom")
        assert r.status == "error"
        assert r.error == "boom"


# ---------------------------------------------------------------------------
# ThresholdCheck dataclass
# ---------------------------------------------------------------------------


class TestThresholdCheck:
    def test_passed(self):
        tc = ThresholdCheck(
            scenario="dag", metric="duration_ms", actual=50.0, threshold=100.0, passed=True
        )
        assert tc.passed is True
        assert tc.to_dict()["passed"] is True

    def test_failed(self):
        tc = ThresholdCheck(
            scenario="dag", metric="duration_ms", actual=150.0, threshold=100.0, passed=False
        )
        assert tc.passed is False


# ---------------------------------------------------------------------------
# BenchmarkReport
# ---------------------------------------------------------------------------


class TestBenchmarkReport:
    def test_empty_report(self):
        report = BenchmarkReport()
        assert report.scenario_count == 0
        assert report.total_duration_ms == 0.0
        assert report.all_passed is True
        assert report.thresholds_passed is True

    def test_total_duration(self):
        report = BenchmarkReport(
            results=[
                ScenarioResult(name="a", duration_ms=100.0),
                ScenarioResult(name="b", duration_ms=200.0),
            ]
        )
        assert report.total_duration_ms == 300.0

    def test_all_passed_true(self):
        report = BenchmarkReport(
            results=[
                ScenarioResult(name="a", status="pass"),
                ScenarioResult(name="b", status="pass"),
            ]
        )
        assert report.all_passed is True

    def test_all_passed_false(self):
        report = BenchmarkReport(
            results=[
                ScenarioResult(name="a", status="pass"),
                ScenarioResult(name="b", status="error"),
            ]
        )
        assert report.all_passed is False

    def test_thresholds_passed_no_checks(self):
        report = BenchmarkReport()
        assert report.thresholds_passed is True

    def test_thresholds_passed_true(self):
        report = BenchmarkReport(
            threshold_checks=[
                ThresholdCheck(scenario="a", metric="x", actual=1.0, threshold=10.0, passed=True),
            ]
        )
        assert report.thresholds_passed is True

    def test_thresholds_passed_false(self):
        report = BenchmarkReport(
            threshold_checks=[
                ThresholdCheck(scenario="a", metric="x", actual=1.0, threshold=10.0, passed=True),
                ThresholdCheck(scenario="b", metric="y", actual=20.0, threshold=10.0, passed=False),
            ]
        )
        assert report.thresholds_passed is False

    def test_to_dict(self):
        report = BenchmarkReport(
            title="Test",
            results=[ScenarioResult(name="a", duration_ms=50.0)],
        )
        d = report.to_dict()
        assert d["title"] == "Test"
        assert d["scenario_count"] == 1
        assert len(d["results"]) == 1
        assert d["results"][0]["name"] == "a"

    def test_to_json(self):
        report = BenchmarkReport(title="Test")
        j = report.to_json()
        data = json.loads(j)
        assert data["title"] == "Test"

    def test_to_markdown_pass(self):
        report = BenchmarkReport(
            title="Test",
            results=[ScenarioResult(name="a", duration_ms=10.0, status="pass")],
        )
        md = report.to_markdown()
        assert "[PASS]" in md
        assert "Test" in md
        assert "| a |" in md

    def test_to_markdown_fail(self):
        report = BenchmarkReport(
            title="Test",
            results=[ScenarioResult(name="bad", status="error", error="boom")],
        )
        md = report.to_markdown()
        assert "[FAIL]" in md
        assert "boom" in md

    def test_to_markdown_with_thresholds(self):
        report = BenchmarkReport(
            title="Test",
            results=[ScenarioResult(name="a", status="pass")],
            threshold_checks=[
                ThresholdCheck(
                    scenario="a", metric="duration_ms", actual=50.0,
                    threshold=100.0, passed=True,
                ),
            ],
        )
        md = report.to_markdown()
        assert "Threshold Checks" in md
        assert "PASS" in md

    def test_save(self, tmp_path):
        report = BenchmarkReport(
            title="Save Test",
            started_at="2026-01-01T00:00:00",
            finished_at="2026-01-01T00:00:01",
            results=[ScenarioResult(name="a", duration_ms=10.0)],
        )
        json_path, md_path = report.save(tmp_path)
        assert json_path.exists()
        assert md_path.exists()
        assert json_path.suffix == ".json"
        assert md_path.suffix == ".md"

        # Check latest files
        assert (tmp_path / "benchmark-latest.json").exists()
        assert (tmp_path / "benchmark-latest.md").exists()

        # Verify JSON content
        data = json.loads(json_path.read_text())
        assert data["title"] == "Save Test"

    def test_scenario_count(self):
        report = BenchmarkReport(
            results=[ScenarioResult(name=f"s{i}") for i in range(5)]
        )
        assert report.scenario_count == 5


# ---------------------------------------------------------------------------
# _measure helper
# ---------------------------------------------------------------------------


class TestMeasure:
    def test_basic(self):
        result = _measure(lambda: None, iterations=10, name="noop")
        assert result.name == "noop"
        assert result.iterations == 10
        assert result.status == "pass"
        assert result.duration_ms >= 0
        assert result.ops_per_sec > 0
        assert result.memory_peak_mb >= 0

    def test_error_handling(self):
        def _fail():
            raise ValueError("intentional")

        result = _measure(_fail, iterations=1, name="fail")
        assert result.status == "error"
        assert "intentional" in result.error

    def test_multiple_iterations(self):
        counter = {"n": 0}

        def _inc():
            counter["n"] += 1

        result = _measure(_inc, iterations=5, name="inc")
        assert counter["n"] == 5
        assert result.iterations == 5


# ---------------------------------------------------------------------------
# Built-in scenarios
# ---------------------------------------------------------------------------


class TestScenarios:
    def test_dag_throughput_runs(self):
        result = scenario_dag_throughput(fan_out=5, iterations=1)
        assert result.name == "dag_throughput"
        assert result.status == "pass"
        assert result.duration_ms > 0
        assert result.ops_per_sec > 0

    def test_policy_evaluation_runs(self):
        result = scenario_policy_evaluation(iterations=10)
        assert result.name == "policy_evaluation"
        assert result.status == "pass"
        assert result.iterations == 10

    def test_orchestration_e2e_runs(self):
        result = scenario_orchestration_e2e(iterations=1)
        assert result.name == "orchestration_e2e"
        assert result.status == "pass"

    def test_report_generation_runs(self):
        result = scenario_report_generation(iterations=5)
        assert result.name == "report_generation"
        assert result.status == "pass"
        assert result.ops_per_sec > 0

    def test_scenario_registry(self):
        assert "dag_throughput" in SCENARIOS
        assert "policy_evaluation" in SCENARIOS
        assert "orchestration_e2e" in SCENARIOS
        assert "report_generation" in SCENARIOS
        assert len(SCENARIOS) == 4

    def test_default_thresholds(self):
        assert "dag_throughput" in DEFAULT_THRESHOLDS
        assert "duration_ms" in DEFAULT_THRESHOLDS["dag_throughput"]


# ---------------------------------------------------------------------------
# BenchmarkSuite
# ---------------------------------------------------------------------------


class TestBenchmarkSuite:
    def test_init_default(self, tmp_path):
        suite = BenchmarkSuite(output_dir=tmp_path)
        assert len(suite.scenario_names) == 4

    def test_scenario_names(self, tmp_path):
        suite = BenchmarkSuite(output_dir=tmp_path)
        names = suite.scenario_names
        assert "dag_throughput" in names
        assert names == sorted(names)

    def test_custom_scenarios(self, tmp_path):
        custom = {"fast": lambda: ScenarioResult(name="fast", duration_ms=1.0)}
        suite = BenchmarkSuite(scenarios=custom, output_dir=tmp_path)
        assert suite.scenario_names == ["fast"]

    def test_run_scenario_known(self, tmp_path):
        def _noop():
            return ScenarioResult(name="noop", duration_ms=0.1, status="pass")

        suite = BenchmarkSuite(scenarios={"noop": _noop}, output_dir=tmp_path)
        result = suite.run_scenario("noop")
        assert result.name == "noop"
        assert result.status == "pass"

    def test_run_scenario_unknown(self, tmp_path):
        suite = BenchmarkSuite(scenarios={}, output_dir=tmp_path)
        result = suite.run_scenario("nonexistent")
        assert result.status == "error"
        assert "Unknown scenario" in result.error

    def test_run_scenario_exception(self, tmp_path):
        def _fail():
            raise RuntimeError("scenario crash")

        suite = BenchmarkSuite(scenarios={"crash": _fail}, output_dir=tmp_path)
        result = suite.run_scenario("crash")
        assert result.status == "error"
        assert "scenario crash" in result.error

    def test_run_all_sequential(self, tmp_path):
        results_produced = []

        def _fast():
            r = ScenarioResult(name="fast", duration_ms=1.0, status="pass")
            results_produced.append(r)
            return r

        def _slow():
            r = ScenarioResult(name="slow", duration_ms=2.0, status="pass")
            results_produced.append(r)
            return r

        suite = BenchmarkSuite(
            scenarios={"fast": _fast, "slow": _slow},
            output_dir=tmp_path,
        )
        report = suite.run_all(parallel=False)
        assert report.scenario_count == 2
        assert report.all_passed is True

    def test_run_all_parallel(self, tmp_path):
        def _fast():
            return ScenarioResult(name="fast", duration_ms=1.0, status="pass")

        def _slow():
            return ScenarioResult(name="slow", duration_ms=2.0, status="pass")

        suite = BenchmarkSuite(
            scenarios={"fast": _fast, "slow": _slow},
            output_dir=tmp_path,
        )
        report = suite.run_all(parallel=True)
        assert report.scenario_count == 2
        assert report.metadata["parallel"] is True

    def test_run_and_save(self, tmp_path):
        def _quick():
            return ScenarioResult(name="quick", duration_ms=0.5, status="pass")

        suite = BenchmarkSuite(scenarios={"quick": _quick}, output_dir=tmp_path)
        report, json_path, md_path = suite.run_and_save()
        assert json_path.exists()
        assert md_path.exists()
        assert report.scenario_count == 1

    def test_threshold_check_pass(self, tmp_path):
        def _fast():
            return ScenarioResult(name="fast", duration_ms=10.0, status="pass")

        suite = BenchmarkSuite(
            scenarios={"fast": _fast},
            thresholds={"fast": {"duration_ms": 1000.0}},
            output_dir=tmp_path,
        )
        report = suite.run_all()
        assert report.thresholds_passed is True
        assert len(report.threshold_checks) == 1
        assert report.threshold_checks[0].passed is True

    def test_threshold_check_fail(self, tmp_path):
        def _slow():
            return ScenarioResult(name="slow", duration_ms=5000.0, status="pass")

        suite = BenchmarkSuite(
            scenarios={"slow": _slow},
            thresholds={"slow": {"duration_ms": 100.0}},
            output_dir=tmp_path,
        )
        report = suite.run_all()
        assert report.thresholds_passed is False

    def test_threshold_ops_per_sec(self, tmp_path):
        def _fast():
            return ScenarioResult(name="fast", ops_per_sec=500.0, status="pass")

        suite = BenchmarkSuite(
            scenarios={"fast": _fast},
            thresholds={"fast": {"ops_per_sec": 100.0}},
            output_dir=tmp_path,
        )
        report = suite.run_all()
        checks = [c for c in report.threshold_checks if c.metric == "ops_per_sec"]
        assert len(checks) == 1
        assert checks[0].passed is True  # 500 >= 100

    def test_threshold_ops_per_sec_fail(self, tmp_path):
        def _slow():
            return ScenarioResult(name="slow", ops_per_sec=5.0, status="pass")

        suite = BenchmarkSuite(
            scenarios={"slow": _slow},
            thresholds={"slow": {"ops_per_sec": 100.0}},
            output_dir=tmp_path,
        )
        report = suite.run_all()
        checks = [c for c in report.threshold_checks if c.metric == "ops_per_sec"]
        assert checks[0].passed is False  # 5 < 100

    def test_set_threshold(self, tmp_path):
        suite = BenchmarkSuite(thresholds={}, output_dir=tmp_path)
        suite.set_threshold("dag", "duration_ms", 500.0)
        assert suite.get_thresholds() == {"dag": {"duration_ms": 500.0}}

    def test_get_thresholds_copy(self, tmp_path):
        suite = BenchmarkSuite(
            thresholds={"a": {"x": 1.0}},
            output_dir=tmp_path,
        )
        t = suite.get_thresholds()
        t["a"]["x"] = 999.0
        assert suite.get_thresholds()["a"]["x"] == 1.0  # Original unchanged

    def test_load_last_report_none(self, tmp_path):
        suite = BenchmarkSuite(output_dir=tmp_path)
        assert suite.load_last_report() is None

    def test_load_last_report_exists(self, tmp_path):
        def _quick():
            return ScenarioResult(name="quick", duration_ms=1.0, status="pass")

        suite = BenchmarkSuite(scenarios={"quick": _quick}, output_dir=tmp_path)
        suite.run_and_save()
        loaded = suite.load_last_report()
        assert loaded is not None
        assert loaded.scenario_count == 1
        assert loaded.results[0].name == "quick"

    def test_output_dir(self, tmp_path):
        suite = BenchmarkSuite(output_dir=tmp_path)
        assert suite.output_dir == tmp_path


# ---------------------------------------------------------------------------
# _report_from_dict
# ---------------------------------------------------------------------------


class TestReportFromDict:
    def test_round_trip(self):
        report = BenchmarkReport(
            title="RT",
            results=[ScenarioResult(name="a", duration_ms=10.0)],
            threshold_checks=[
                ThresholdCheck(scenario="a", metric="m", actual=1.0, threshold=2.0, passed=True),
            ],
        )
        d = report.to_dict()
        loaded = _report_from_dict(d)
        assert loaded.title == "RT"
        assert loaded.scenario_count == 1
        assert loaded.results[0].name == "a"
        assert len(loaded.threshold_checks) == 1

    def test_empty_dict(self):
        loaded = _report_from_dict({})
        assert loaded.title == "Benchmark Report"
        assert loaded.scenario_count == 0


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestCLI:
    def _runner(self):
        return CliRunner()

    def test_benchmark_group_help(self):
        from superpowers.cli_benchmark import benchmark_group

        result = self._runner().invoke(benchmark_group, ["--help"])
        assert result.exit_code == 0
        assert "benchmark" in result.output.lower()

    def test_benchmark_list(self):
        from superpowers.cli_benchmark import benchmark_group

        result = self._runner().invoke(benchmark_group, ["list"])
        assert result.exit_code == 0
        assert "dag_throughput" in result.output
        assert "policy_evaluation" in result.output

    def test_benchmark_run_unknown_scenario(self):
        from superpowers.cli_benchmark import benchmark_group

        result = self._runner().invoke(benchmark_group, ["run", "--scenario", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown scenario" in result.output

    def test_benchmark_run_specific_scenario(self):
        from superpowers.cli_benchmark import benchmark_group

        result = self._runner().invoke(
            benchmark_group, ["run", "--scenario", "policy_evaluation", "--no-save"]
        )
        assert result.exit_code == 0
        assert "policy_evaluation" in result.output

    def test_benchmark_run_all_no_save(self):
        from superpowers.cli_benchmark import benchmark_group

        result = self._runner().invoke(benchmark_group, ["run", "--no-save"])
        assert result.exit_code == 0
        assert "Benchmark" in result.output

    def test_benchmark_report_no_data(self):
        from superpowers.cli_benchmark import benchmark_group

        with patch("superpowers.benchmark.BenchmarkSuite.load_last_report", return_value=None):
            result = self._runner().invoke(benchmark_group, ["report"])
            assert result.exit_code == 0
            assert "No benchmark reports" in result.output

    def test_benchmark_report_with_data(self):
        from superpowers.benchmark import BenchmarkReport, ScenarioResult
        from superpowers.cli_benchmark import benchmark_group

        mock_report = BenchmarkReport(
            title="Test",
            results=[ScenarioResult(name="a", duration_ms=10.0, status="pass")],
        )
        with patch(
            "superpowers.benchmark.BenchmarkSuite.load_last_report", return_value=mock_report
        ):
            result = self._runner().invoke(benchmark_group, ["report"])
            assert result.exit_code == 0

    def test_cli_registered_in_main(self):
        from superpowers.cli import main

        # Verify the benchmark group is registered
        cmd_names = [cmd for cmd in main.commands]
        assert "benchmark" in cmd_names


# ---------------------------------------------------------------------------
# Integration: full suite with real scenarios
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_suite_run(self, tmp_path):
        """Run the actual default suite with small params and verify end-to-end."""
        # Use lightweight scenarios
        def _light_dag():
            return scenario_dag_throughput(fan_out=3, iterations=1)

        def _light_policy():
            return scenario_policy_evaluation(iterations=5)

        def _light_orch():
            return scenario_orchestration_e2e(iterations=1)

        def _light_report():
            return scenario_report_generation(iterations=2)

        suite = BenchmarkSuite(
            scenarios={
                "dag_throughput": _light_dag,
                "policy_evaluation": _light_policy,
                "orchestration_e2e": _light_orch,
                "report_generation": _light_report,
            },
            output_dir=tmp_path,
        )
        report, json_path, md_path = suite.run_and_save()

        assert report.scenario_count == 4
        assert report.all_passed is True
        assert json_path.exists()
        assert md_path.exists()

        # Verify JSON is valid
        data = json.loads(json_path.read_text())
        assert data["scenario_count"] == 4

        # Verify Markdown
        md = md_path.read_text()
        assert "dag_throughput" in md
        assert "policy_evaluation" in md

    def test_suite_parallel_vs_sequential(self, tmp_path):
        """Both modes should produce the same number of results."""
        def _quick():
            return ScenarioResult(name="q", duration_ms=0.1, status="pass")

        scenarios = {"a": _quick, "b": _quick, "c": _quick}

        suite_seq = BenchmarkSuite(scenarios=scenarios, output_dir=tmp_path / "seq")
        suite_par = BenchmarkSuite(scenarios=scenarios, output_dir=tmp_path / "par")

        report_seq = suite_seq.run_all(parallel=False)
        report_par = suite_par.run_all(parallel=True)

        assert report_seq.scenario_count == report_par.scenario_count == 3
