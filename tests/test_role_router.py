"""Tests for multi-agent role routing with per-role skill mapping."""

from __future__ import annotations

import types

from superpowers.role_router import (
    PLANNER_KEYWORDS,
    ROLE_SKILL_TYPES,
    VERIFIER_KEYWORDS,
    Role,
    RoleAssignment,
    RoleRouter,
)

# --- Role enum ---

class TestRoleEnum:
    def test_role_values(self):
        assert Role.planner.value == "planner"
        assert Role.executor.value == "executor"
        assert Role.verifier.value == "verifier"

    def test_role_is_str_enum(self):
        assert isinstance(Role.planner, str)
        assert Role.planner == "planner"

    def test_role_members(self):
        assert set(Role) == {Role.planner, Role.executor, Role.verifier}


# --- ROLE_SKILL_TYPES mapping ---

class TestRoleSkillTypes:
    def test_planner_types(self):
        assert ROLE_SKILL_TYPES[Role.planner] == {"planning", "analysis"}

    def test_executor_types(self):
        assert ROLE_SKILL_TYPES[Role.executor] == {"execution", ""}

    def test_verifier_types(self):
        assert ROLE_SKILL_TYPES[Role.verifier] == {"validation", "testing"}


# --- RoleRouter.assign_role ---

class TestAssignRole:
    def setup_method(self):
        self.router = RoleRouter()

    def test_planner_keyword_plan(self):
        assignment = self.router.assign_role(1, "plan the deployment")
        assert assignment.role == Role.planner
        assert assignment.task_id == 1
        assert "plan" in assignment.reason

    def test_planner_keyword_analyze(self):
        assignment = self.router.assign_role(2, "analyze the logs")
        assert assignment.role == Role.planner
        assert "analyze" in assignment.reason

    def test_planner_keyword_design(self):
        assignment = self.router.assign_role(3, "design the architecture")
        assert assignment.role == Role.planner
        assert "design" in assignment.reason

    def test_planner_keyword_evaluate(self):
        assignment = self.router.assign_role(4, "evaluate current performance")
        assert assignment.role == Role.planner
        assert "evaluate" in assignment.reason

    def test_planner_keyword_propose(self):
        assignment = self.router.assign_role(5, "propose a solution")
        assert assignment.role == Role.planner
        assert "propose" in assignment.reason

    def test_planner_multiple_keywords(self):
        assignment = self.router.assign_role(6, "review and analyze the code")
        assert assignment.role == Role.planner
        # Should include both matched keywords in reason
        assert "analyze" in assignment.reason
        assert "review" in assignment.reason

    def test_all_planner_keywords_recognized(self):
        for keyword in PLANNER_KEYWORDS:
            assignment = self.router.assign_role(0, f"please {keyword} the task")
            assert assignment.role == Role.planner, f"keyword '{keyword}' not recognized as planner"

    def test_verifier_keyword_test(self):
        assignment = self.router.assign_role(1, "test the deployment")
        assert assignment.role == Role.verifier
        assert "test" in assignment.reason

    def test_verifier_keyword_validate(self):
        assignment = self.router.assign_role(2, "validate the output")
        assert assignment.role == Role.verifier
        assert "validate" in assignment.reason

    def test_verifier_keyword_check(self):
        assignment = self.router.assign_role(3, "check the config")
        assert assignment.role == Role.verifier
        assert "check" in assignment.reason

    def test_verifier_keyword_audit(self):
        assignment = self.router.assign_role(4, "audit the permissions")
        assert assignment.role == Role.verifier
        assert "audit" in assignment.reason

    def test_verifier_keyword_lint(self):
        assignment = self.router.assign_role(5, "lint the codebase")
        assert assignment.role == Role.verifier
        assert "lint" in assignment.reason

    def test_all_verifier_keywords_recognized(self):
        for keyword in VERIFIER_KEYWORDS:
            assignment = self.router.assign_role(0, f"please {keyword} the result")
            assert assignment.role == Role.verifier, f"keyword '{keyword}' not recognized as verifier"

    def test_default_to_executor(self):
        assignment = self.router.assign_role(1, "deploy to production")
        assert assignment.role == Role.executor
        assert assignment.reason == "default"

    def test_default_executor_no_keywords(self):
        assignment = self.router.assign_role(2, "run the build")
        assert assignment.role == Role.executor
        assert assignment.reason == "default"

    def test_planner_takes_priority_over_verifier(self):
        """When both planner and verifier keywords are present, planner wins."""
        assignment = self.router.assign_role(1, "plan and test the feature")
        assert assignment.role == Role.planner

    def test_case_insensitive(self):
        assignment = self.router.assign_role(1, "ANALYZE the Logs")
        assert assignment.role == Role.planner

    def test_empty_requirement_defaults_to_executor(self):
        assignment = self.router.assign_role(1, "")
        assert assignment.role == Role.executor
        assert assignment.reason == "default"


# --- RoleRouter.assign_roles ---

class TestAssignRoles:
    def setup_method(self):
        self.router = RoleRouter()

    def test_assign_roles_batch(self):
        tasks = [
            types.SimpleNamespace(id=1, requirement="plan the deploy"),
            types.SimpleNamespace(id=2, requirement="run the deploy"),
            types.SimpleNamespace(id=3, requirement="test the deploy"),
        ]
        assignments = self.router.assign_roles(tasks)
        assert len(assignments) == 3
        assert assignments[0].role == Role.planner
        assert assignments[1].role == Role.executor
        assert assignments[2].role == Role.verifier

    def test_assign_roles_empty_list(self):
        assert self.router.assign_roles([]) == []

    def test_assign_roles_preserves_task_ids(self):
        tasks = [
            types.SimpleNamespace(id=10, requirement="analyze data"),
            types.SimpleNamespace(id=20, requirement="deploy service"),
        ]
        assignments = self.router.assign_roles(tasks)
        assert assignments[0].task_id == 10
        assert assignments[1].task_id == 20


# --- RoleRouter.can_execute ---

class TestCanExecute:
    def setup_method(self):
        self.router = RoleRouter()

    def test_planner_can_execute_planning(self):
        assert self.router.can_execute("planning", Role.planner) is True

    def test_planner_can_execute_analysis(self):
        assert self.router.can_execute("analysis", Role.planner) is True

    def test_planner_cannot_execute_execution(self):
        assert self.router.can_execute("execution", Role.planner) is False

    def test_planner_cannot_execute_testing(self):
        assert self.router.can_execute("testing", Role.planner) is False

    def test_executor_can_execute_execution(self):
        assert self.router.can_execute("execution", Role.executor) is True

    def test_executor_can_execute_empty_type(self):
        assert self.router.can_execute("", Role.executor) is True

    def test_executor_cannot_execute_planning(self):
        assert self.router.can_execute("planning", Role.executor) is False

    def test_verifier_can_execute_validation(self):
        assert self.router.can_execute("validation", Role.verifier) is True

    def test_verifier_can_execute_testing(self):
        assert self.router.can_execute("testing", Role.verifier) is True

    def test_verifier_cannot_execute_execution(self):
        assert self.router.can_execute("execution", Role.verifier) is False

    def test_unknown_skill_type_rejected(self):
        assert self.router.can_execute("unknown_type", Role.executor) is False
        assert self.router.can_execute("unknown_type", Role.planner) is False
        assert self.router.can_execute("unknown_type", Role.verifier) is False


# --- RoleRouter.filter_skills ---

class TestFilterSkills:
    def setup_method(self):
        self.router = RoleRouter()

    def test_filter_for_planner(self):
        skills = [
            types.SimpleNamespace(name="a", skill_type="planning"),
            types.SimpleNamespace(name="b", skill_type="execution"),
            types.SimpleNamespace(name="c", skill_type="analysis"),
            types.SimpleNamespace(name="d", skill_type="testing"),
        ]
        filtered = self.router.filter_skills(skills, Role.planner)
        names = [s.name for s in filtered]
        assert names == ["a", "c"]

    def test_filter_for_executor(self):
        skills = [
            types.SimpleNamespace(name="a", skill_type="planning"),
            types.SimpleNamespace(name="b", skill_type="execution"),
            types.SimpleNamespace(name="c", skill_type=""),
            types.SimpleNamespace(name="d", skill_type="testing"),
        ]
        filtered = self.router.filter_skills(skills, Role.executor)
        names = [s.name for s in filtered]
        assert names == ["b", "c"]

    def test_filter_for_verifier(self):
        skills = [
            types.SimpleNamespace(name="a", skill_type="validation"),
            types.SimpleNamespace(name="b", skill_type="execution"),
            types.SimpleNamespace(name="c", skill_type="testing"),
        ]
        filtered = self.router.filter_skills(skills, Role.verifier)
        names = [s.name for s in filtered]
        assert names == ["a", "c"]

    def test_filter_empty_skills_list(self):
        assert self.router.filter_skills([], Role.planner) == []

    def test_filter_no_match(self):
        skills = [types.SimpleNamespace(name="x", skill_type="planning")]
        assert self.router.filter_skills(skills, Role.executor) == []


# --- RoleAssignment dataclass ---

class TestRoleAssignment:
    def test_default_reason(self):
        ra = RoleAssignment(task_id=1, role=Role.planner)
        assert ra.reason == ""

    def test_with_reason(self):
        ra = RoleAssignment(task_id=5, role=Role.verifier, reason="matched: test")
        assert ra.task_id == 5
        assert ra.role == Role.verifier
        assert ra.reason == "matched: test"


# --- RoleRouter allowed_roles ---

class TestAllowedRoles:
    def test_default_all_roles(self):
        router = RoleRouter()
        assert set(router.allowed_roles) == set(Role)

    def test_custom_allowed_roles(self):
        router = RoleRouter(allowed_roles=[Role.planner, Role.executor])
        assert router.allowed_roles == [Role.planner, Role.executor]


# --- IntakeTask.assigned_role field ---

class TestIntakeTaskAssignedRole:
    def test_default_assigned_role(self):
        from superpowers.intake import IntakeTask

        task = IntakeTask(id=1, requirement="do something", skill=None)
        assert task.assigned_role == "executor"

    def test_custom_assigned_role(self):
        from superpowers.intake import IntakeTask

        task = IntakeTask(id=1, requirement="plan something", skill=None, assigned_role="planner")
        assert task.assigned_role == "planner"

    def test_assigned_role_serialized(self):
        from dataclasses import asdict

        from superpowers.intake import IntakeTask

        task = IntakeTask(id=1, requirement="test something", skill=None, assigned_role="verifier")
        d = asdict(task)
        assert d["assigned_role"] == "verifier"


# --- run_intake with role parameter ---

class TestRunIntakeWithRole:
    def test_run_intake_assigns_roles(self, tmp_path, monkeypatch):
        from superpowers import intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

        payload = run_intake(
            "- plan the deployment\n- run the build\n- test the output",
            runtime_dir=tmp_path,
            execute=False,
        )

        tasks = payload["tasks"]
        assert tasks[0]["assigned_role"] == "planner"
        assert tasks[1]["assigned_role"] == "executor"
        assert tasks[2]["assigned_role"] == "verifier"

    def test_run_intake_role_filter_skips_non_matching(self, tmp_path, monkeypatch):
        from superpowers import intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

        payload = run_intake(
            "- plan the deployment\n- run the build\n- test the output",
            runtime_dir=tmp_path,
            execute=False,
            role="executor",
        )

        tasks = payload["tasks"]
        # Only the executor task should proceed; others should be skipped
        assert tasks[0]["status"] == "skipped"  # planner
        assert tasks[0]["assigned_role"] == "planner"
        assert tasks[1]["status"] == "planned"  # executor - proceeds
        assert tasks[1]["assigned_role"] == "executor"
        assert tasks[2]["status"] == "skipped"  # verifier
        assert tasks[2]["assigned_role"] == "verifier"

    def test_run_intake_role_all_runs_everything(self, tmp_path, monkeypatch):
        from superpowers import intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

        payload = run_intake(
            "- plan the deployment\n- run the build",
            runtime_dir=tmp_path,
            execute=False,
            role="all",
        )

        tasks = payload["tasks"]
        # No tasks should be skipped when role is "all"
        assert all(t["status"] != "skipped" for t in tasks)

    def test_run_intake_role_none_runs_everything(self, tmp_path, monkeypatch):
        from superpowers import intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

        payload = run_intake(
            "- plan the deployment\n- run the build",
            runtime_dir=tmp_path,
            execute=False,
            role=None,
        )

        tasks = payload["tasks"]
        assert all(t["status"] != "skipped" for t in tasks)

    def test_run_intake_payload_includes_role_assignments(self, tmp_path, monkeypatch):
        from superpowers import intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

        payload = run_intake(
            "- analyze the system\n- deploy now",
            runtime_dir=tmp_path,
            execute=False,
        )

        assert "role_assignments" in payload
        assert len(payload["role_assignments"]) == 2
        ra0 = payload["role_assignments"][0]
        assert ra0["task_id"] == 1
        assert ra0["role"] == "planner"
        assert "analyze" in ra0["reason"]

    def test_run_intake_payload_includes_role_field(self, tmp_path, monkeypatch):
        from superpowers import intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)
        monkeypatch.setattr(intake, "check_and_install", lambda *_args, **_kwargs: "heartbeat")

        payload = run_intake("do something", runtime_dir=tmp_path, execute=False, role="executor")
        assert payload["role"] == "executor"

    def test_run_intake_skipped_tasks_not_skill_resolved(self, tmp_path, monkeypatch):
        from superpowers import intake

        session_file = tmp_path / "current_request.json"
        monkeypatch.setattr(intake, "SESSION_FILE", session_file)

        install_calls = []
        def tracking_install(*args, **kwargs):
            install_calls.append(args)
            return "heartbeat"

        monkeypatch.setattr(intake, "check_and_install", tracking_install)

        payload = run_intake(
            "- plan the deployment\n- run the build",
            runtime_dir=tmp_path,
            execute=False,
            role="executor",
        )

        # Only the executor task should have had check_and_install called
        assert len(install_calls) == 1
        # The planner task should be skipped with no skill set
        assert payload["tasks"][0]["skill"] is None
        assert payload["tasks"][0]["status"] == "skipped"


# --- Skill.skill_type field ---

class TestSkillType:
    def test_skill_default_skill_type(self):
        from pathlib import Path

        from superpowers.skill_registry import Skill

        skill = Skill(
            name="test",
            description="test skill",
            version="1.0",
            author="me",
            script_path=Path("/tmp/test.sh"),
        )
        assert skill.skill_type == ""

    def test_skill_custom_skill_type(self):
        from pathlib import Path

        from superpowers.skill_registry import Skill

        skill = Skill(
            name="test",
            description="test skill",
            version="1.0",
            author="me",
            script_path=Path("/tmp/test.sh"),
            skill_type="planning",
        )
        assert skill.skill_type == "planning"

    def test_skill_type_parsed_from_yaml(self, tmp_path):
        import yaml

        from superpowers.skill_registry import _parse_skill_yaml

        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        script = skill_dir / "run.sh"
        script.write_text("#!/bin/bash\necho hello")

        manifest = skill_dir / "skill.yaml"
        manifest.write_text(yaml.dump({
            "name": "my-skill",
            "description": "A test skill",
            "version": "1.0",
            "author": "tester",
            "script": "run.sh",
            "skill_type": "validation",
        }))

        skill = _parse_skill_yaml(manifest)
        assert skill.skill_type == "validation"

    def test_skill_type_defaults_when_missing_in_yaml(self, tmp_path):
        import yaml

        from superpowers.skill_registry import _parse_skill_yaml

        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        script = skill_dir / "run.sh"
        script.write_text("#!/bin/bash\necho hello")

        manifest = skill_dir / "skill.yaml"
        manifest.write_text(yaml.dump({
            "name": "my-skill",
            "description": "A test skill",
            "version": "1.0",
            "author": "tester",
            "script": "run.sh",
        }))

        skill = _parse_skill_yaml(manifest)
        assert skill.skill_type == ""


# Need this import at module level for the run_intake tests
from superpowers.intake import run_intake  # noqa: E402
