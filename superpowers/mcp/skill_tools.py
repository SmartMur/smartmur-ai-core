from __future__ import annotations

import subprocess

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def run_skill(name: str, args: str = "") -> str:
        """Run an installed skill by name and return its output.

        Args:
            name: Skill name as defined in skill.yaml.
            args: Arguments as comma-separated key=value pairs (e.g. "host=192.168.1.1,port=22"). Optional.
        """
        try:
            from superpowers.skill_loader import SkillLoader
            from superpowers.skill_registry import SkillRegistry

            registry = SkillRegistry()
            loader = SkillLoader()
            skill = registry.get(name)

            parsed_args = None
            if args:
                parsed_args = {}
                for pair in args.split(","):
                    pair = pair.strip()
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        parsed_args[k.strip()] = v.strip()

            result = loader.run(skill, parsed_args)
            output = result.stdout + result.stderr
            status = "OK" if result.returncode == 0 else f"FAILED (exit {result.returncode})"
            return f"Skill '{name}' — {status}\n{output.strip()}"
        except KeyError:
            return f"Skill not found: {name}"
        except (ImportError, RuntimeError, OSError, subprocess.SubprocessError, ValueError) as exc:
            return f"Error running skill '{name}': {exc}"

    @mcp.tool()
    def list_skills() -> str:
        """List all installed skills with their descriptions."""
        try:
            from superpowers.skill_registry import SkillRegistry

            registry = SkillRegistry()
            skills = registry.list_skills()
            if not skills:
                return "No skills installed."

            lines = [f"{len(skills)} skill(s):"]
            for s in skills:
                lines.append(f"  {s.name} (v{s.version}) — {s.description}")
            return "\n".join(lines)
        except (ImportError, OSError, RuntimeError) as exc:
            return f"Error listing skills: {exc}"

    @mcp.tool()
    def skill_info(name: str) -> str:
        """Show detailed information about a skill.

        Args:
            name: Skill name as defined in skill.yaml.
        """
        try:
            from superpowers.skill_registry import SkillRegistry

            registry = SkillRegistry()
            skill = registry.get(name)

            lines = [
                f"Skill: {skill.name}",
                f"Version: {skill.version}",
                f"Author: {skill.author}",
                f"Description: {skill.description}",
                f"Script: {skill.script_path}",
            ]
            if skill.triggers:
                lines.append(f"Triggers: {', '.join(skill.triggers)}")
            if skill.dependencies:
                lines.append(f"Dependencies: {', '.join(skill.dependencies)}")
            if skill.permissions:
                lines.append(f"Permissions: {', '.join(skill.permissions)}")
            lines.append(f"Slash command: {'yes' if skill.slash_command else 'no'}")
            return "\n".join(lines)
        except KeyError:
            return f"Skill not found: {name}"
        except (ImportError, OSError, RuntimeError) as exc:
            return f"Error getting skill info: {exc}"
