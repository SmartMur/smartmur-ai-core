"""Soak / reliability tests — validate system stability under sustained load.

Proves that DAG executor, policy engine, reporting, and orchestration
subsystems do not degrade under repeated or concurrent use.  Every test
is capped at ~30 s via timeouts and conservative iteration counts.

Run:
    PYTHONPATH=. .venv/bin/python -m pytest tests/test_soak.py -v
"""

from __future__ import annotations

import gc
import json
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import pytest

from superpowers.dag_executor import DAGError, DAGExecutor, NodeStatus
from superpowers.policy_engine import (
    Policy,
    PolicyAction,
    PolicyEngine,
    PolicyRule,
)
from superpowers.reporting import (
    Report,
    ReportFormatter,
    ReportItem,
    ReportRegistry,
    ReportSection,
    quick_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop():
    return "ok"


def _failing():
    raise RuntimeError("deliberate failure")


def _make_simple_dag(n: int = 3) -> DAGExecutor:
    """Build a simple linear chain of *n* nodes."""
    dag = DAGExecutor()
    prev = None
    for i in range(n):
        deps = [prev] if prev else None
        dag.add_node(f"n{i}", f"Node-{i}", action=_noop, depends_on=deps)
        prev = f"n{i}"
    return dag


def _make_diamond_dag() -> DAGExecutor:
    """A -> (B, C) -> D pattern."""
    dag = DAGExecutor()
    dag.add_node("a", "A", action=_noop)
    dag.add_node("b", "B", action=_noop, depends_on=["a"])
    dag.add_node("c", "C", action=_noop, depends_on=["a"])
    dag.add_node("d", "D", action=_noop, depends_on=["b", "c"])
    return dag


def _make_report(idx: int = 0) -> Report:
    """Create a small report for testing."""
    return quick_report(
        title=f"Soak report {idx}",
        items=[
            ("check-1", "passed", "ok"),
            ("check-2", "7 warnings", "warn"),
        ],
        command="soak-test",
        metadata={"iteration": idx},
    )


# ---------------------------------------------------------------------------
# 1. Repeated DAG execution — no crashes, consistent results
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestRepeatedDAGExecution:
    """Run DAG executor many times and verify determinism."""

    def test_linear_chain_100_times(self):
        """Execute a 3-node linear chain 100 times — all must succeed."""
        for _ in range(100):
            dag = _make_simple_dag(3)
            dag.execute(max_workers=2)
            summary = dag.status_summary()
            assert summary["done"] == 3
            assert summary["failed"] == 0

    def test_diamond_dag_100_times(self):
        """Diamond DAG executed 100 times — results must be consistent."""
        for _ in range(100):
            dag = _make_diamond_dag()
            dag.execute(max_workers=4)
            assert dag.get_node("d").status == NodeStatus.done
            assert dag.get_node("d").result == "ok"

    def test_empty_dag_200_times(self):
        """Empty DAG is a valid edge case — must never crash."""
        for _ in range(200):
            dag = DAGExecutor()
            result = dag.execute()
            assert result == {}

    def test_single_node_150_times(self):
        """Single-node DAG repeated 150 times."""
        for _ in range(150):
            dag = DAGExecutor()
            dag.add_node("solo", "Solo", action=_noop)
            dag.execute()
            assert dag.get_node("solo").result == "ok"

    def test_failure_propagation_consistent(self):
        """A failing root consistently skips all dependents over 100 runs."""
        for _ in range(100):
            dag = DAGExecutor()
            dag.add_node("root", "Root", action=_failing)
            dag.add_node("child", "Child", action=_noop, depends_on=["root"])
            dag.execute()
            assert dag.get_node("root").status == NodeStatus.failed
            assert dag.get_node("child").status == NodeStatus.skipped


# ---------------------------------------------------------------------------
# 2. Memory leak detection via tracemalloc
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestMemoryStability:
    """Use tracemalloc to verify no significant memory growth."""

    def test_dag_no_memory_leak(self):
        """Run DAG 200 times and check memory doesn't grow unboundedly."""
        tracemalloc.start()
        gc.collect()
        snap_before = tracemalloc.take_snapshot()

        for _ in range(200):
            dag = _make_diamond_dag()
            dag.execute(max_workers=2)

        gc.collect()
        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Compare top memory allocations
        stats = snap_after.compare_to(snap_before, "lineno")
        # Sum the size differences (positive = growth)
        total_growth = sum(s.size_diff for s in stats if s.size_diff > 0)
        # Allow up to 5 MB growth for 200 iterations — generous but catches real leaks
        assert total_growth < 5 * 1024 * 1024, (
            f"Memory grew by {total_growth / 1024 / 1024:.1f} MB over 200 DAG runs"
        )

    def test_policy_engine_no_memory_leak(self):
        """Repeated policy checks should not leak memory."""
        tracemalloc.start()
        gc.collect()
        snap_before = tracemalloc.take_snapshot()

        engine = PolicyEngine()
        for _ in range(1000):
            engine.check_command("echo hello")
            engine.check_command("rm -rf /")
            engine.check_file_access("/etc/passwd")
            engine.check_output("token=abc123secretvalue")

        gc.collect()
        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap_after.compare_to(snap_before, "lineno")
        total_growth = sum(s.size_diff for s in stats if s.size_diff > 0)
        assert total_growth < 5 * 1024 * 1024, (
            f"Memory grew by {total_growth / 1024 / 1024:.1f} MB over 4000 policy checks"
        )

    def test_report_generation_no_memory_leak(self):
        """Creating many reports should not leak memory."""
        tracemalloc.start()
        gc.collect()
        snap_before = tracemalloc.take_snapshot()

        for i in range(200):
            report = _make_report(i)
            _ = ReportFormatter.to_json(report)
            _ = ReportFormatter.to_markdown(report)

        gc.collect()
        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap_after.compare_to(snap_before, "lineno")
        total_growth = sum(s.size_diff for s in stats if s.size_diff > 0)
        assert total_growth < 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# 3. Concurrent stress tests
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestConcurrentStress:
    """Run many DAGs / policy checks / reports concurrently."""

    def test_20_concurrent_dags(self):
        """Run 20 DAGs in parallel threads — no deadlocks, no crashes."""
        results = {}
        errors = []

        def run_dag(idx: int):
            try:
                dag = _make_diamond_dag()
                dag.execute(max_workers=2)
                summary = dag.status_summary()
                results[idx] = summary
            except Exception as exc:
                errors.append((idx, str(exc)))

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(run_dag, i): i for i in range(20)}
            for f in as_completed(futures, timeout=30):
                f.result()  # re-raise any exception

        assert len(errors) == 0, f"DAG errors: {errors}"
        assert len(results) == 20
        for idx, summary in results.items():
            assert summary["done"] == 4, f"DAG {idx} had {summary['done']} done"

    def test_30_concurrent_dags_with_failures(self):
        """Mix of passing and failing DAGs run concurrently."""
        results = {}

        def run_dag(idx: int):
            dag = DAGExecutor()
            if idx % 3 == 0:
                dag.add_node("root", "Root", action=_failing)
            else:
                dag.add_node("root", "Root", action=_noop)
            dag.add_node("child", "Child", action=_noop, depends_on=["root"])
            dag.execute(max_workers=2)
            results[idx] = dag.status_summary()

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(run_dag, i) for i in range(30)]
            for f in as_completed(futures, timeout=30):
                f.result()

        assert len(results) == 30
        for idx, summary in results.items():
            if idx % 3 == 0:
                assert summary["failed"] == 1
                assert summary["skipped"] == 1
            else:
                assert summary["done"] == 2

    def test_concurrent_policy_checks(self):
        """50 threads hammering policy engine simultaneously."""
        engine = PolicyEngine()
        results = {}

        def check(idx: int):
            d1 = engine.check_command("echo safe")
            d2 = engine.check_command("rm -rf /")
            d3 = engine.check_file_access("/etc/passwd")
            results[idx] = (d1.action, d2.action, d3.action)

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(check, i) for i in range(50)]
            for f in as_completed(futures, timeout=30):
                f.result()

        assert len(results) == 50
        for idx, (a1, a2, a3) in results.items():
            assert a1 == PolicyAction.allow
            assert a2 == PolicyAction.deny
            assert a3 == PolicyAction.deny

    def test_concurrent_report_formatting(self):
        """50 reports formatted concurrently — all must complete correctly."""
        outputs = {}

        def format_report(idx: int):
            report = _make_report(idx)
            j = ReportFormatter.to_json(report)
            m = ReportFormatter.to_markdown(report)
            outputs[idx] = (len(j), len(m))

        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = [pool.submit(format_report, i) for i in range(50)]
            for f in as_completed(futures, timeout=30):
                f.result()

        assert len(outputs) == 50
        for idx, (jlen, mlen) in outputs.items():
            assert jlen > 50, f"Report {idx} JSON too short: {jlen}"
            assert mlen > 50, f"Report {idx} markdown too short: {mlen}"

    def test_concurrent_report_save(self, tmp_path):
        """50 reports saved concurrently to same dir — no file corruption."""
        registry = ReportRegistry(reports_dir=tmp_path / "reports")
        saved_paths = {}

        def save_report(idx: int):
            report = _make_report(idx)
            jp, mp = registry.save_report(report)
            saved_paths[idx] = (jp, mp)

        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = [pool.submit(save_report, i) for i in range(50)]
            for f in as_completed(futures, timeout=30):
                f.result()

        assert len(saved_paths) == 50
        # Verify each saved JSON is valid
        for idx, (jp, mp) in saved_paths.items():
            assert jp.exists()
            assert mp.exists()
            data = json.loads(jp.read_text())
            assert data["title"] == f"Soak report {idx}"


# ---------------------------------------------------------------------------
# 4. Policy engine rapid-fire stress
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestPolicyEngineStress:
    """Evaluate many policy checks rapidly."""

    def test_1000_command_checks(self):
        """1000 command checks — all must return consistent results."""
        engine = PolicyEngine()
        commands = [
            ("echo hello", PolicyAction.allow),
            ("rm -rf /", PolicyAction.deny),
            ("git push --force main", PolicyAction.deny),
            ("git push origin feature", PolicyAction.require_approval),
            ("docker rm mycontainer", PolicyAction.require_approval),
            ("ls -la", PolicyAction.allow),
        ]
        for i in range(1000):
            cmd, expected = commands[i % len(commands)]
            decision = engine.check_command(cmd)
            assert decision.action == expected, (
                f"Iteration {i}: {cmd!r} expected {expected}, got {decision.action}"
            )

    def test_1000_file_checks(self):
        """1000 file access checks — consistent decisions."""
        engine = PolicyEngine()
        files = [
            ("/etc/passwd", PolicyAction.deny),
            ("/etc/shadow", PolicyAction.deny),
            ("/home/user/code.py", PolicyAction.allow),
            ("/home/user/.env", PolicyAction.deny),
            ("/tmp/test.txt", PolicyAction.allow),
        ]
        for i in range(1000):
            path, expected = files[i % len(files)]
            decision = engine.check_file_access(path)
            assert decision.action == expected, (
                f"Iteration {i}: {path!r} expected {expected}, got {decision.action}"
            )

    def test_1000_output_scans(self):
        """1000 output scans — secret detection is consistent."""
        engine = PolicyEngine()
        clean = "This is normal output with no secrets"
        dirty = "api_key=AKIAIOSFODNN7EXAMPLE1234567890"

        for _ in range(500):
            found, _ = engine.check_output(clean)
            assert not found

        for _ in range(500):
            found, redacted = engine.check_output(dirty)
            assert found
            assert "AKIAIOSFODNN7EXAMPLE" not in redacted

    def test_add_remove_policy_stress(self):
        """Repeatedly add and remove policies — engine stays consistent."""
        engine = PolicyEngine()
        base_count = len(engine.get_policies())

        for i in range(200):
            p = Policy(
                name=f"stress-{i}",
                rules=[PolicyRule(action=PolicyAction.deny, command_pattern=f"stress-cmd-{i}")],
            )
            engine.add_policy(p)
            assert len(engine.get_policies()) == base_count + 1
            engine.remove_policy(f"stress-{i}")
            assert len(engine.get_policies()) == base_count

    def test_custom_policy_rapid_checks(self):
        """Add a custom policy, run 500 checks against it."""
        engine = PolicyEngine()
        engine.add_policy(
            Policy(
                name="soak-custom",
                rules=[
                    PolicyRule(
                        action=PolicyAction.deny,
                        command_pattern=r"soak-forbidden-\d+",
                    )
                ],
            )
        )
        for i in range(500):
            d = engine.check_command(f"soak-forbidden-{i}")
            assert d.action == PolicyAction.deny


# ---------------------------------------------------------------------------
# 5. Report generation under load
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestReportLoad:
    """Generate many reports and verify correctness."""

    def test_100_quick_reports(self):
        """Create 100 quick_report objects — verify structure."""
        for i in range(100):
            report = _make_report(i)
            assert report.title == f"Soak report {i}"
            assert report.section_count == 1
            assert report.item_count == 2
            assert report.status in ("pass", "warn", "fail")

    def test_json_round_trip_50_reports(self):
        """50 reports serialized to JSON and back — data preserved."""
        for i in range(50):
            report = _make_report(i)
            j = ReportFormatter.to_json(report)
            data = json.loads(j)
            restored = Report.from_dict(data)
            assert restored.title == report.title
            assert restored.command == report.command
            assert len(restored.sections) == len(report.sections)

    def test_markdown_output_50_reports(self):
        """50 reports rendered to markdown — all non-empty."""
        for i in range(50):
            report = _make_report(i)
            md = ReportFormatter.to_markdown(report)
            assert f"Soak report {i}" in md
            assert "| Status |" in md

    def test_registry_list_after_bulk_save(self, tmp_path):
        """Save 30 reports, then list them — count matches."""
        registry = ReportRegistry(reports_dir=tmp_path / "soak_reports")
        for i in range(30):
            report = _make_report(i)
            registry.save_report(report)

        listing = registry.list_reports(limit=50)
        assert len(listing) == 30

    def test_registry_get_after_bulk_save(self, tmp_path):
        """Save 20 reports, retrieve each by ID."""
        registry = ReportRegistry(reports_dir=tmp_path / "soak_get")
        ids = []
        for i in range(20):
            report = _make_report(i)
            ids.append(report.id)
            registry.save_report(report)

        for rid in ids:
            loaded = registry.get_report(rid)
            assert loaded is not None
            assert loaded.id == rid


# ---------------------------------------------------------------------------
# 6. Retry / idempotency tests
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestRetryIdempotency:
    """Simulate failures mid-execution, verify consistent outcomes."""

    def test_same_dag_same_result(self):
        """Identical DAG config produces identical results every time."""
        reference = None
        for _ in range(50):
            dag = _make_diamond_dag()
            dag.execute(max_workers=2)
            summary = dag.status_summary()
            if reference is None:
                reference = summary
            else:
                assert summary == reference

    def test_partial_failure_idempotent(self):
        """DAG with one failing node always produces same status map."""
        for _ in range(50):
            dag = DAGExecutor()
            dag.add_node("a", "A", action=_noop)
            dag.add_node("b", "B", action=_failing, depends_on=["a"])
            dag.add_node("c", "C", action=_noop, depends_on=["a"])
            dag.add_node("d", "D", action=_noop, depends_on=["b", "c"])
            dag.execute(max_workers=2)

            assert dag.get_node("a").status == NodeStatus.done
            assert dag.get_node("b").status == NodeStatus.failed
            assert dag.get_node("c").status == NodeStatus.done
            assert dag.get_node("d").status == NodeStatus.skipped

    def test_transient_failure_retry(self):
        """Simulate transient failures — first N calls fail, then succeed."""
        call_count = {"n": 0}

        def transient_action():
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise RuntimeError("transient")
            return "recovered"

        # First attempt fails
        dag1 = DAGExecutor()
        dag1.add_node("t", "Transient", action=transient_action)
        dag1.execute()
        assert dag1.get_node("t").status == NodeStatus.failed

        # Second attempt also fails (count == 2)
        call_count["n"] = 1  # reset to 1 so next call is #2
        dag2 = DAGExecutor()
        dag2.add_node("t", "Transient", action=transient_action)
        dag2.execute()
        assert dag2.get_node("t").status == NodeStatus.failed

        # Third attempt succeeds (count == 3)
        dag3 = DAGExecutor()
        dag3.add_node("t", "Transient", action=transient_action)
        dag3.execute()
        assert dag3.get_node("t").status == NodeStatus.done
        assert dag3.get_node("t").result == "recovered"

    def test_policy_check_idempotent(self):
        """Same command always gets same policy decision."""
        engine = PolicyEngine()
        for _ in range(100):
            d = engine.check_command("rm -rf /")
            assert d.action == PolicyAction.deny
            assert d.policy_name == "destructive-commands"


# ---------------------------------------------------------------------------
# 7. Resource cleanup — thread leaks, file handle leaks
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestResourceCleanup:
    """Verify no threads or file handles leak after repeated runs."""

    def test_no_thread_leak_after_dag_runs(self):
        """Thread count should not grow after many DAG executions."""
        # Warm-up
        for _ in range(5):
            dag = _make_diamond_dag()
            dag.execute(max_workers=2)

        baseline_threads = threading.active_count()

        for _ in range(50):
            dag = _make_diamond_dag()
            dag.execute(max_workers=4)

        # Allow a small margin (GC may not have cleaned up daemon threads yet)
        time.sleep(0.1)
        final_threads = threading.active_count()
        growth = final_threads - baseline_threads
        assert growth <= 2, (
            f"Thread leak detected: baseline={baseline_threads}, final={final_threads}, growth={growth}"
        )

    def test_no_thread_leak_concurrent_dags(self):
        """Running concurrent DAGs should not leak threads."""
        # Warm-up
        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = [pool.submit(_make_diamond_dag().execute, 2) for _ in range(5)]
            for f in futs:
                f.result()

        time.sleep(0.1)
        baseline = threading.active_count()

        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = [pool.submit(lambda: _make_diamond_dag().execute(2)) for _ in range(20)]
            for f in futs:
                f.result()

        time.sleep(0.2)
        final = threading.active_count()
        growth = final - baseline
        assert growth <= 2, f"Thread leak: {baseline} -> {final}"

    def test_no_file_handle_leak_reports(self, tmp_path):
        """Writing many reports should not leak file handles."""
        import os

        registry = ReportRegistry(reports_dir=tmp_path / "fh_test")

        # Count open fds (Linux)
        def count_fds():
            try:
                return len(os.listdir(f"/proc/{os.getpid()}/fd"))
            except (FileNotFoundError, PermissionError):
                return -1  # not on Linux or no access

        baseline = count_fds()
        if baseline == -1:
            pytest.skip("Cannot count file descriptors on this platform")

        for i in range(50):
            report = _make_report(i)
            registry.save_report(report)

        gc.collect()
        final = count_fds()
        growth = final - baseline
        # Some growth is expected for directory handles; cap at 10
        assert growth < 10, f"File handle leak: {baseline} -> {final} (growth={growth})"

    def test_gc_collects_dag_objects(self):
        """DAG objects become garbage-collectible after use."""
        import weakref

        refs = []
        for _ in range(20):
            dag = _make_simple_dag(5)
            dag.execute(max_workers=2)
            refs.append(weakref.ref(dag))

        del dag
        gc.collect()

        alive = sum(1 for r in refs if r() is not None)
        # At most 1 might still be alive due to the last ref in the loop
        assert alive <= 1, f"{alive} of 20 DAG objects still alive after gc"


# ---------------------------------------------------------------------------
# 8. Edge cases under stress
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestEdgeCasesStress:
    """DAG structural edge cases run repeatedly to flush out rare bugs."""

    def test_empty_dag_concurrent(self):
        """50 empty DAGs executed concurrently."""
        results = {}

        def run_empty(idx):
            dag = DAGExecutor()
            results[idx] = dag.execute()

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(run_empty, i) for i in range(50)]
            for f in as_completed(futures, timeout=10):
                f.result()

        assert len(results) == 50
        for r in results.values():
            assert r == {}

    def test_single_node_concurrent(self):
        """50 single-node DAGs concurrently."""
        results = {}

        def run_single(idx):
            dag = DAGExecutor()
            dag.add_node("s", "Solo", action=lambda: idx)
            dag.execute()
            results[idx] = dag.get_node("s").result

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(run_single, i) for i in range(50)]
            for f in as_completed(futures, timeout=10):
                f.result()

        assert len(results) == 50

    def test_deep_chain_dag(self):
        """50-level deep chain — no stack overflow or performance collapse."""
        depth = 50
        dag = DAGExecutor()
        for i in range(depth):
            deps = [f"n{i-1}"] if i > 0 else None
            dag.add_node(f"n{i}", f"Node-{i}", action=_noop, depends_on=deps)

        dag.execute(max_workers=2)
        assert dag.status_summary()["done"] == depth
        # Last node must have completed
        assert dag.get_node(f"n{depth-1}").status == NodeStatus.done

    def test_deep_chain_repeated(self):
        """Run 50-level chain 20 times — must always succeed."""
        for _ in range(20):
            dag = DAGExecutor()
            for i in range(50):
                deps = [f"n{i-1}"] if i > 0 else None
                dag.add_node(f"n{i}", f"Node-{i}", action=_noop, depends_on=deps)
            dag.execute(max_workers=2)
            assert dag.status_summary()["done"] == 50

    def test_wide_fan_out_stress(self):
        """Root with 100 children — must complete all."""
        dag = DAGExecutor()
        dag.add_node("root", "Root", action=_noop)
        for i in range(100):
            dag.add_node(f"c{i}", f"Child-{i}", action=_noop, depends_on=["root"])
        dag.execute(max_workers=8)
        assert dag.status_summary()["done"] == 101

    def test_wide_fan_in_stress(self):
        """100 roots converging to one sink — must complete."""
        dag = DAGExecutor()
        root_ids = []
        for i in range(100):
            nid = f"r{i}"
            dag.add_node(nid, f"Root-{i}", action=_noop)
            root_ids.append(nid)
        dag.add_node("sink", "Sink", action=_noop, depends_on=root_ids)
        dag.execute(max_workers=8)
        assert dag.get_node("sink").status == NodeStatus.done

    def test_circular_dependency_detection_stress(self):
        """Cycle detection must work reliably under repeated attempts."""
        for _ in range(100):
            dag = DAGExecutor()
            dag.add_node("a", "A", action=_noop, depends_on=["b"])
            dag.add_node("b", "B", action=_noop, depends_on=["a"])
            with pytest.raises(DAGError, match="Circular dependency"):
                dag.execute()

    def test_mixed_success_failure_fan_out(self):
        """Root fails, 50 children should all be skipped."""
        dag = DAGExecutor()
        dag.add_node("root", "Root", action=_failing)
        for i in range(50):
            dag.add_node(f"c{i}", f"Child-{i}", action=_noop, depends_on=["root"])
        dag.execute(max_workers=4)
        assert dag.get_node("root").status == NodeStatus.failed
        for i in range(50):
            assert dag.get_node(f"c{i}").status == NodeStatus.skipped

    def test_resource_conflict_under_concurrency(self):
        """Nodes sharing a resource must serialize even under load."""
        concurrent = {"max": 0, "current": 0}
        lock = threading.Lock()

        def guarded_action():
            with lock:
                concurrent["current"] += 1
                concurrent["max"] = max(concurrent["max"], concurrent["current"])
            time.sleep(0.01)
            with lock:
                concurrent["current"] -= 1
            return "ok"

        for _ in range(20):
            concurrent["max"] = 0
            concurrent["current"] = 0
            dag = DAGExecutor()
            for i in range(5):
                dag.add_node(
                    f"n{i}", f"N{i}", action=guarded_action, resources=["shared"]
                )
            dag.execute(max_workers=4)
            assert concurrent["max"] == 1, (
                f"Resource conflict: max concurrent = {concurrent['max']}"
            )
            assert dag.status_summary()["done"] == 5


# ---------------------------------------------------------------------------
# 9. Serialization / to_dict under stress
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestSerializationStress:
    """Verify DAG serialization is consistent under repeated use."""

    def test_to_dict_100_times(self):
        """to_dict must produce valid structure every time."""
        for _ in range(100):
            dag = _make_diamond_dag()
            dag.execute(max_workers=2)
            d = dag.to_dict()
            assert "nodes" in d
            assert "summary" in d
            assert len(d["nodes"]) == 4
            assert d["summary"]["done"] == 4

    def test_to_ascii_100_times(self):
        """to_ascii must never crash."""
        for _ in range(100):
            dag = _make_diamond_dag()
            dag.execute(max_workers=2)
            text = dag.to_ascii()
            assert "[+]" in text  # done symbol

    def test_to_json_concurrent(self):
        """Concurrent JSON serialization of reports."""
        reports = [_make_report(i) for i in range(50)]
        results = {}

        def serialize(idx):
            j = ReportFormatter.to_json(reports[idx])
            data = json.loads(j)
            results[idx] = data["title"]

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(serialize, i) for i in range(50)]
            for f in as_completed(futures, timeout=10):
                f.result()

        assert len(results) == 50
        for i in range(50):
            assert results[i] == f"Soak report {i}"


# ---------------------------------------------------------------------------
# 10. Combined subsystem stress
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestCombinedStress:
    """Exercise multiple subsystems simultaneously."""

    def test_dag_plus_policy_plus_report(self):
        """Run DAG, check policies, generate report — 50 iterations."""
        engine = PolicyEngine()
        for i in range(50):
            # DAG
            dag = _make_diamond_dag()
            dag.execute(max_workers=2)
            assert dag.status_summary()["done"] == 4

            # Policy
            d = engine.check_command("echo safe")
            assert d.action == PolicyAction.allow

            # Report
            report = _make_report(i)
            j = ReportFormatter.to_json(report)
            data = json.loads(j)
            assert data["title"] == f"Soak report {i}"

    def test_all_subsystems_concurrent(self):
        """Mix of DAG/policy/report tasks in a shared thread pool."""
        results = {"dag": 0, "policy": 0, "report": 0}
        lock = threading.Lock()

        def dag_task():
            dag = _make_diamond_dag()
            dag.execute(max_workers=2)
            assert dag.status_summary()["done"] == 4
            with lock:
                results["dag"] += 1

        def policy_task():
            engine = PolicyEngine()
            for cmd in ["echo hi", "rm -rf /", "ls"]:
                engine.check_command(cmd)
            with lock:
                results["policy"] += 1

        def report_task():
            report = _make_report(0)
            ReportFormatter.to_json(report)
            ReportFormatter.to_markdown(report)
            with lock:
                results["report"] += 1

        tasks = []
        for _ in range(10):
            tasks.extend([dag_task, policy_task, report_task])

        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = [pool.submit(t) for t in tasks]
            for f in as_completed(futures, timeout=30):
                f.result()

        assert results["dag"] == 10
        assert results["policy"] == 10
        assert results["report"] == 10
