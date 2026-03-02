from __future__ import annotations

import stat
from pathlib import Path

import pytest
import yaml

from superpowers.skill_creator import create_skill, scaffold_from_existing


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / "skills"
    d.mkdir()
    return d


class TestCreateSkill:
    def test_creates_all_files(self, skills_dir: Path) -> None:
        result = create_skill(
            name="hello-world",
            description="A test skill",
            skills_dir=skills_dir,
        )
        assert result == skills_dir / "hello-world"
        assert (result / "skill.yaml").is_file()
        assert (result / "run.sh").is_file()
        assert (result / "command.md").is_file()

    def test_bash_script_type(self, skills_dir: Path) -> None:
        result = create_skill(
            name="bash-skill",
            description="Bash skill",
            script_type="bash",
            skills_dir=skills_dir,
        )
        script = result / "run.sh"
        assert script.is_file()
        assert not (result / "run.py").exists()

        content = script.read_text()
        assert content.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in content

        # Executable bit
        assert script.stat().st_mode & stat.S_IXUSR

    def test_python_script_type(self, skills_dir: Path) -> None:
        result = create_skill(
            name="py-skill",
            description="Python skill",
            script_type="python",
            skills_dir=skills_dir,
        )
        script = result / "run.py"
        assert script.is_file()
        assert not (result / "run.sh").exists()

        content = script.read_text()
        assert content.startswith("#!/usr/bin/env python3")
        assert "argparse" in content

        assert script.stat().st_mode & stat.S_IXUSR

    def test_skill_yaml_fields(self, skills_dir: Path) -> None:
        result = create_skill(
            name="my-skill",
            description="Does things",
            script_type="python",
            permissions=["fs:read", "net:outbound"],
            triggers=["on-commit"],
            skills_dir=skills_dir,
        )
        data = yaml.safe_load((result / "skill.yaml").read_text())
        assert data["name"] == "my-skill"
        assert data["description"] == "Does things"
        assert data["script"] == "run.py"
        assert data["permissions"] == ["fs:read", "net:outbound"]
        assert data["triggers"] == ["on-commit"]
        assert data["slash_command"] is True

    def test_kebab_case_normalisation(self, skills_dir: Path) -> None:
        result = create_skill(
            name="My Cool Skill",
            description="test",
            skills_dir=skills_dir,
        )
        assert result.name == "my-cool-skill"

    def test_command_md_content(self, skills_dir: Path) -> None:
        result = create_skill(
            name="deploy-app",
            description="Deploy the app to prod",
            skills_dir=skills_dir,
        )
        md = (result / "command.md").read_text()
        assert "Deploy App" in md
        assert "Deploy the app to prod" in md


class TestScaffoldFromExisting:
    def test_copies_bash_script(self, skills_dir: Path, tmp_path: Path) -> None:
        src = tmp_path / "myscript.sh"
        src.write_text("#!/usr/bin/env bash\necho hello\n")

        result = scaffold_from_existing(
            source_script=src,
            name="from-existing",
            description="Imported skill",
            skills_dir=skills_dir,
        )
        assert result == skills_dir / "from-existing"
        assert (result / "run.sh").is_file()
        assert (result / "run.sh").read_text() == src.read_text()
        assert (result / "skill.yaml").is_file()
        assert (result / "command.md").is_file()

    def test_copies_python_script(self, skills_dir: Path, tmp_path: Path) -> None:
        src = tmp_path / "tool.py"
        src.write_text("#!/usr/bin/env python3\nimport sys\nprint('hi')\n")

        result = scaffold_from_existing(
            source_script=src,
            name="py-import",
            description="Imported python skill",
            skills_dir=skills_dir,
        )
        assert (result / "run.py").is_file()
        data = yaml.safe_load((result / "skill.yaml").read_text())
        assert data["script"] == "run.py"

    def test_missing_source_raises(self, skills_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            scaffold_from_existing(
                source_script=Path("/nonexistent/script.sh"),
                name="nope",
                description="should fail",
                skills_dir=skills_dir,
            )

    def test_script_is_executable(self, skills_dir: Path, tmp_path: Path) -> None:
        src = tmp_path / "run.sh"
        src.write_text("#!/bin/bash\necho ok\n")

        result = scaffold_from_existing(
            source_script=src,
            name="exec-test",
            description="test",
            skills_dir=skills_dir,
        )
        assert (result / "run.sh").stat().st_mode & stat.S_IXUSR
