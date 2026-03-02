"""Base types for the workflow engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class WorkflowError(Exception):
    """Raised on workflow loading or execution failures."""


class StepType(StrEnum):
    shell = "shell"
    claude_prompt = "claude_prompt"
    skill = "skill"
    http = "http"
    approval_gate = "approval_gate"


class StepStatus(StrEnum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    skipped = "skipped"


class WorkflowStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    aborted = "aborted"


@dataclass
class StepResult:
    step_name: str
    status: StepStatus
    output: str = ""
    error: str = ""
    duration_ms: int = 0


@dataclass
class StepConfig:
    name: str
    type: StepType
    command: str
    args: dict = field(default_factory=dict)
    condition: str = ""
    on_failure: str = "abort"  # "continue", "abort", "rollback"
    timeout: int = 300


@dataclass
class WorkflowConfig:
    name: str
    description: str = ""
    steps: list[StepConfig] = field(default_factory=list)
    rollback_steps: list[StepConfig] = field(default_factory=list)
    notify_profile: str = ""
