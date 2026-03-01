from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def run_workflow(name: str, dry_run: bool = False) -> str:
        """Load and execute a workflow by name, returning step-by-step results.

        Args:
            name: Workflow name (matches filename without .yaml extension).
            dry_run: If true, simulate execution without running commands.
        """
        try:
            from superpowers.workflow.engine import WorkflowEngine
            from superpowers.workflow.loader import WorkflowLoader

            loader = WorkflowLoader()
            config = loader.load(name)
            engine = WorkflowEngine()
            results = engine.run(config, dry_run=dry_run)

            lines = [f"Workflow '{name}' {'(dry run) ' if dry_run else ''}— {len(results)} step(s):"]
            for r in results:
                status = r.status.value.upper()
                duration = f" ({r.duration_ms}ms)" if r.duration_ms else ""
                lines.append(f"  [{status}] {r.step_name}{duration}")
                if r.output:
                    for out_line in r.output.strip().splitlines()[:10]:
                        lines.append(f"    {out_line}")
                if r.error:
                    lines.append(f"    ERROR: {r.error}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Error running workflow '{name}': {exc}"

    @mcp.tool()
    def list_workflows() -> str:
        """List available workflow YAML files."""
        try:
            from superpowers.workflow.loader import WorkflowLoader

            loader = WorkflowLoader()
            names = loader.list_workflows()
            if not names:
                return "No workflows found in ~/.claude-superpowers/workflows/"
            return "Available workflows:\n" + "\n".join(f"  - {n}" for n in names)
        except Exception as exc:
            return f"Error listing workflows: {exc}"

    @mcp.tool()
    def show_workflow(name: str) -> str:
        """Show detailed steps of a workflow.

        Args:
            name: Workflow name (matches filename without .yaml extension).
        """
        try:
            from superpowers.workflow.loader import WorkflowLoader

            loader = WorkflowLoader()
            config = loader.load(name)

            lines = [f"Workflow: {config.name}"]
            if config.description:
                lines.append(f"Description: {config.description}")
            if config.notify_profile:
                lines.append(f"Notify profile: {config.notify_profile}")
            lines.append(f"\nSteps ({len(config.steps)}):")
            for i, step in enumerate(config.steps, 1):
                lines.append(f"  {i}. {step.name}")
                lines.append(f"     type: {step.type.value}")
                lines.append(f"     command: {step.command}")
                if step.condition:
                    lines.append(f"     condition: {step.condition}")
                lines.append(f"     on_failure: {step.on_failure}")
                lines.append(f"     timeout: {step.timeout}s")
                if step.args:
                    lines.append(f"     args: {step.args}")

            if config.rollback_steps:
                lines.append(f"\nRollback steps ({len(config.rollback_steps)}):")
                for i, step in enumerate(config.rollback_steps, 1):
                    lines.append(f"  {i}. {step.name} ({step.type.value}): {step.command}")

            return "\n".join(lines)
        except Exception as exc:
            return f"Error showing workflow '{name}': {exc}"

    @mcp.tool()
    def validate_workflow(name: str) -> str:
        """Validate a workflow definition for errors.

        Args:
            name: Workflow name (matches filename without .yaml extension).
        """
        try:
            from superpowers.workflow.loader import WorkflowLoader

            loader = WorkflowLoader()
            config = loader.load(name)
            errors = loader.validate(config)
            if not errors:
                return f"Workflow '{name}' is valid ({len(config.steps)} steps)."
            return f"Workflow '{name}' has {len(errors)} error(s):\n" + "\n".join(f"  - {e}" for e in errors)
        except Exception as exc:
            return f"Error validating workflow '{name}': {exc}"
