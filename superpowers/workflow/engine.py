"""Workflow execution engine — runs steps sequentially with conditions and rollback."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.request

from superpowers.workflow.base import (
    StepConfig,
    StepResult,
    StepStatus,
    StepType,
    WorkflowConfig,
)


class WorkflowEngine:
    def __init__(self):
        pass

    def run(self, config: WorkflowConfig, dry_run: bool = False) -> list[StepResult]:
        results: list[StepResult] = []
        failed = False

        for step in config.steps:
            if failed and step.on_failure != "continue":
                results.append(
                    StepResult(
                        step_name=step.name,
                        status=StepStatus.skipped,
                    )
                )
                continue

            if step.condition and not self._check_condition(step.condition, results):
                results.append(
                    StepResult(
                        step_name=step.name,
                        status=StepStatus.skipped,
                        output="condition not met",
                    )
                )
                continue

            if dry_run and step.type == StepType.approval_gate:
                results.append(
                    StepResult(
                        step_name=step.name,
                        status=StepStatus.passed,
                        output="dry-run: gate auto-approved",
                    )
                )
                continue

            result = self._execute_step(step, dry_run)
            results.append(result)

            if result.status == StepStatus.failed:
                failed = True
                if step.on_failure == "rollback" and config.rollback_steps:
                    self._run_rollback(config.rollback_steps, results)
                    break
                elif step.on_failure == "abort":
                    break

        if config.notify_profile and not dry_run:
            self._notify(config, results)

        return results

    def _execute_step(self, step: StepConfig, dry_run: bool = False) -> StepResult:
        if dry_run:
            return StepResult(
                step_name=step.name,
                status=StepStatus.passed,
                output=f"dry-run: would execute {step.type.value}: {step.command}",
            )

        start = time.monotonic()
        try:
            if step.type == StepType.shell:
                output, ok = self._run_shell(step)
            elif step.type == StepType.claude_prompt:
                output, ok = self._run_claude(step)
            elif step.type == StepType.skill:
                output, ok = self._run_skill(step)
            elif step.type == StepType.http:
                output, ok = self._run_http(step)
            elif step.type == StepType.approval_gate:
                output, ok = self._run_approval(step)
            elif step.type == StepType.auto_agent:
                output, ok = self._run_auto_agent(step)
            else:
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.failed,
                    error=f"Unknown step type: {step.type}",
                )
        except (subprocess.SubprocessError, OSError, RuntimeError, ValueError, KeyError,
                urllib.error.URLError) as exc:
            return StepResult(
                step_name=step.name,
                status=StepStatus.failed,
                error=str(exc),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        elapsed = int((time.monotonic() - start) * 1000)
        return StepResult(
            step_name=step.name,
            status=StepStatus.passed if ok else StepStatus.failed,
            output=output,
            duration_ms=elapsed,
        )

    def _run_shell(self, step: StepConfig) -> tuple[str, bool]:
        env = {**os.environ, **{f"WF_{k.upper()}": str(v) for k, v in step.args.items()}}
        result = subprocess.run(
            shlex.split(step.command),
            capture_output=True,
            text=True,
            timeout=step.timeout,
            env=env,
        )
        return result.stdout + result.stderr, result.returncode == 0

    def _run_claude(self, step: StepConfig) -> tuple[str, bool]:
        from superpowers.llm_provider import get_default_provider

        provider = get_default_provider(role="job")
        try:
            output = provider.invoke(step.command)
            return output, True
        except (RuntimeError, FileNotFoundError) as exc:
            return str(exc), False

    def _run_skill(self, step: StepConfig) -> tuple[str, bool]:
        from superpowers.skill_loader import SkillLoader
        from superpowers.skill_registry import SkillRegistry

        registry = SkillRegistry()
        loader = SkillLoader()
        skill = registry.get(step.command)
        result = loader.run(skill, step.args or None)
        return result.stdout + result.stderr, result.returncode == 0

    def _run_http(self, step: StepConfig) -> tuple[str, bool]:
        method = step.args.get("method", "POST").upper()
        headers = step.args.get("headers", {"Content-Type": "application/json"})
        body = step.args.get("body")
        data = json.dumps(body).encode() if body else None

        req = urllib.request.Request(
            step.command,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=step.timeout) as resp:
                return resp.read().decode(), True
        except urllib.error.URLError as exc:
            return str(exc), False

    def _run_approval(self, step: StepConfig) -> tuple[str, bool]:
        prompt = step.args.get("prompt", f"Approve step '{step.name}'? [y/N] ")
        try:
            answer = input(prompt).strip().lower()
            if answer in ("y", "yes"):
                return "approved", True
            return "rejected", False
        except EOFError:
            return "no tty — rejected", False

    def _run_auto_agent(self, step: StepConfig) -> tuple[str, bool]:
        """Auto-select the best agent for the task and run its skills.

        The ``command`` field is used as the task description for agent
        selection.  Optional ``args`` may include ``repo_path`` for
        tech-stack detection.
        """
        from superpowers.agent_router import select_agents

        task = step.command
        repo_path = step.args.get("repo_path")

        selections = select_agents(
            task_description=task,
            repo_path=repo_path,
        )

        if not selections:
            return f"No agents matched task: {task}", False

        top = selections[0]
        agent = top.agent
        reasons = "; ".join(top.reasons)
        lines = [f"Selected agent: {agent.name} (score: {top.score}, reasons: {reasons})"]

        # If agent has skills, run the first one
        if agent.skills:
            skill_name = agent.skills[0]
            try:
                from superpowers.skill_loader import SkillLoader
                from superpowers.skill_registry import SkillRegistry

                sr = SkillRegistry()
                loader = SkillLoader()
                skill = sr.get(skill_name)
                result = loader.run(skill, step.args or None)
                lines.append(f"Ran skill: {skill_name}")
                lines.append(result.stdout + result.stderr)
                return "\n".join(lines), result.returncode == 0
            except (KeyError, OSError, RuntimeError) as exc:
                lines.append(f"Skill {skill_name} failed: {exc}")
                return "\n".join(lines), False
        else:
            lines.append(f"Agent {agent.name} has no skills; task logged only.")
            return "\n".join(lines), True

    def _check_condition(self, condition: str, results: list[StepResult]) -> bool:
        if not results:
            return condition == "always"
        last = results[-1]
        if condition == "previous.ok":
            return last.status == StepStatus.passed
        if condition == "previous.failed":
            return last.status == StepStatus.failed
        if condition == "always":
            return True
        return True

    def _run_rollback(self, rollback_steps: list[StepConfig], results: list[StepResult]) -> None:
        for step in rollback_steps:
            result = self._execute_step(step)
            results.append(
                StepResult(
                    step_name=f"rollback:{result.step_name}",
                    status=result.status,
                    output=result.output,
                    error=result.error,
                    duration_ms=result.duration_ms,
                )
            )

    def _notify(self, config: WorkflowConfig, results: list[StepResult]) -> None:
        try:
            from superpowers.channels.registry import ChannelRegistry
            from superpowers.config import Settings
            from superpowers.profiles import ProfileManager

            passed = sum(1 for r in results if r.status == StepStatus.passed)
            failed = sum(1 for r in results if r.status == StepStatus.failed)
            summary = f"Workflow '{config.name}': {passed} passed, {failed} failed"

            settings = Settings.load()
            registry = ChannelRegistry(settings)
            pm = ProfileManager(registry)
            pm.send(config.notify_profile, summary)
        except (ImportError, KeyError, OSError, ValueError):
            pass
