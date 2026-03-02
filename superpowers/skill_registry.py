from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Skill:
    name: str
    description: str
    version: str
    author: str
    script_path: Path
    triggers: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    slash_command: bool = False
    permissions: list[str] = field(default_factory=list)
    skill_type: str = ""


REQUIRED_FIELDS = {"name", "version", "description", "author", "script"}

SKILLS_DIR_DEFAULT = Path.home() / "Projects" / "claude-superpowers" / "skills"
GLOBAL_COMMANDS_DIR = Path.home() / ".claude" / "commands"


def _parse_skill_yaml(skill_yaml: Path) -> Skill:
    data = yaml.safe_load(skill_yaml.read_text())
    skill_dir = skill_yaml.parent
    return Skill(
        name=data["name"],
        description=data.get("description", ""),
        version=data.get("version", "0.0.0"),
        author=data.get("author", "unknown"),
        script_path=skill_dir / data["script"],
        triggers=data.get("triggers", []),
        dependencies=data.get("dependencies", []),
        slash_command=data.get("slash_command", False),
        permissions=data.get("permissions", []),
        skill_type=data.get("skill_type", ""),
    )


class SkillRegistry:
    def __init__(self, skills_dir: Path | str | None = None):
        self.skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR_DEFAULT
        self._cache: dict[str, Skill] = {}

    def discover(self) -> list[Skill]:
        self._cache.clear()
        skills = []
        if not self.skills_dir.exists():
            return skills
        for skill_yaml in sorted(self.skills_dir.rglob("skill.yaml")):
            # Only pick up top-level skill dirs (depth 1 under skills_dir)
            if skill_yaml.parent.parent != self.skills_dir:
                continue
            try:
                skill = _parse_skill_yaml(skill_yaml)
                self._cache[skill.name] = skill
                skills.append(skill)
            except Exception:
                continue
        return skills

    def get(self, name: str) -> Skill:
        if not self._cache:
            self.discover()
        if name not in self._cache:
            raise KeyError(f"Skill not found: {name}")
        return self._cache[name]

    def install(self, skill_dir: Path) -> Skill:
        skill_dir = Path(skill_dir)
        errors = self.validate(skill_dir)
        if errors:
            raise ValueError(f"Invalid skill: {'; '.join(errors)}")
        skill = _parse_skill_yaml(skill_dir / "skill.yaml")
        dest = self.skills_dir / skill.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill_dir, dest)
        # Re-parse from installed location
        skill = _parse_skill_yaml(dest / "skill.yaml")
        self._cache[skill.name] = skill
        return skill

    def uninstall(self, name: str) -> None:
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            raise FileNotFoundError(f"Skill directory not found: {skill_dir}")
        shutil.rmtree(skill_dir)
        self._cache.pop(name, None)

    def list_skills(self) -> list[Skill]:
        if not self._cache:
            self.discover()
        return list(self._cache.values())

    def sync_slash_commands(self) -> list[Path]:
        """Generate command .md files and symlinks for slash_command skills."""
        if not self._cache:
            self.discover()

        GLOBAL_COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []

        for skill in self._cache.values():
            if not skill.slash_command:
                continue

            skill_dir = skill.script_path.parent
            commands_dir = skill_dir / ".claude" / "commands"
            commands_dir.mkdir(parents=True, exist_ok=True)

            # Generate the command .md file
            md_path = commands_dir / f"{skill.name}.md"
            md_content = (
                f"# {skill.name}\n\n"
                f"{skill.description}\n\n"
                f"Execute this skill by running:\n"
                f"`{skill.script_path}`\n"
            )
            md_path.write_text(md_content)

            # Symlink into global commands dir
            symlink = GLOBAL_COMMANDS_DIR / f"{skill.name}.md"
            if symlink.exists() or symlink.is_symlink():
                symlink.unlink()
            symlink.symlink_to(md_path)
            created.append(symlink)

        return created

    def validate(self, skill_dir: Path) -> list[str]:
        skill_dir = Path(skill_dir)
        errors: list[str] = []

        manifest = skill_dir / "skill.yaml"
        if not manifest.exists():
            errors.append("Missing skill.yaml")
            return errors

        try:
            data = yaml.safe_load(manifest.read_text())
        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML: {e}")
            return errors

        if not isinstance(data, dict):
            errors.append("skill.yaml must be a YAML mapping")
            return errors

        for f in REQUIRED_FIELDS:
            if f not in data:
                errors.append(f"Missing required field: {f}")

        if "script" in data:
            script = skill_dir / data["script"]
            if not script.exists():
                errors.append(f"Script not found: {data['script']}")

        return errors
