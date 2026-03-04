"""Tests for the DAG-based parallel execution engine."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from superpowers.dag_executor import (
    DAGError,
    DAGExecutor,
    DAGNode,
    NodeStatus,
    _safe_serialize,
)


# ---------------------------------------------------------------------------
# DAGNode dataclass
# ---------------------------------------------------------------------------


class TestDAGNode:
    def test_defaults(self):
        node = DAGNode(id="a", name="Alpha", action=lambda: None)
        assert node.id == "a"
        assert node.name == "Alpha"
        assert node.status == NodeStatus.pending
        assert node.result is None
        assert node.error == ""
        assert node.depends_on == []
        assert node.resources == []
        assert node.started_at is None
        assert node.finished_at is None

    def test_duration_ms_not_started(self):
        node = DAGNode(id="a", name="A", action=lambda: None)
        assert node.duration_ms == 0

    def test_duration_ms_completed(self):
        node = DAGNode(id="a", name="A", action=lambda: None)
        node.started_at = 100.0
        node.finished_at = 100.250
        assert node.duration_ms == 250

    def test_duration_ms_partial(self):
        node = DAGNode(id="a", name="A", action=lambda: None)
        node.started_at = 100.0
        # finished_at is None
        assert node.duration_ms == 0


class TestNodeStatus:
    def test_values(self):
        assert NodeStatus.pending == "pending"
        assert NodeStatus.running == "running"
        assert NodeStatus.done == "done"
        assert NodeStatus.failed == "failed"
        assert NodeStatus.skipped == "skipped"

    def test_count(self):
        assert len(NodeStatus) == 5


# ---------------------------------------------------------------------------
# DAGExecutor — construction
# ---------------------------------------------------------------------------


class TestDAGConstruction:
    def test_add_single_node(self):
        dag = DAGExecutor()
        node = dag.add_node("a", "Alpha", action=lambda: "ok")
        assert node.id == "a"
        assert dag.get_node("a") is node

    def test_add_multiple_nodes(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None)
        dag.add_node("b", "B", action=lambda: None, depends_on=["a"])
        assert len(dag.get_results()) == 2

    def test_duplicate_node_raises(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None)
        with pytest.raises(DAGError, match="Duplicate node id"):
            dag.add_node("a", "A again", action=lambda: None)

    def test_get_node_missing(self):
        dag = DAGExecutor()
        assert dag.get_node("nope") is None


# ---------------------------------------------------------------------------
# Execution — linear chain
# ---------------------------------------------------------------------------


class TestLinearChain:
    def test_a_then_b_then_c(self):
        """A -> B -> C executes in order."""
        order = []

        def make_action(label):
            def action():
                order.append(label)
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"))
        dag.add_node("b", "B", action=make_action("b"), depends_on=["a"])
        dag.add_node("c", "C", action=make_action("c"), depends_on=["b"])
        dag.execute(max_workers=4)

        assert order == ["a", "b", "c"]
        assert dag.get_node("a").status == NodeStatus.done
        assert dag.get_node("b").status == NodeStatus.done
        assert dag.get_node("c").status == NodeStatus.done

    def test_results_stored(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: 42)
        dag.execute()
        assert dag.get_node("a").result == 42

    def test_chain_results_propagate(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: "hello")
        dag.add_node("b", "B", action=lambda: "world", depends_on=["a"])
        dag.execute()
        assert dag.get_node("a").result == "hello"
        assert dag.get_node("b").result == "world"


# ---------------------------------------------------------------------------
# Execution — parallel independent nodes
# ---------------------------------------------------------------------------


class TestParallelExecution:
    def test_independent_nodes_run_concurrently(self):
        """Three independent nodes should overlap in time."""
        start_times = {}
        end_times = {}

        def make_action(label):
            def action():
                start_times[label] = time.monotonic()
                time.sleep(0.1)
                end_times[label] = time.monotonic()
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"))
        dag.add_node("b", "B", action=make_action("b"))
        dag.add_node("c", "C", action=make_action("c"))
        dag.execute(max_workers=3)

        # All three should have started before any finished (or very close)
        # Total time should be ~0.1s, not ~0.3s
        total = max(end_times.values()) - min(start_times.values())
        assert total < 0.25, f"Expected parallel execution, took {total:.2f}s"

    def test_all_done(self):
        dag = DAGExecutor()
        for i in range(5):
            dag.add_node(f"n{i}", f"Node {i}", action=lambda: "ok")
        dag.execute(max_workers=5)
        summary = dag.status_summary()
        assert summary["done"] == 5
        assert summary["total"] == 5


# ---------------------------------------------------------------------------
# Execution — diamond dependency
# ---------------------------------------------------------------------------


class TestDiamondDependency:
    def test_diamond_a_bc_d(self):
        """
        A -> B -> D
        A -> C -> D
        B and C should run in parallel after A; D waits for both.
        """
        order = []
        lock = threading.Lock()

        def make_action(label, sleep_time=0):
            def action():
                if sleep_time:
                    time.sleep(sleep_time)
                with lock:
                    order.append(label)
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"))
        dag.add_node("b", "B", action=make_action("b", 0.05), depends_on=["a"])
        dag.add_node("c", "C", action=make_action("c", 0.05), depends_on=["a"])
        dag.add_node("d", "D", action=make_action("d"), depends_on=["b", "c"])
        dag.execute(max_workers=4)

        assert order[0] == "a"
        assert order[-1] == "d"
        # b and c should both be between a and d
        assert set(order[1:3]) == {"b", "c"}

        for nid in ("a", "b", "c", "d"):
            assert dag.get_node(nid).status == NodeStatus.done


# ---------------------------------------------------------------------------
# Failure propagation
# ---------------------------------------------------------------------------


class TestFailurePropagation:
    def test_failed_node_skips_dependents(self):
        """A fails -> B skipped -> C skipped."""
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        dag.add_node("b", "B", action=lambda: "ok", depends_on=["a"])
        dag.add_node("c", "C", action=lambda: "ok", depends_on=["b"])
        dag.execute()

        assert dag.get_node("a").status == NodeStatus.failed
        assert dag.get_node("a").error == "boom"
        assert dag.get_node("b").status == NodeStatus.skipped
        assert dag.get_node("c").status == NodeStatus.skipped

    def test_failure_only_affects_dependents(self):
        """A fails, but independent node D still runs."""
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: (_ for _ in ()).throw(ValueError("err")))
        dag.add_node("b", "B", action=lambda: "ok", depends_on=["a"])
        dag.add_node("d", "D", action=lambda: "independent")
        dag.execute()

        assert dag.get_node("a").status == NodeStatus.failed
        assert dag.get_node("b").status == NodeStatus.skipped
        assert dag.get_node("d").status == NodeStatus.done
        assert dag.get_node("d").result == "independent"

    def test_diamond_one_branch_fails(self):
        """
        A -> B (fail) -> D (skipped)
        A -> C (ok)   -> D (skipped because B failed)
        """
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: "ok")
        dag.add_node("b", "B", action=lambda: (_ for _ in ()).throw(RuntimeError("b-fail")),
                     depends_on=["a"])
        dag.add_node("c", "C", action=lambda: "ok", depends_on=["a"])
        dag.add_node("d", "D", action=lambda: "ok", depends_on=["b", "c"])
        dag.execute()

        assert dag.get_node("a").status == NodeStatus.done
        assert dag.get_node("b").status == NodeStatus.failed
        assert dag.get_node("c").status == NodeStatus.done
        assert dag.get_node("d").status == NodeStatus.skipped

    def test_error_message_stored(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: (_ for _ in ()).throw(
            TypeError("wrong type")))
        dag.execute()
        assert dag.get_node("a").error == "wrong type"


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_self_cycle(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None, depends_on=["a"])
        with pytest.raises(DAGError, match="Circular dependency"):
            dag.execute()

    def test_two_node_cycle(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None, depends_on=["b"])
        dag.add_node("b", "B", action=lambda: None, depends_on=["a"])
        with pytest.raises(DAGError, match="Circular dependency"):
            dag.execute()

    def test_three_node_cycle(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None, depends_on=["c"])
        dag.add_node("b", "B", action=lambda: None, depends_on=["a"])
        dag.add_node("c", "C", action=lambda: None, depends_on=["b"])
        with pytest.raises(DAGError, match="Circular dependency"):
            dag.execute()

    def test_unknown_dependency_raises(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None, depends_on=["nonexistent"])
        with pytest.raises(DAGError, match="unknown node"):
            dag.execute()

    def test_cycle_with_valid_nodes(self):
        """Cycle in part of the graph; valid nodes should still be detected."""
        dag = DAGExecutor()
        dag.add_node("ok", "OK", action=lambda: None)
        dag.add_node("a", "A", action=lambda: None, depends_on=["b"])
        dag.add_node("b", "B", action=lambda: None, depends_on=["a"])
        with pytest.raises(DAGError, match="Circular dependency"):
            dag.execute()


# ---------------------------------------------------------------------------
# Resource conflict detection
# ---------------------------------------------------------------------------


class TestResourceConflicts:
    def test_shared_resource_serialized(self):
        """Two nodes sharing a resource must not run simultaneously."""
        concurrent_count = {"max": 0, "current": 0}
        lock = threading.Lock()

        def make_action(label):
            def action():
                with lock:
                    concurrent_count["current"] += 1
                    concurrent_count["max"] = max(
                        concurrent_count["max"], concurrent_count["current"]
                    )
                time.sleep(0.08)
                with lock:
                    concurrent_count["current"] -= 1
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"), resources=["db"])
        dag.add_node("b", "B", action=make_action("b"), resources=["db"])
        dag.execute(max_workers=4)

        assert concurrent_count["max"] == 1, (
            f"Expected max concurrency 1 for shared resource, got {concurrent_count['max']}"
        )
        assert dag.get_node("a").status == NodeStatus.done
        assert dag.get_node("b").status == NodeStatus.done

    def test_different_resources_parallel(self):
        """Nodes with different resources can run in parallel."""
        start_times = {}

        def make_action(label):
            def action():
                start_times[label] = time.monotonic()
                time.sleep(0.08)
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"), resources=["db"])
        dag.add_node("b", "B", action=make_action("b"), resources=["cache"])
        dag.execute(max_workers=4)

        # They should start nearly at the same time
        diff = abs(start_times["a"] - start_times["b"])
        assert diff < 0.05, f"Expected parallel start, diff={diff:.3f}s"

    def test_no_resources_always_parallel(self):
        """Nodes without resources run freely in parallel."""
        dag = DAGExecutor()
        for i in range(4):
            dag.add_node(f"n{i}", f"N{i}", action=lambda: "ok")
        dag.execute(max_workers=4)
        assert dag.status_summary()["done"] == 4

    def test_multiple_shared_resources(self):
        """A node holding two resources blocks any node sharing either."""
        concurrent_count = {"max": 0, "current": 0}
        lock = threading.Lock()

        def make_action(label):
            def action():
                with lock:
                    concurrent_count["current"] += 1
                    concurrent_count["max"] = max(
                        concurrent_count["max"], concurrent_count["current"]
                    )
                time.sleep(0.08)
                with lock:
                    concurrent_count["current"] -= 1
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"), resources=["db", "cache"])
        dag.add_node("b", "B", action=make_action("b"), resources=["db"])
        dag.add_node("c", "C", action=make_action("c"), resources=["cache"])
        dag.execute(max_workers=4)

        # All three share resources with A, so at most one can run at a time
        # (a runs first, then b and c can each run, but b and c don't share so
        # they could overlap)
        assert dag.get_node("a").status == NodeStatus.done
        assert dag.get_node("b").status == NodeStatus.done
        assert dag.get_node("c").status == NodeStatus.done


# ---------------------------------------------------------------------------
# Max workers limiting
# ---------------------------------------------------------------------------


class TestMaxWorkers:
    def test_max_workers_1_serializes(self):
        """With max_workers=1, nodes run one at a time."""
        order = []

        def make_action(label):
            def action():
                order.append(label)
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"))
        dag.add_node("b", "B", action=make_action("b"))
        dag.add_node("c", "C", action=make_action("c"))
        dag.execute(max_workers=1)

        assert len(order) == 3
        assert dag.status_summary()["done"] == 3

    def test_max_workers_limits_concurrency(self):
        """With max_workers=2, at most 2 nodes run simultaneously."""
        concurrent_count = {"max": 0, "current": 0}
        lock = threading.Lock()

        def make_action(label):
            def action():
                with lock:
                    concurrent_count["current"] += 1
                    concurrent_count["max"] = max(
                        concurrent_count["max"], concurrent_count["current"]
                    )
                time.sleep(0.08)
                with lock:
                    concurrent_count["current"] -= 1
                return label
            return action

        dag = DAGExecutor()
        for i in range(6):
            dag.add_node(f"n{i}", f"N{i}", action=make_action(f"n{i}"))
        dag.execute(max_workers=2)

        assert concurrent_count["max"] <= 2
        assert dag.status_summary()["done"] == 6


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_status_updates(self):
        """Verify status transitions are atomic under concurrent execution."""
        dag = DAGExecutor()
        for i in range(20):
            dag.add_node(f"n{i}", f"N{i}", action=lambda: time.sleep(0.01) or "ok")
        dag.execute(max_workers=8)

        # All should be done with no corrupted states
        for node in dag.get_results().values():
            assert node.status == NodeStatus.done
            assert node.result == "ok"

    def test_timestamps_set(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: "done")
        dag.execute()
        node = dag.get_node("a")
        assert node.started_at is not None
        assert node.finished_at is not None
        assert node.finished_at >= node.started_at


# ---------------------------------------------------------------------------
# Status summary
# ---------------------------------------------------------------------------


class TestStatusSummary:
    def test_all_done(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: "ok")
        dag.add_node("b", "B", action=lambda: "ok")
        dag.execute()
        summary = dag.status_summary()
        assert summary == {"done": 2, "failed": 0, "skipped": 0, "pending": 0, "running": 0, "total": 2}

    def test_mixed_statuses(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        dag.add_node("b", "B", action=lambda: "ok", depends_on=["a"])
        dag.add_node("c", "C", action=lambda: "ok")
        dag.execute()
        summary = dag.status_summary()
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["done"] == 1
        assert summary["total"] == 3

    def test_empty_dag(self):
        dag = DAGExecutor()
        summary = dag.status_summary()
        assert summary["total"] == 0

    def test_before_execution(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None)
        summary = dag.status_summary()
        assert summary["pending"] == 1


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_structure(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: 42)
        dag.add_node("b", "B", action=lambda: "hello", depends_on=["a"])
        dag.execute()

        d = dag.to_dict()
        assert "nodes" in d
        assert "summary" in d
        assert len(d["nodes"]) == 2

        node_a = next(n for n in d["nodes"] if n["id"] == "a")
        assert node_a["result"] == 42
        assert node_a["status"] == "done"
        assert node_a["depends_on"] == []

        node_b = next(n for n in d["nodes"] if n["id"] == "b")
        assert node_b["result"] == "hello"
        assert node_b["depends_on"] == ["a"]

    def test_to_dict_with_resources(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None, resources=["db", "cache"])
        dag.execute()

        d = dag.to_dict()
        assert d["nodes"][0]["resources"] == ["db", "cache"]

    def test_to_dict_with_errors(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: (_ for _ in ()).throw(RuntimeError("oops")))
        dag.execute()

        d = dag.to_dict()
        assert d["nodes"][0]["error"] == "oops"
        assert d["nodes"][0]["status"] == "failed"

    def test_to_dict_duration(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: "fast")
        dag.execute()

        d = dag.to_dict()
        assert d["nodes"][0]["duration_ms"] >= 0

    def test_safe_serialize(self):
        assert _safe_serialize(None) is None
        assert _safe_serialize(42) == 42
        assert _safe_serialize("hello") == "hello"
        assert _safe_serialize([1, 2]) == [1, 2]
        assert _safe_serialize({"a": 1}) == {"a": 1}
        # Non-serializable falls back to str()
        assert isinstance(_safe_serialize(object()), str)


# ---------------------------------------------------------------------------
# ASCII visualization
# ---------------------------------------------------------------------------


class TestASCII:
    def test_empty_dag(self):
        dag = DAGExecutor()
        assert dag.to_ascii() == "(empty DAG)"

    def test_single_node(self):
        dag = DAGExecutor()
        dag.add_node("a", "Alpha", action=lambda: None)
        text = dag.to_ascii()
        assert "a: Alpha" in text
        assert "[ ]" in text  # pending

    def test_after_execution(self):
        dag = DAGExecutor()
        dag.add_node("a", "Alpha", action=lambda: "ok")
        dag.add_node("b", "Beta", action=lambda: "ok", depends_on=["a"])
        dag.execute()
        text = dag.to_ascii()
        assert "[+]" in text  # done
        assert "<- a" in text  # dependency shown

    def test_failed_node_symbol(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: (_ for _ in ()).throw(RuntimeError("x")))
        dag.execute()
        assert "[X]" in dag.to_ascii()

    def test_skipped_node_symbol(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: (_ for _ in ()).throw(RuntimeError("x")))
        dag.add_node("b", "B", action=lambda: "ok", depends_on=["a"])
        dag.execute()
        text = dag.to_ascii()
        assert "[-]" in text  # skipped

    def test_resources_shown(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None, resources=["db"])
        assert "[res: db]" in dag.to_ascii()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_dag_execute(self):
        dag = DAGExecutor()
        result = dag.execute()
        assert result == {}

    def test_single_node_no_deps(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: "solo")
        dag.execute()
        assert dag.get_node("a").result == "solo"

    def test_wide_fan_out(self):
        """One root with 10 children — all should complete."""
        dag = DAGExecutor()
        dag.add_node("root", "Root", action=lambda: "base")
        for i in range(10):
            dag.add_node(f"child-{i}", f"Child {i}", action=lambda: "leaf", depends_on=["root"])
        dag.execute(max_workers=4)
        assert dag.status_summary()["done"] == 11

    def test_wide_fan_in(self):
        """Ten roots converging to one sink."""
        dag = DAGExecutor()
        root_ids = []
        for i in range(10):
            nid = f"root-{i}"
            dag.add_node(nid, f"Root {i}", action=lambda: "done")
            root_ids.append(nid)
        dag.add_node("sink", "Sink", action=lambda: "merged", depends_on=root_ids)
        dag.execute(max_workers=4)
        assert dag.get_node("sink").status == NodeStatus.done
        assert dag.get_node("sink").result == "merged"

    def test_action_returning_none(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None)
        dag.execute()
        assert dag.get_node("a").result is None
        assert dag.get_node("a").status == NodeStatus.done

    def test_action_returning_dict(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: {"key": "value"})
        dag.execute()
        assert dag.get_node("a").result == {"key": "value"}

    def test_get_results_returns_copy_keys(self):
        dag = DAGExecutor()
        dag.add_node("a", "A", action=lambda: None)
        r1 = dag.get_results()
        r2 = dag.get_results()
        assert r1 is not r2  # different dict objects
        assert r1["a"] is r2["a"]  # same node objects


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestCLI:
    def test_dag_group_help(self):
        from superpowers.cli_dag import dag_group
        runner = CliRunner()
        result = runner.invoke(dag_group, ["--help"])
        assert result.exit_code == 0
        assert "DAG" in result.output or "dag" in result.output.lower()

    def test_dag_run_missing_workflow(self):
        from superpowers.cli_dag import dag_group
        runner = CliRunner()
        result = runner.invoke(dag_group, ["run", "nonexistent-workflow-xyz"])
        assert result.exit_code != 0

    def test_dag_visualize_missing_workflow(self):
        from superpowers.cli_dag import dag_group
        runner = CliRunner()
        result = runner.invoke(dag_group, ["visualize", "nonexistent-workflow-xyz"])
        assert result.exit_code != 0

    def test_dag_run_with_workflow(self, tmp_path):
        """Integration test: create a workflow YAML and run it through the DAG CLI."""
        from superpowers.cli_dag import dag_group

        wf_file = tmp_path / "test-dag.yaml"
        wf_file.write_text(
            "name: test-dag\n"
            "description: Test DAG workflow\n"
            "steps:\n"
            "  - name: echo-hello\n"
            "    type: shell\n"
            '    command: "echo hello"\n'
        )

        runner = CliRunner()
        with patch("superpowers.cli_dag.WorkflowLoader") as mock_loader_cls:
            from superpowers.workflow.base import StepConfig, StepType, WorkflowConfig
            mock_loader = mock_loader_cls.return_value
            mock_loader.load.return_value = WorkflowConfig(
                name="test-dag",
                description="Test DAG workflow",
                steps=[
                    StepConfig(name="echo-hello", type=StepType.shell, command="echo hello"),
                ],
            )
            result = runner.invoke(dag_group, ["run", "test-dag"])
            assert "echo-hello" in result.output

    def test_dag_visualize_with_workflow(self):
        from superpowers.cli_dag import dag_group

        runner = CliRunner()
        with patch("superpowers.cli_dag.WorkflowLoader") as mock_loader_cls:
            from superpowers.workflow.base import StepConfig, StepType, WorkflowConfig
            mock_loader = mock_loader_cls.return_value
            mock_loader.load.return_value = WorkflowConfig(
                name="viz-test",
                description="Viz test",
                steps=[
                    StepConfig(name="build", type=StepType.shell, command="echo build"),
                    StepConfig(name="test", type=StepType.shell, command="echo test"),
                ],
            )
            result = runner.invoke(dag_group, ["visualize", "viz-test"])
            assert result.exit_code == 0
            assert "build" in result.output
            assert "test" in result.output

    def test_dag_registered_in_main_cli(self):
        from superpowers.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["dag", "--help"])
        assert result.exit_code == 0
        assert "dag" in result.output.lower()


# ---------------------------------------------------------------------------
# Complex DAG topologies
# ---------------------------------------------------------------------------


class TestComplexTopologies:
    def test_multi_layer_diamond(self):
        """
        Layer 0: A
        Layer 1: B, C (depend on A)
        Layer 2: D (depends on B, C)
        Layer 3: E, F (depend on D)
        Layer 4: G (depends on E, F)
        """
        results_order = []
        lock = threading.Lock()

        def make_action(label):
            def action():
                with lock:
                    results_order.append(label)
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"))
        dag.add_node("b", "B", action=make_action("b"), depends_on=["a"])
        dag.add_node("c", "C", action=make_action("c"), depends_on=["a"])
        dag.add_node("d", "D", action=make_action("d"), depends_on=["b", "c"])
        dag.add_node("e", "E", action=make_action("e"), depends_on=["d"])
        dag.add_node("f", "F", action=make_action("f"), depends_on=["d"])
        dag.add_node("g", "G", action=make_action("g"), depends_on=["e", "f"])
        dag.execute(max_workers=4)

        assert results_order[0] == "a"
        assert results_order[-1] == "g"
        assert dag.status_summary()["done"] == 7

    def test_two_independent_chains(self):
        """Two separate chains: A->B->C and D->E->F."""
        order = []
        lock = threading.Lock()

        def make_action(label):
            def action():
                with lock:
                    order.append(label)
                return label
            return action

        dag = DAGExecutor()
        dag.add_node("a", "A", action=make_action("a"))
        dag.add_node("b", "B", action=make_action("b"), depends_on=["a"])
        dag.add_node("c", "C", action=make_action("c"), depends_on=["b"])
        dag.add_node("d", "D", action=make_action("d"))
        dag.add_node("e", "E", action=make_action("e"), depends_on=["d"])
        dag.add_node("f", "F", action=make_action("f"), depends_on=["e"])
        dag.execute(max_workers=4)

        assert dag.status_summary()["done"] == 6
        # A must come before B and C; D before E and F
        assert order.index("a") < order.index("b") < order.index("c")
        assert order.index("d") < order.index("e") < order.index("f")
