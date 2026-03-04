from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from superpowers.auto_install import (
    BUILTIN_TEMPLATES,
    _match_template,
    _tokenize,
    check_and_install,
    install_from_template,
    suggest_skill,
)
from superpowers.skill_registry import SkillRegistry


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / "skills"
    d.mkdir()
    return d


@pytest.fixture()
def registry(skills_dir: Path) -> SkillRegistry:
    return SkillRegistry(skills_dir)


class TestTokenize:
    def test_splits_words(self) -> None:
        assert _tokenize("scan network hosts") == {"scan", "network", "hosts"}

    def test_ignores_single_char(self) -> None:
        assert "a" not in _tokenize("a big scan")

    def test_lowercases(self) -> None:
        assert _tokenize("Docker Health") == {"docker", "health"}


class TestMatchTemplate:
    def test_matches_network(self) -> None:
        assert _match_template("scan the network for hosts") == "network-scan"

    def test_matches_disk(self) -> None:
        assert _match_template("check disk usage") == "disk-usage"

    def test_matches_git(self) -> None:
        assert _match_template("show git commit stats") == "git-stats"

    def test_matches_docker(self) -> None:
        assert _match_template("docker container health check") == "docker-health"

    def test_matches_log(self) -> None:
        assert _match_template("search logs for errors") == "log-search"

    def test_no_match(self) -> None:
        assert _match_template("make me a sandwich") is None


class TestSuggestSkill:
    def test_suggests_template_match(self) -> None:
        result = suggest_skill("scan the network")
        assert result["name"] == "network-scan"
        assert result["template"] == "network-scan"
        assert "network" in result["tags"]

    def test_suggests_generic_when_no_match(self) -> None:
        result = suggest_skill("compile rust project")
        assert result["template"] is None
        assert result["name"] == "compile-rust-project"
        assert result["script_type"] == "bash"

    def test_tags_from_description(self) -> None:
        result = suggest_skill("compile rust project")
        assert isinstance(result["tags"], list)
        assert len(result["tags"]) <= 5


class TestInstallFromTemplate:
    def test_installs_network_scan(self, skills_dir: Path) -> None:
        name = install_from_template("network-scan", skills_dir=skills_dir)
        assert name == "network-scan"

        skill_dir = skills_dir / "network-scan"
        assert (skill_dir / "skill.yaml").is_file()
        assert (skill_dir / "run.sh").is_file()

        data = yaml.safe_load((skill_dir / "skill.yaml").read_text())
        assert data["name"] == "network-scan"

        script = (skill_dir / "run.sh").read_text()
        assert "nmap" in script

    def test_installs_all_templates(self, tmp_path: Path) -> None:
        for tpl_name in BUILTIN_TEMPLATES:
            d = tmp_path / tpl_name
            d.mkdir()
            name = install_from_template(tpl_name, skills_dir=d)
            assert name == tpl_name
            assert (d / tpl_name / "skill.yaml").is_file()

    def test_unknown_template_raises(self, skills_dir: Path) -> None:
        with pytest.raises(ValueError, match="Unknown template"):
            install_from_template("nonexistent", skills_dir=skills_dir)

    def test_registers_with_registry(self, skills_dir: Path, registry: SkillRegistry) -> None:
        install_from_template("disk-usage", skills_dir=skills_dir, registry=registry)
        skill = registry.get("disk-usage")
        assert skill.name == "disk-usage"


class TestCheckAndInstall:
    def test_installs_from_template_match(self, skills_dir: Path, registry: SkillRegistry) -> None:
        name = check_and_install("scan the network", skills_dir=skills_dir, registry=registry)
        assert name == "network-scan"
        skill = registry.get("network-scan")
        assert skill is not None

    def test_returns_existing_skill(self, skills_dir: Path, registry: SkillRegistry) -> None:
        # Pre-install a skill
        install_from_template("docker-health", skills_dir=skills_dir, registry=registry)
        registry.discover()

        # Now ask for docker-related capability -- should return existing
        name = check_and_install("check docker health", skills_dir=skills_dir, registry=registry)
        assert name == "docker-health"

    def test_scaffolds_generic_skill(self, skills_dir: Path, registry: SkillRegistry) -> None:
        name = check_and_install(
            "backup postgres database", skills_dir=skills_dir, registry=registry
        )
        assert name == "backup-postgres-database"
        assert (skills_dir / "backup-postgres-database" / "skill.yaml").is_file()
        assert (skills_dir / "backup-postgres-database" / "run.sh").is_file()

    def test_returns_none_for_empty(self, skills_dir: Path, registry: SkillRegistry) -> None:
        name = check_and_install("", skills_dir=skills_dir, registry=registry)
        assert name is None

    def test_long_description_truncated(self, skills_dir: Path, registry: SkillRegistry) -> None:
        desc = "a " * 50 + "very long description"
        name = check_and_install(desc, skills_dir=skills_dir, registry=registry)
        assert name is not None
        assert len(name) <= 40
