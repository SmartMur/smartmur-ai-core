# Benchmark Baseline — Orchestration Performance

Established: 2026-03-06

## Purpose

This document records the initial performance baseline for the orchestration
subsystem. All future benchmark runs are compared against these thresholds to
detect regressions.

## Default Thresholds

| Scenario | Metric | Threshold | Direction |
|----------|--------|-----------|-----------|
| dag_throughput | duration_ms | 10000.0 | lower is better |
| dag_throughput | memory_peak_mb | 100.0 | lower is better |
| policy_evaluation | duration_ms | 5000.0 | lower is better |
| policy_evaluation | ops_per_sec | 100.0 | higher is better |
| orchestration_e2e | duration_ms | 5000.0 | lower is better |
| report_generation | duration_ms | 5000.0 | lower is better |
| report_generation | ops_per_sec | 10.0 | higher is better |

## Scenarios

### dag_throughput
Fan-out DAG with 50 parallel tasks depending on a root node, collected by a
single sink node. Measures thread pool scheduling overhead and dependency
resolution speed.

### policy_evaluation
1000 iterations of `PolicyEngine.check_command()` across 10 different command
strings (mix of allowed, denied, and approval-required).

### orchestration_e2e
5-step sequential DAG pipeline executed 3 times. Measures end-to-end
orchestration overhead.

### report_generation
50 iterations of JSON + Markdown rendering for a report with 5 sections and
50 items.

## How to Run

```bash
claw benchmark run              # run all and save
claw benchmark run --scenario dag_throughput   # single scenario
claw benchmark report           # show last results
claw benchmark list             # list scenarios
```

## Initial Baseline Results

Run `claw benchmark run` to populate this section with actual numbers. Results
are saved to `~/.claude-superpowers/benchmarks/`.

| Scenario | Duration (ms) | Ops/sec | Peak Memory (MB) |
|----------|--------------|---------|-------------------|
| (run benchmarks to fill) | | | |
