from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from superpowers.skillhub import SkillHub

SKILL_MANIFEST = {
    "name": "test-skill",
    "version": "1.0.0",
    "description": "A test skill",
    "author": "tester",
    "script": "run.sh",
}


def _make_skill(parent: Path, name: str = "test-skill", **overrides) -> Path:
    """Create a minimal skill directory."""
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    manifest = {**SKILL_MANIFEST, "name": name, **overrides}
    (skill_dir / "skill.yaml").write_text(yaml.dump(manifest))
    script = skill_dir / "run.sh"
    script.write_text("#!/usr/bin/env bash\necho hello\n")
    script.chmod(0o755)
    return skill_dir


@pytest.fixture()
def hub_env(tmp_path):
    """Set up local skills dir and hub repo dir."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    hub_path = tmp_path / "skillhub"
    hub_path.mkdir()
    # Init a git repo in hub
    import subprocess
    subprocess.run(["git", "init"], cwd=hub_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=hub_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=hub_path, capture_output=True)
    return SkillHub(hub_path=hub_path, skills_dir=skills_dir)


class TestPush:
    def test_push_copies_skill_to_hub(self, hub_env: SkillHub):
        _make_skill(hub_env.skills_dir, "my-skill")
        result = hub_env.push("my-skill")
        assert result.action == "pushed"
        assert (hub_env.hub_path / "my-skill" / "skill.yaml").exists()
        assert (hub_env.hub_path / "my-skill" / "run.sh").exists()

    def test_push_missing_skill_returns_error(self, hub_env: SkillHub):
        result = hub_env.push("nonexistent")
        assert result.action == "error"
        assert "not found" in result.message

    def test_push_no_manifest_returns_error(self, hub_env: SkillHub):
        bad_dir = hub_env.skills_dir / "bad-skill"
        bad_dir.mkdir()
        (bad_dir / "run.sh").write_text("#!/bin/bash\n")
        result = hub_env.push("bad-skill")
        assert result.action == "error"
        assert "skill.yaml" in result.message

    def test_push_already_up_to_date(self, hub_env: SkillHub):
        _make_skill(hub_env.skills_dir, "my-skill")
        hub_env.push("my-skill")
        # Push again with no changes
        result = hub_env.push("my-skill")
        assert result.action == "up-to-date"

    def test_push_overwrites_existing(self, hub_env: SkillHub):
        _make_skill(hub_env.skills_dir, "my-skill", version="1.0.0")
        hub_env.push("my-skill")
        # Update the local version
        _make_skill(hub_env.skills_dir, "my-skill", version="2.0.0")
        result = hub_env.push("my-skill")
        assert result.action == "pushed"
        data = yaml.safe_load((hub_env.hub_path / "my-skill" / "skill.yaml").read_text())
        assert data["version"] == "2.0.0"


class TestPull:
    def test_pull_single_skill(self, hub_env: SkillHub):
        _make_skill(hub_env.hub_path, "remote-skill")
        results = hub_env.pull("remote-skill")
        assert len(results) == 1
        assert results[0].action == "pulled"
        assert (hub_env.skills_dir / "remote-skill" / "skill.yaml").exists()

    def test_pull_all_skills(self, hub_env: SkillHub):
        _make_skill(hub_env.hub_path, "skill-a")
        _make_skill(hub_env.hub_path, "skill-b")
        results = hub_env.pull()
        assert len(results) == 2
        names = {r.skill_name for r in results}
        assert names == {"skill-a", "skill-b"}

    def test_pull_missing_skill_returns_error(self, hub_env: SkillHub):
        results = hub_env.pull("nonexistent")
        assert len(results) == 1
        assert results[0].action == "error"

    def test_pull_missing_hub_returns_error(self, tmp_path):
        hub = SkillHub(hub_path=tmp_path / "nope", skills_dir=tmp_path / "skills")
        results = hub.pull("anything")
        assert results[0].action == "error"

    def test_pull_overwrites_local(self, hub_env: SkillHub):
        _make_skill(hub_env.skills_dir, "my-skill", version="1.0.0")
        _make_skill(hub_env.hub_path, "my-skill", version="2.0.0")
        hub_env.pull("my-skill")
        data = yaml.safe_load((hub_env.skills_dir / "my-skill" / "skill.yaml").read_text())
        assert data["version"] == "2.0.0"

    def test_pull_skips_dotdirs(self, hub_env: SkillHub):
        _make_skill(hub_env.hub_path, "real-skill")
        # .git dir should be ignored
        results = hub_env.pull()
        names = {r.skill_name for r in results}
        assert ".git" not in names


class TestListRemote:
    def test_list_empty_hub(self, hub_env: SkillHub):
        assert hub_env.list_remote() == []

    def test_list_skills(self, hub_env: SkillHub):
        _make_skill(hub_env.hub_path, "alpha", description="First")
        _make_skill(hub_env.hub_path, "beta", description="Second")
        skills = hub_env.list_remote()
        assert len(skills) == 2
        assert skills[0]["name"] == "alpha"
        assert skills[1]["name"] == "beta"

    def test_list_nonexistent_hub(self, tmp_path):
        hub = SkillHub(hub_path=tmp_path / "nope", skills_dir=tmp_path / "s")
        assert hub.list_remote() == []

    def test_list_ignores_dirs_without_manifest(self, hub_env: SkillHub):
        (hub_env.hub_path / "no-manifest").mkdir()
        _make_skill(hub_env.hub_path, "real")
        skills = hub_env.list_remote()
        assert len(skills) == 1


class TestDiff:
    def test_diff_identical(self, hub_env: SkillHub):
        _make_skill(hub_env.skills_dir, "my-skill", version="1.0.0")
        _make_skill(hub_env.hub_path, "my-skill", version="1.0.0")
        output = hub_env.diff("my-skill")
        assert "No differences" in output

    def test_diff_shows_changes(self, hub_env: SkillHub):
        _make_skill(hub_env.skills_dir, "my-skill", version="2.0.0")
        _make_skill(hub_env.hub_path, "my-skill", version="1.0.0")
        output = hub_env.diff("my-skill")
        assert "2.0.0" in output
        assert "1.0.0" in output

    def test_diff_local_missing(self, hub_env: SkillHub):
        _make_skill(hub_env.hub_path, "remote-only")
        output = hub_env.diff("remote-only")
        assert "not found" in output.lower()

    def test_diff_hub_missing(self, hub_env: SkillHub):
        _make_skill(hub_env.skills_dir, "local-only")
        output = hub_env.diff("local-only")
        assert "not found" in output.lower()
