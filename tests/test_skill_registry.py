from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from superpowers.skill_registry import SkillRegistry

FIXTURES = Path(__file__).parent / "fixtures" / "skills"


@pytest.fixture()
def tmp_skills(tmp_path):
    """Create a temporary skills directory with a valid skill."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text(
        yaml.dump(
            {
                "name": "test-skill",
                "version": "0.1.0",
                "description": "A test skill",
                "author": "tester",
                "script": "run.sh",
                "slash_command": True,
                "triggers": [],
                "dependencies": [],
                "permissions": [],
            }
        )
    )
    script = skill_dir / "run.sh"
    script.write_text("#!/usr/bin/env bash\necho hello\n")
    script.chmod(0o755)
    return tmp_path


@pytest.fixture()
def registry(tmp_skills):
    return SkillRegistry(skills_dir=tmp_skills)


class TestDiscover:
    def test_discovers_skills(self, registry, tmp_skills):
        skills = registry.discover()
        assert len(skills) == 1
        assert skills[0].name == "test-skill"

    def test_skips_underscore_prefixed_dirs(self):
        """Directories prefixed with _ (e.g. _template) are excluded from discovery."""
        reg = SkillRegistry()
        skills = reg.discover()
        names = [s.name for s in skills]
        assert "template-skill" not in names
        # But real skills should still be found
        assert len(skills) >= 1

    def test_discovers_template_in_real_dir(self, tmp_path):
        """A skill named 'template-skill' is found when its directory is not underscore-prefixed."""
        skill_dir = tmp_path / "template-skill"
        skill_dir.mkdir()
        (skill_dir / "skill.yaml").write_text(
            yaml.dump(
                {
                    "name": "template-skill",
                    "version": "0.1.0",
                    "description": "A template skill - copy this to create new skills",
                    "author": "DreDay",
                    "script": "run.sh",
                    "slash_command": True,
                    "triggers": [],
                    "dependencies": [],
                    "permissions": [],
                }
            )
        )
        script = skill_dir / "run.sh"
        script.write_text("#!/usr/bin/env bash\necho hello\n")
        script.chmod(0o755)
        reg = SkillRegistry(skills_dir=tmp_path)
        skills = reg.discover()
        names = [s.name for s in skills]
        assert "template-skill" in names

    def test_ignores_nested_dirs(self, tmp_skills):
        nested = tmp_skills / "test-skill" / "sub" / "nested"
        nested.mkdir(parents=True)
        (nested / "skill.yaml").write_text(
            yaml.dump(
                {
                    "name": "nested",
                    "version": "1.0",
                    "description": "x",
                    "author": "x",
                    "script": "run.sh",
                }
            )
        )
        reg = SkillRegistry(skills_dir=tmp_skills)
        skills = reg.discover()
        assert all(s.name != "nested" for s in skills)


class TestValidate:
    def test_valid_skill(self, registry, tmp_skills):
        errors = registry.validate(tmp_skills / "test-skill")
        assert errors == []

    def test_missing_yaml(self, tmp_path):
        empty = tmp_path / "empty-skill"
        empty.mkdir()
        reg = SkillRegistry(skills_dir=tmp_path)
        errors = reg.validate(empty)
        assert any("Missing skill.yaml" in e for e in errors)

    def test_missing_required_fields(self, tmp_path):
        bad = tmp_path / "bad-skill"
        bad.mkdir()
        (bad / "skill.yaml").write_text(yaml.dump({"name": "bad"}))
        reg = SkillRegistry(skills_dir=tmp_path)
        errors = reg.validate(bad)
        assert any("version" in e for e in errors)
        assert any("description" in e for e in errors)
        assert any("author" in e for e in errors)
        assert any("script" in e for e in errors)

    def test_missing_script_file(self, tmp_path):
        s = tmp_path / "no-script"
        s.mkdir()
        (s / "skill.yaml").write_text(
            yaml.dump(
                {
                    "name": "no-script",
                    "version": "1",
                    "description": "x",
                    "author": "x",
                    "script": "gone.sh",
                }
            )
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        errors = reg.validate(s)
        assert any("Script not found" in e for e in errors)


class TestSyncSlashCommands:
    def test_creates_symlinks(self, registry, tmp_path, monkeypatch):
        global_cmds = tmp_path / "global_commands"
        global_cmds.mkdir()
        monkeypatch.setattr("superpowers.skill_registry.GLOBAL_COMMANDS_DIR", global_cmds)

        registry.discover()
        created = registry.sync_slash_commands()

        assert len(created) == 1
        symlink = global_cmds / "test-skill.md"
        assert symlink.is_symlink()
        assert "test-skill" in symlink.read_text()

    def test_skips_non_slash_command(self, tmp_path, monkeypatch):
        skill_dir = tmp_path / "no-slash"
        skill_dir.mkdir()
        (skill_dir / "skill.yaml").write_text(
            yaml.dump(
                {
                    "name": "no-slash",
                    "version": "1",
                    "description": "x",
                    "author": "x",
                    "script": "run.sh",
                    "slash_command": False,
                }
            )
        )
        (skill_dir / "run.sh").write_text("#!/bin/bash\necho hi\n")

        global_cmds = tmp_path / "global_commands"
        global_cmds.mkdir()
        monkeypatch.setattr("superpowers.skill_registry.GLOBAL_COMMANDS_DIR", global_cmds)

        reg = SkillRegistry(skills_dir=tmp_path)
        reg.discover()
        created = reg.sync_slash_commands()
        assert len(created) == 0


class TestGetAndList:
    def test_get_existing(self, registry):
        registry.discover()
        s = registry.get("test-skill")
        assert s.name == "test-skill"

    def test_get_missing(self, registry):
        registry.discover()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_list_skills(self, registry):
        registry.discover()
        skills = registry.list_skills()
        assert len(skills) == 1
