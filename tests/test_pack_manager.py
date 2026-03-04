"""Tests for superpowers.pack_manager and superpowers.cli_pack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from superpowers.cli_pack import pack_group
from superpowers.pack_manager import (
    PackError,
    PackManager,
    PackManifest,
    _compute_pack_checksum,
    _sha256_dir,
    _sha256_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_SKILL_YAML = {
    "name": "test-skill",
    "version": "1.0.0",
    "description": "A test skill",
    "author": "tester",
    "script": "run.sh",
}


def _make_pack(
    parent: Path,
    name: str = "demo",
    version: str = "1.0.0",
    skills: list[str] | None = None,
    workflows: list[str] | None = None,
    agents: list[str] | None = None,
    *,
    checksum: str = "",
    create_contents: bool = True,
) -> Path:
    """Create a minimal pack directory with pack.yaml and optional contents."""
    pack_dir = parent / name
    pack_dir.mkdir(parents=True, exist_ok=True)

    skills = skills or []
    workflows = workflows or []
    agents = agents or []

    manifest = {
        "name": name,
        "version": version,
        "description": f"Test pack {name}",
        "author": "tester",
        "skills": skills,
        "workflows": workflows,
        "agents": agents,
        "checksum": checksum,
    }
    (pack_dir / "pack.yaml").write_text(yaml.dump(manifest))

    if create_contents:
        # Create skill directories
        if skills:
            skills_dir = pack_dir / "skills"
            skills_dir.mkdir(exist_ok=True)
            for skill in skills:
                skill_dir = skills_dir / skill
                skill_dir.mkdir(exist_ok=True)
                skill_manifest = {**MINIMAL_SKILL_YAML, "name": skill}
                (skill_dir / "skill.yaml").write_text(yaml.dump(skill_manifest))
                script = skill_dir / "run.sh"
                script.write_text("#!/usr/bin/env bash\necho hello\n")
                script.chmod(0o755)

        # Create workflow files
        if workflows:
            wf_dir = pack_dir / "workflows"
            wf_dir.mkdir(exist_ok=True)
            for wf in workflows:
                (wf_dir / f"{wf}.yaml").write_text(
                    yaml.dump(
                        {
                            "name": wf,
                            "steps": [{"name": "test", "type": "shell", "command": "echo ok"}],
                        }
                    )
                )

        # Create agent directories
        if agents:
            agents_dir = pack_dir / "agents"
            agents_dir.mkdir(exist_ok=True)
            for agent in agents:
                agent_dir = agents_dir / agent
                agent_dir.mkdir(exist_ok=True)
                (agent_dir / "agent.yaml").write_text(yaml.dump({"name": agent}))

    return pack_dir


def _make_pack_with_checksum(parent: Path, **kwargs) -> Path:
    """Create a pack and write the correct checksum into pack.yaml."""
    pack_dir = _make_pack(parent, **kwargs)
    checksum = _compute_pack_checksum(pack_dir)
    manifest_path = pack_dir / "pack.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["checksum"] = checksum
    manifest_path.write_text(yaml.dump(data))
    return pack_dir


@pytest.fixture()
def env(tmp_path):
    """Create isolated skills/workflows/agents/data dirs."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return PackManager(
        skills_dir=skills_dir,
        workflows_dir=workflows_dir,
        agents_dir=agents_dir,
        data_dir=data_dir,
    )


# ---------------------------------------------------------------------------
# PackManifest tests
# ---------------------------------------------------------------------------


class TestPackManifest:
    def test_from_yaml_valid(self, tmp_path):
        pack_dir = _make_pack(tmp_path, "my-pack", skills=["s1"], workflows=["w1"])
        manifest = PackManifest.from_yaml(pack_dir / "pack.yaml")
        assert manifest.name == "my-pack"
        assert manifest.version == "1.0.0"
        assert manifest.skills == ["s1"]
        assert manifest.workflows == ["w1"]

    def test_from_yaml_missing_file(self, tmp_path):
        with pytest.raises(PackError, match="not found"):
            PackManifest.from_yaml(tmp_path / "nonexistent.yaml")

    def test_from_yaml_invalid_yaml(self, tmp_path):
        bad = tmp_path / "pack.yaml"
        bad.write_text(": : : invalid yaml [[[")
        with pytest.raises(PackError, match="Invalid YAML"):
            PackManifest.from_yaml(bad)

    def test_from_yaml_not_a_mapping(self, tmp_path):
        bad = tmp_path / "pack.yaml"
        bad.write_text("- list\n- item\n")
        with pytest.raises(PackError, match="must be a mapping"):
            PackManifest.from_yaml(bad)

    def test_from_yaml_missing_name(self, tmp_path):
        bad = tmp_path / "pack.yaml"
        bad.write_text("version: '1.0'\n")
        with pytest.raises(PackError, match="'name' field"):
            PackManifest.from_yaml(bad)

    def test_to_dict(self):
        m = PackManifest(name="test", version="2.0", skills=["a", "b"])
        d = m.to_dict()
        assert d["name"] == "test"
        assert d["skills"] == ["a", "b"]

    def test_defaults(self):
        m = PackManifest(name="minimal")
        assert m.version == "0.0.0"
        assert m.skills == []
        assert m.workflows == []
        assert m.agents == []
        assert m.checksum == ""


# ---------------------------------------------------------------------------
# Checksum tests
# ---------------------------------------------------------------------------


class TestChecksums:
    def test_sha256_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world\n")
        h = _sha256_file(f)
        assert len(h) == 64
        # Same content = same hash
        f2 = tmp_path / "hello2.txt"
        f2.write_text("hello world\n")
        assert _sha256_file(f2) == h

    def test_sha256_dir_deterministic(self, tmp_path):
        d = tmp_path / "mydir"
        d.mkdir()
        (d / "a.txt").write_text("aaa")
        (d / "b.txt").write_text("bbb")
        h1 = _sha256_dir(d)
        h2 = _sha256_dir(d)
        assert h1 == h2

    def test_sha256_dir_changes_on_content_change(self, tmp_path):
        d = tmp_path / "mydir"
        d.mkdir()
        (d / "a.txt").write_text("aaa")
        h1 = _sha256_dir(d)
        (d / "a.txt").write_text("bbb")
        h2 = _sha256_dir(d)
        assert h1 != h2

    def test_compute_pack_checksum(self, tmp_path):
        pack_dir = _make_pack(tmp_path, "ck-pack", skills=["s1"])
        c1 = _compute_pack_checksum(pack_dir)
        assert len(c1) == 64
        # Modifying a file changes the checksum
        skill_script = pack_dir / "skills" / "s1" / "run.sh"
        skill_script.write_text("#!/bin/bash\necho changed\n")
        c2 = _compute_pack_checksum(pack_dir)
        assert c1 != c2


# ---------------------------------------------------------------------------
# PackManager.install tests
# ---------------------------------------------------------------------------


class TestInstall:
    def test_install_basic(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["my-skill"], workflows=["my-wf"])
        manifest = env.install(pack_dir)
        assert manifest.name == "demo"
        assert (env.skills_dir / "my-skill" / "skill.yaml").exists()
        assert (env.workflows_dir / "my-wf.yaml").exists()

    def test_install_records_in_registry(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"])
        env.install(pack_dir)
        installed = env.list_installed()
        assert len(installed) == 1
        assert installed[0]["name"] == "demo"

    def test_install_with_agents(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", agents=["my-agent"])
        env.install(pack_dir)
        assert (env.agents_dir / "my-agent" / "agent.yaml").exists()

    def test_install_with_valid_checksum(self, env: PackManager, tmp_path):
        pack_dir = _make_pack_with_checksum(tmp_path / "packs", skills=["s1"])
        manifest = env.install(pack_dir)
        assert manifest.name == "demo"

    def test_install_with_bad_checksum(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(
            tmp_path / "packs",
            skills=["s1"],
            checksum="bad0000000000000000000000000000000000000000000000000000000000000",
        )
        with pytest.raises(PackError, match="Checksum mismatch"):
            env.install(pack_dir)

    def test_install_missing_skill_dir(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["missing"], create_contents=False)
        with pytest.raises(PackError, match="validation failed"):
            env.install(pack_dir)

    def test_install_missing_workflow_file(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", workflows=["missing"], create_contents=False)
        with pytest.raises(PackError, match="validation failed"):
            env.install(pack_dir)

    def test_install_missing_manifest(self, env: PackManager, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(PackError, match="not found"):
            env.install(empty_dir)

    def test_install_nonexistent_source(self, env: PackManager, tmp_path):
        with pytest.raises(PackError, match="not found"):
            env.install(tmp_path / "nope")

    def test_install_overwrites_existing(self, env: PackManager, tmp_path):
        pack_v1 = _make_pack(tmp_path / "v1", skills=["s1"], version="1.0.0")
        env.install(pack_v1)
        # Modify the skill script
        (env.skills_dir / "s1" / "run.sh").write_text("#!/bin/bash\necho v1\n")

        pack_v2 = _make_pack(tmp_path / "v2", skills=["s1"], version="2.0.0")
        env.install(pack_v2)
        installed = env.list_installed()
        assert installed[0]["version"] == "2.0.0"


# ---------------------------------------------------------------------------
# PackManager.update tests
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_update_reinstalls_from_source(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"], version="1.0.0")
        env.install(pack_dir)

        # Modify the pack source
        manifest_path = pack_dir / "pack.yaml"
        data = yaml.safe_load(manifest_path.read_text())
        data["version"] = "1.1.0"
        manifest_path.write_text(yaml.dump(data))

        manifest = env.update("demo")
        assert manifest.version == "1.1.0"

    def test_update_not_installed(self, env: PackManager):
        with pytest.raises(PackError, match="not installed"):
            env.update("nonexistent")


# ---------------------------------------------------------------------------
# PackManager.uninstall tests
# ---------------------------------------------------------------------------


class TestUninstall:
    def test_uninstall_removes_files(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"], workflows=["w1"], agents=["a1"])
        env.install(pack_dir)
        assert (env.skills_dir / "s1").exists()
        assert (env.workflows_dir / "w1.yaml").exists()
        assert (env.agents_dir / "a1").exists()

        env.uninstall("demo")
        assert not (env.skills_dir / "s1").exists()
        assert not (env.workflows_dir / "w1.yaml").exists()
        assert not (env.agents_dir / "a1").exists()

    def test_uninstall_removes_from_registry(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"])
        env.install(pack_dir)
        env.uninstall("demo")
        assert env.list_installed() == []

    def test_uninstall_not_installed(self, env: PackManager):
        with pytest.raises(PackError, match="not installed"):
            env.uninstall("nonexistent")

    def test_uninstall_tolerates_missing_files(self, env: PackManager, tmp_path):
        """Uninstall should not fail if files were already manually removed."""
        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"])
        env.install(pack_dir)
        # Manually remove the skill dir
        import shutil

        shutil.rmtree(env.skills_dir / "s1")
        # Should not raise
        env.uninstall("demo")
        assert env.list_installed() == []


# ---------------------------------------------------------------------------
# PackManager.list_installed tests
# ---------------------------------------------------------------------------


class TestListInstalled:
    def test_empty_when_no_packs(self, env: PackManager):
        assert env.list_installed() == []

    def test_lists_all_installed(self, env: PackManager, tmp_path):
        _make_pack(tmp_path / "a", name="alpha", skills=["s1"])
        _make_pack(tmp_path / "b", name="beta", workflows=["w1"])
        env.install(tmp_path / "a" / "alpha")
        env.install(tmp_path / "b" / "beta")
        installed = env.list_installed()
        assert len(installed) == 2
        names = {p["name"] for p in installed}
        assert names == {"alpha", "beta"}


# ---------------------------------------------------------------------------
# PackManager.validate tests
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid_pack(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"], workflows=["w1"])
        errors = env.validate(pack_dir)
        assert errors == []

    def test_valid_pack_with_checksum(self, env: PackManager, tmp_path):
        pack_dir = _make_pack_with_checksum(tmp_path / "packs", skills=["s1"])
        errors = env.validate(pack_dir)
        assert errors == []

    def test_invalid_checksum(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(
            tmp_path / "packs",
            skills=["s1"],
            checksum="deadbeef" * 8,
        )
        errors = env.validate(pack_dir)
        assert any("Checksum mismatch" in e for e in errors)

    def test_missing_manifest(self, env: PackManager, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        errors = env.validate(empty)
        assert any("pack.yaml not found" in e for e in errors)

    def test_missing_skill_dir(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["missing"], create_contents=False)
        errors = env.validate(pack_dir)
        assert any("Skill directory not found" in e for e in errors)

    def test_missing_skill_yaml(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["bad"], create_contents=False)
        # Create the skill dir but not skill.yaml
        skill_dir = pack_dir / "skills" / "bad"
        skill_dir.mkdir(parents=True)
        (skill_dir / "run.sh").write_text("#!/bin/bash\necho hi\n")
        errors = env.validate(pack_dir)
        assert any("skill.yaml" in e for e in errors)

    def test_nonexistent_source(self, env: PackManager, tmp_path):
        errors = env.validate(tmp_path / "nope")
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# Registry persistence tests
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_registry_file_created(self, env: PackManager, tmp_path):
        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"])
        env.install(pack_dir)
        assert env._registry_file.exists()
        data = json.loads(env._registry_file.read_text())
        assert "demo" in data

    def test_corrupted_registry_handled(self, env: PackManager):
        env._registry_dir.mkdir(parents=True, exist_ok=True)
        env._registry_file.write_text("NOT JSON")
        # Should not raise
        assert env.list_installed() == []


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_pack_list_empty(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(pack_group, ["list"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "No packs installed" in result.output

    def test_pack_install_and_list(self, tmp_path, monkeypatch):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"], workflows=["w1"])

        # Monkey-patch PackManager construction to use tmp dirs
        original_init = PackManager.__init__

        def patched_init(self, **kwargs):
            original_init(
                self,
                skills_dir=skills_dir,
                workflows_dir=workflows_dir,
                agents_dir=agents_dir,
                data_dir=data_dir,
            )

        monkeypatch.setattr(PackManager, "__init__", patched_init)

        runner = CliRunner()
        result = runner.invoke(pack_group, ["install", str(pack_dir)], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Installed pack" in result.output
        assert "demo" in result.output

        result = runner.invoke(pack_group, ["list"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "demo" in result.output

    def test_pack_validate_valid(self, tmp_path, monkeypatch):
        pack_dir = _make_pack(tmp_path / "packs", skills=["s1"])

        original_init = PackManager.__init__

        def patched_init(self, **kwargs):
            original_init(self, data_dir=tmp_path / "data")

        monkeypatch.setattr(PackManager, "__init__", patched_init)

        runner = CliRunner()
        result = runner.invoke(pack_group, ["validate", str(pack_dir)], catch_exceptions=False)
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_pack_validate_invalid(self, tmp_path, monkeypatch):
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()

        original_init = PackManager.__init__

        def patched_init(self, **kwargs):
            original_init(self, data_dir=tmp_path / "data")

        monkeypatch.setattr(PackManager, "__init__", patched_init)

        runner = CliRunner()
        result = runner.invoke(pack_group, ["validate", str(bad_dir)], catch_exceptions=False)
        assert result.exit_code == 1
        assert "failed" in result.output.lower() or "not found" in result.output.lower()

    def test_pack_uninstall_not_installed(self, tmp_path, monkeypatch):
        original_init = PackManager.__init__

        def patched_init(self, **kwargs):
            original_init(self, data_dir=tmp_path / "data")

        monkeypatch.setattr(PackManager, "__init__", patched_init)

        runner = CliRunner()
        result = runner.invoke(pack_group, ["uninstall", "nonexistent"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "not installed" in result.output.lower()

    def test_pack_update_not_installed(self, tmp_path, monkeypatch):
        original_init = PackManager.__init__

        def patched_init(self, **kwargs):
            original_init(self, data_dir=tmp_path / "data")

        monkeypatch.setattr(PackManager, "__init__", patched_init)

        runner = CliRunner()
        result = runner.invoke(pack_group, ["update", "nonexistent"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "not installed" in result.output.lower()
