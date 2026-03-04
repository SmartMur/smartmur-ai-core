"""SkillHub — sync skills between local and a shared git repo."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from superpowers.config import get_data_dir

DEFAULT_HUB_PATH = Path.home() / "Projects" / "claude-superpowers" / "skillhub"
DEFAULT_SKILLS_DIR = get_data_dir() / "skills"


@dataclass
class SyncResult:
    skill_name: str
    action: str  # "pushed", "pulled", "up-to-date", "error"
    message: str = ""


def _git(hub_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=hub_path,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _ensure_hub_repo(hub_path: Path) -> None:
    if not hub_path.exists():
        hub_path.mkdir(parents=True, exist_ok=True)
        _git(hub_path, "init")
    elif not (hub_path / ".git").exists():
        _git(hub_path, "init")


def _read_skill_name(skill_dir: Path) -> str | None:
    manifest = skill_dir / "skill.yaml"
    if not manifest.exists():
        return None
    try:
        data = yaml.safe_load(manifest.read_text())
        return data.get("name")
    except (yaml.YAMLError, OSError, ValueError):
        return None


class SkillHub:
    def __init__(
        self,
        hub_path: Path | str | None = None,
        skills_dir: Path | str | None = None,
    ):
        self.hub_path = Path(hub_path) if hub_path else DEFAULT_HUB_PATH
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR

    def push(self, skill_name: str) -> SyncResult:
        """Copy a local skill to the hub repo and commit."""
        local_dir = self.skills_dir / skill_name
        if not local_dir.exists():
            return SyncResult(skill_name, "error", f"Local skill not found: {local_dir}")

        manifest = local_dir / "skill.yaml"
        if not manifest.exists():
            return SyncResult(skill_name, "error", "No skill.yaml in skill directory")

        _ensure_hub_repo(self.hub_path)

        dest = self.hub_path / skill_name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(local_dir, dest)

        _git(self.hub_path, "add", skill_name)

        # Check if there are staged changes
        status = _git(self.hub_path, "diff", "--cached", "--quiet")
        if status.returncode == 0:
            return SyncResult(skill_name, "up-to-date", "No changes to push")

        _git(self.hub_path, "commit", "-m", f"Update skill: {skill_name}")

        # Push if remote exists
        remote_check = _git(self.hub_path, "remote")
        if remote_check.stdout.strip():
            result = _git(self.hub_path, "push")
            if result.returncode != 0:
                return SyncResult(skill_name, "error", f"Git push failed: {result.stderr}")

        return SyncResult(skill_name, "pushed")

    def pull(self, skill_name: str | None = None) -> list[SyncResult]:
        """Pull skill(s) from the hub repo to local skills dir."""
        if not self.hub_path.exists():
            return [SyncResult(skill_name or "*", "error", f"Hub repo not found: {self.hub_path}")]

        # Pull from remote if available
        remote_check = _git(self.hub_path, "remote")
        if remote_check.stdout.strip():
            _git(self.hub_path, "pull")

        self.skills_dir.mkdir(parents=True, exist_ok=True)
        results = []

        if skill_name:
            names = [skill_name]
        else:
            names = [
                d.name
                for d in sorted(self.hub_path.iterdir())
                if d.is_dir() and not d.name.startswith(".") and (d / "skill.yaml").exists()
            ]

        for name in names:
            src = self.hub_path / name
            if not src.exists() or not (src / "skill.yaml").exists():
                results.append(SyncResult(name, "error", f"Skill not found in hub: {name}"))
                continue

            dest = self.skills_dir / name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            results.append(SyncResult(name, "pulled"))

        return results

    def list_remote(self) -> list[dict[str, str]]:
        """List skills available in the hub repo."""
        if not self.hub_path.exists():
            return []

        skills = []
        for d in sorted(self.hub_path.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            manifest = d / "skill.yaml"
            if not manifest.exists():
                continue
            try:
                data = yaml.safe_load(manifest.read_text())
                skills.append(
                    {
                        "name": data.get("name", d.name),
                        "version": data.get("version", "?"),
                        "description": data.get("description", ""),
                    }
                )
            except (yaml.YAMLError, OSError, ValueError):
                continue
        return skills

    def diff(self, skill_name: str) -> str:
        """Show diff between local and hub version of a skill."""
        local_dir = self.skills_dir / skill_name
        hub_dir = self.hub_path / skill_name

        if not local_dir.exists():
            return f"Local skill not found: {local_dir}"
        if not hub_dir.exists():
            return f"Hub skill not found: {hub_dir}"

        result = subprocess.run(
            ["diff", "-ru", str(hub_dir), str(local_dir)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return "No differences."
        return result.stdout
