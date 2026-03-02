"""Load and validate workflow definitions from YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from superpowers.workflow.base import StepConfig, StepType, WorkflowConfig, WorkflowError


class WorkflowLoader:
    def __init__(self, workflows_dir: Path | None = None):
        if workflows_dir is None:
            from superpowers.config import get_data_dir
            workflows_dir = get_data_dir() / "workflows"
        self._dir = workflows_dir

    def load(self, name: str) -> WorkflowConfig:
        path = self._dir / f"{name}.yaml"
        if not path.is_file():
            raise WorkflowError(f"Workflow not found: {name} (looked in {path})")

        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            raise WorkflowError(f"Invalid YAML in {path}: {exc}")

        return self._parse(data, name)

    def list_workflows(self) -> list[str]:
        if not self._dir.is_dir():
            return []
        return sorted(p.stem for p in self._dir.glob("*.yaml"))

    def validate(self, config: WorkflowConfig) -> list[str]:
        errors = []
        if not config.name:
            errors.append("Workflow name is required")
        if not config.steps:
            errors.append("Workflow must have at least one step")
        for i, step in enumerate(config.steps):
            if not step.name:
                errors.append(f"Step {i} missing name")
            if not step.command:
                errors.append(f"Step '{step.name}' missing command")
            if step.on_failure not in ("continue", "abort", "rollback"):
                errors.append(f"Step '{step.name}' invalid on_failure: {step.on_failure}")
        return errors

    def _parse(self, data: dict, name: str) -> WorkflowConfig:
        steps = [self._parse_step(s) for s in data.get("steps", [])]
        rollback = [self._parse_step(s) for s in data.get("rollback", [])]
        return WorkflowConfig(
            name=data.get("name", name),
            description=data.get("description", ""),
            steps=steps,
            rollback_steps=rollback,
            notify_profile=data.get("notify_profile", ""),
        )

    def _parse_step(self, raw: dict) -> StepConfig:
        return StepConfig(
            name=raw.get("name", ""),
            type=StepType(raw.get("type", "shell")),
            command=raw.get("command", ""),
            args=raw.get("args", {}),
            condition=raw.get("condition", ""),
            on_failure=raw.get("on_failure", "abort"),
            timeout=raw.get("timeout", 300),
        )
