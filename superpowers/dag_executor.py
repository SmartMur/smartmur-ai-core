"""DAG-based parallel execution engine for multi-agent orchestration.

Provides dependency-aware parallel execution of task nodes using a directed
acyclic graph.  Nodes with satisfied dependencies run concurrently via
ThreadPoolExecutor.  Failed nodes cause their dependents to be skipped.
Optional resource-conflict detection prevents two nodes that share a resource
from running at the same time.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable


class DAGError(Exception):
    """Raised on DAG construction or execution failures."""


class NodeStatus(StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    skipped = "skipped"


@dataclass
class DAGNode:
    """A single task node in the execution DAG."""

    id: str
    name: str
    action: Callable[[], Any]
    depends_on: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.pending
    result: Any = None
    error: str = ""
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def duration_ms(self) -> int:
        """Wall-clock duration in milliseconds, or 0 if not completed."""
        if self.started_at is not None and self.finished_at is not None:
            return int((self.finished_at - self.started_at) * 1000)
        return 0


class DAGExecutor:
    """Execute a DAG of task nodes with dependency-aware parallelism.

    Usage::

        dag = DAGExecutor()
        dag.add_node("a", "Build", action=build_fn)
        dag.add_node("b", "Test", action=test_fn, depends_on=["a"])
        dag.execute(max_workers=4)
        print(dag.status_summary())
    """

    def __init__(self) -> None:
        self._nodes: dict[str, DAGNode] = {}
        self._lock = threading.Lock()
        self._executed = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        name: str,
        action: Callable[[], Any],
        depends_on: list[str] | None = None,
        resources: list[str] | None = None,
    ) -> DAGNode:
        """Register a task node in the DAG.

        Parameters
        ----------
        node_id:
            Unique identifier for this node.
        name:
            Human-readable name.
        action:
            A zero-argument callable that performs the work.  Its return value
            is stored in ``node.result``.
        depends_on:
            List of node IDs that must complete successfully before this node
            can start.
        resources:
            Optional list of shared resource names.  Two nodes that share a
            resource will never run concurrently.
        """
        if node_id in self._nodes:
            raise DAGError(f"Duplicate node id: {node_id}")
        node = DAGNode(
            id=node_id,
            name=name,
            action=action,
            depends_on=list(depends_on or []),
            resources=list(resources or []),
        )
        self._nodes[node_id] = node
        return node

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Validate the DAG: check references and detect cycles."""
        # Check that all depends_on references exist
        for node in self._nodes.values():
            for dep_id in node.depends_on:
                if dep_id not in self._nodes:
                    raise DAGError(
                        f"Node '{node.id}' depends on unknown node '{dep_id}'"
                    )

        # Cycle detection via Kahn's algorithm
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in self._nodes}
        for node in self._nodes.values():
            for dep_id in node.depends_on:
                adj[dep_id].append(node.id)
                in_degree[node.id] += 1

        queue: deque[str] = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        visited = 0
        while queue:
            nid = queue.popleft()
            visited += 1
            for child in adj[nid]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if visited != len(self._nodes):
            # Find the nodes involved in cycles for a useful error message
            cycle_nodes = [
                nid for nid, deg in in_degree.items() if deg > 0
            ]
            raise DAGError(
                f"Circular dependency detected involving nodes: "
                f"{', '.join(sorted(cycle_nodes))}"
            )

    def _topological_sort(self) -> list[str]:
        """Return node IDs in topological order (Kahn's algorithm)."""
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in self._nodes}
        for node in self._nodes.values():
            for dep_id in node.depends_on:
                adj[dep_id].append(node.id)
                in_degree[node.id] += 1

        queue: deque[str] = deque(
            sorted(nid for nid, deg in in_degree.items() if deg == 0)
        )
        order: list[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for child in sorted(adj[nid]):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
        return order

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, max_workers: int = 4) -> dict[str, DAGNode]:
        """Execute all nodes respecting dependencies and resource constraints.

        Nodes whose dependencies have all completed successfully are submitted
        to a thread pool.  When a node fails, all transitive dependents are
        marked as skipped.

        Parameters
        ----------
        max_workers:
            Maximum number of concurrent threads.

        Returns
        -------
        dict mapping node_id to the DAGNode (with result/status populated).
        """
        if not self._nodes:
            return {}

        self._validate()
        self._executed = True

        # Build reverse dependency map: child -> set of parents
        # and forward map: parent -> set of children
        children_of: dict[str, set[str]] = {nid: set() for nid in self._nodes}
        for node in self._nodes.values():
            for dep_id in node.depends_on:
                children_of[dep_id].add(node.id)

        # Track which resources are currently held
        held_resources: set[str] = set()
        # Nodes waiting because of resource conflicts (deps are met, but resource busy)
        resource_waiters: set[str] = set()

        # Track completion
        pending: set[str] = set(self._nodes.keys())
        in_flight: dict[str, Future] = {}

        def _deps_satisfied(node_id: str) -> bool:
            node = self._nodes[node_id]
            for dep_id in node.depends_on:
                dep = self._nodes[dep_id]
                if dep.status != NodeStatus.done:
                    return False
            return True

        def _can_acquire_resources(node_id: str) -> bool:
            node = self._nodes[node_id]
            if not node.resources:
                return True
            for res in node.resources:
                if res in held_resources:
                    return False
            return True

        def _acquire_resources(node_id: str) -> None:
            node = self._nodes[node_id]
            for res in node.resources:
                held_resources.add(res)

        def _release_resources(node_id: str) -> None:
            node = self._nodes[node_id]
            for res in node.resources:
                held_resources.discard(res)

        def _mark_skipped(node_id: str) -> None:
            """Recursively mark a node and all its transitive dependents as skipped."""
            node = self._nodes[node_id]
            if node.status in (NodeStatus.done, NodeStatus.failed):
                return
            with self._lock:
                node.status = NodeStatus.skipped
            pending.discard(node_id)
            resource_waiters.discard(node_id)
            for child_id in children_of[node_id]:
                _mark_skipped(child_id)

        def _run_node(node_id: str) -> Any:
            """Execute a single node's action (runs in worker thread)."""
            node = self._nodes[node_id]
            with self._lock:
                node.status = NodeStatus.running
                node.started_at = time.monotonic()
            try:
                result = node.action()
                with self._lock:
                    node.result = result
                    node.status = NodeStatus.done
                    node.finished_at = time.monotonic()
                return result
            except Exception as exc:
                with self._lock:
                    node.status = NodeStatus.failed
                    node.error = str(exc)
                    node.finished_at = time.monotonic()
                raise

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            while pending or in_flight:
                # Submit all ready nodes
                newly_submitted = set()
                for node_id in list(pending):
                    if node_id in in_flight:
                        continue
                    node = self._nodes[node_id]
                    if node.status == NodeStatus.skipped:
                        pending.discard(node_id)
                        continue

                    # Check if any dependency failed or was skipped
                    dep_failed = False
                    deps_ready = True
                    for dep_id in node.depends_on:
                        dep = self._nodes[dep_id]
                        if dep.status in (NodeStatus.failed, NodeStatus.skipped):
                            dep_failed = True
                            break
                        if dep.status != NodeStatus.done:
                            deps_ready = False

                    if dep_failed:
                        _mark_skipped(node_id)
                        continue

                    if not deps_ready:
                        continue

                    # Dependencies met — check resource conflicts
                    with self._lock:
                        if not _can_acquire_resources(node_id):
                            resource_waiters.add(node_id)
                            continue
                        _acquire_resources(node_id)
                        resource_waiters.discard(node_id)

                    pending.discard(node_id)
                    future = pool.submit(_run_node, node_id)
                    in_flight[node_id] = future
                    newly_submitted.add(node_id)

                if not in_flight:
                    # Nothing in flight and nothing can be submitted — we're done
                    # (remaining pending nodes should all be skipped)
                    for node_id in list(pending):
                        _mark_skipped(node_id)
                    break

                # Wait for at least one future to complete
                # We poll briefly to allow new submissions when resources free up
                completed = set()
                for node_id, future in list(in_flight.items()):
                    if future.done():
                        completed.add(node_id)

                if not completed:
                    # Block until at least one completes
                    # Use a short timeout so we can recheck resource waiters
                    for node_id, future in list(in_flight.items()):
                        try:
                            future.result(timeout=0.05)
                        except Exception:
                            pass
                        if future.done():
                            completed.add(node_id)
                            break

                for node_id in completed:
                    del in_flight[node_id]
                    with self._lock:
                        _release_resources(node_id)

                    node = self._nodes[node_id]
                    if node.status == NodeStatus.failed:
                        # Skip all transitive dependents
                        for child_id in children_of[node_id]:
                            _mark_skipped(child_id)

        return dict(self._nodes)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_results(self) -> dict[str, DAGNode]:
        """Return dict of node_id -> DAGNode with results."""
        return dict(self._nodes)

    def get_node(self, node_id: str) -> DAGNode | None:
        """Return a single node by ID, or None if not found."""
        return self._nodes.get(node_id)

    def status_summary(self) -> dict[str, int]:
        """Return counts of done/failed/skipped/pending/running nodes."""
        counts: dict[str, int] = {
            "done": 0,
            "failed": 0,
            "skipped": 0,
            "pending": 0,
            "running": 0,
            "total": len(self._nodes),
        }
        for node in self._nodes.values():
            counts[node.status.value] = counts.get(node.status.value, 0) + 1
        return counts

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation of the entire execution."""
        nodes = []
        for node in self._nodes.values():
            d = {
                "id": node.id,
                "name": node.name,
                "depends_on": node.depends_on,
                "resources": node.resources,
                "status": node.status.value,
                "result": _safe_serialize(node.result),
                "error": node.error,
                "started_at": node.started_at,
                "finished_at": node.finished_at,
                "duration_ms": node.duration_ms,
            }
            nodes.append(d)
        return {
            "nodes": nodes,
            "summary": self.status_summary(),
        }

    def to_ascii(self) -> str:
        """Return an ASCII visualization of the DAG structure."""
        if not self._nodes:
            return "(empty DAG)"

        lines: list[str] = []
        order = self._topological_sort()

        # Status symbols
        symbols = {
            NodeStatus.pending: "[ ]",
            NodeStatus.running: "[~]",
            NodeStatus.done: "[+]",
            NodeStatus.failed: "[X]",
            NodeStatus.skipped: "[-]",
        }

        # Find roots and build level map
        for node_id in order:
            node = self._nodes[node_id]
            sym = symbols.get(node.status, "[ ]")
            deps_str = ""
            if node.depends_on:
                deps_str = f" <- {', '.join(node.depends_on)}"
            res_str = ""
            if node.resources:
                res_str = f" [res: {', '.join(node.resources)}]"
            dur_str = ""
            if node.duration_ms:
                dur_str = f" ({node.duration_ms}ms)"
            lines.append(f"  {sym} {node.id}: {node.name}{deps_str}{res_str}{dur_str}")

        return "\n".join(lines)


def _safe_serialize(value: Any) -> Any:
    """Convert a value to something JSON-serializable."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_serialize(v) for k, v in value.items()}
    return str(value)
