"""Multi-agent role routing with per-role skill mapping."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    planner = "planner"
    executor = "executor"
    verifier = "verifier"


ROLE_SKILL_TYPES: dict[Role, set[str]] = {
    Role.planner: {"planning", "analysis"},
    Role.executor: {"execution", ""},
    Role.verifier: {"validation", "testing"},
}

# Keywords for auto-assigning roles to tasks
PLANNER_KEYWORDS = {
    "plan", "analyze", "design", "review", "decompose",
    "suggest", "assess", "propose", "outline", "evaluate",
}
VERIFIER_KEYWORDS = {
    "verify", "test", "check", "validate", "audit",
    "confirm", "assert", "inspect", "scan", "lint",
}


@dataclass
class RoleAssignment:
    task_id: int
    role: Role
    reason: str = ""


class RoleRouter:
    """Assign agent roles to tasks and gate skill execution by role."""

    def __init__(self, allowed_roles: list[Role] | None = None):
        self.allowed_roles = allowed_roles or list(Role)

    def assign_role(self, task_id: int, requirement: str) -> RoleAssignment:
        """Assign a role to a single task based on requirement keywords."""
        tokens = set(requirement.lower().split())
        if tokens & PLANNER_KEYWORDS:
            matched = tokens & PLANNER_KEYWORDS
            return RoleAssignment(
                task_id=task_id,
                role=Role.planner,
                reason=f"matched: {', '.join(sorted(matched))}",
            )
        if tokens & VERIFIER_KEYWORDS:
            matched = tokens & VERIFIER_KEYWORDS
            return RoleAssignment(
                task_id=task_id,
                role=Role.verifier,
                reason=f"matched: {', '.join(sorted(matched))}",
            )
        return RoleAssignment(task_id=task_id, role=Role.executor, reason="default")

    def assign_roles(self, tasks: list) -> list[RoleAssignment]:
        """Assign roles to all tasks. Each task must have .id and .requirement."""
        return [self.assign_role(t.id, t.requirement) for t in tasks]

    def can_execute(self, skill_type: str, role: Role) -> bool:
        """Check if a role is allowed to run a skill of given type."""
        allowed = ROLE_SKILL_TYPES.get(role, set())
        return skill_type in allowed

    def filter_skills(self, skills: list, role: Role) -> list:
        """Return skills allowed for a given role (each skill must have .skill_type)."""
        allowed_types = ROLE_SKILL_TYPES.get(role, set())
        return [s for s in skills if s.skill_type in allowed_types]
