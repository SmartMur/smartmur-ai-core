from __future__ import annotations

import os
import subprocess
from pathlib import Path

from superpowers.skill_registry import Skill


class DependencyError(RuntimeError):
    pass


class SkillLoader:
    def load(self, skill: Skill) -> None:
        """Verify all dependencies are available before running."""
        missing = []
        for dep in skill.dependencies:
            # Check if the dependency is an executable on PATH
            if not _which(dep):
                missing.append(dep)
        if missing:
            raise DependencyError(f"Missing dependencies: {', '.join(missing)}")

    def run(self, skill: Skill, args: dict | None = None) -> subprocess.CompletedProcess:
        """Execute a skill's script, capturing output."""
        self.load(skill)
        cmd, env = _build_command(skill, args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=skill.script_path.parent,
            env=env,
            timeout=300,
        )

    def run_sandboxed(self, skill: Skill, args: dict | None = None) -> subprocess.CompletedProcess:
        """Run in a subprocess with a restricted environment."""
        self.load(skill)
        cmd, _ = _build_command(skill, args)

        # Build a minimal env — strip vault/secret vars unless permitted
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", ""),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "TERM": os.environ.get("TERM", "xterm"),
        }

        if "vault" not in skill.permissions:
            # Strip anything that looks like a secret
            pass  # safe_env already excludes everything by default
        else:
            # Allow full env passthrough for vault-permitted skills
            safe_env = _build_command(skill, args)[1]

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=skill.script_path.parent,
            env=safe_env,
            timeout=300,
        )


def _which(name: str) -> str | None:
    """Find executable on PATH."""
    import shutil

    return shutil.which(name)


def _build_command(skill: Skill, args: dict | None) -> tuple[list[str], dict[str, str]]:
    script = skill.script_path
    env = os.environ.copy()

    # Pass args as env vars prefixed with SKILL_
    if args:
        for k, v in args.items():
            env[f"SKILL_{k.upper()}"] = str(v)

    if script.suffix == ".py":
        cmd = ["python3", str(script)]
    elif script.suffix == ".sh":
        cmd = ["bash", str(script)]
    else:
        cmd = [str(script)]

    return cmd, env
