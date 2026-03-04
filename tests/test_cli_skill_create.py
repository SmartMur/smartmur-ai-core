"""Tests for CLI skill create subcommand."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_skill_create import skill_create

# --- skill create ---


@patch("superpowers.cli_skill_create.SkillRegistry")
@patch("superpowers.cli_skill_create.create_skill")
def test_skill_create_bash(mock_create, mock_reg_cls, tmp_path):
    skill_dir = tmp_path / "my-tool"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text("name: my-tool")
    (skill_dir / "run.sh").write_text("#!/bin/bash")
    (skill_dir / "command.md").write_text("# my-tool")
    mock_create.return_value = skill_dir

    registry = MagicMock()
    registry.sync_slash_commands.return_value = [Path("/home/user/.claude/commands/my-tool.md")]
    mock_reg_cls.return_value = registry

    runner = CliRunner()
    result = runner.invoke(
        skill_create,
        input="my-tool\nA useful tool\nbash\n",
    )
    assert result.exit_code == 0
    assert "Created skill" in result.output
    assert "my-tool" in result.output
    assert "run.sh" in result.output
    mock_create.assert_called_once()


@patch("superpowers.cli_skill_create.SkillRegistry")
@patch("superpowers.cli_skill_create.create_skill")
def test_skill_create_python(mock_create, mock_reg_cls, tmp_path):
    skill_dir = tmp_path / "scanner"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text("name: scanner")
    (skill_dir / "run.py").write_text("print('hi')")
    mock_create.return_value = skill_dir

    registry = MagicMock()
    registry.sync_slash_commands.return_value = []
    mock_reg_cls.return_value = registry

    runner = CliRunner()
    result = runner.invoke(
        skill_create,
        ["--name", "scanner", "--description", "Scan stuff", "--type", "python"],
    )
    assert result.exit_code == 0
    assert "Created skill" in result.output
    assert "run.py" in result.output


@patch("superpowers.cli_skill_create.SkillRegistry")
@patch("superpowers.cli_skill_create.create_skill")
def test_skill_create_with_permissions(mock_create, mock_reg_cls, tmp_path):
    skill_dir = tmp_path / "vault-reader"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text("name: vault-reader")
    (skill_dir / "run.sh").write_text("#!/bin/bash")
    mock_create.return_value = skill_dir

    registry = MagicMock()
    registry.sync_slash_commands.return_value = []
    mock_reg_cls.return_value = registry

    runner = CliRunner()
    result = runner.invoke(
        skill_create,
        [
            "--name",
            "vault-reader",
            "--description",
            "Read vault secrets",
            "--type",
            "bash",
            "-p",
            "vault",
            "-p",
            "ssh",
        ],
    )
    assert result.exit_code == 0
    _, kwargs = mock_create.call_args
    assert kwargs["permissions"] == ["vault", "ssh"]


@patch("superpowers.cli_skill_create.SkillRegistry")
@patch("superpowers.cli_skill_create.create_skill")
def test_skill_create_with_triggers(mock_create, mock_reg_cls, tmp_path):
    skill_dir = tmp_path / "watcher"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text("name: watcher")
    (skill_dir / "run.sh").write_text("#!/bin/bash")
    mock_create.return_value = skill_dir

    registry = MagicMock()
    registry.sync_slash_commands.return_value = []
    mock_reg_cls.return_value = registry

    runner = CliRunner()
    result = runner.invoke(
        skill_create,
        [
            "--name",
            "watcher",
            "--description",
            "Watch files",
            "--type",
            "bash",
            "-t",
            "file-change",
            "-t",
            "cron",
        ],
    )
    assert result.exit_code == 0
    _, kwargs = mock_create.call_args
    assert kwargs["triggers"] == ["file-change", "cron"]


@patch("superpowers.cli_skill_create.SkillRegistry")
@patch("superpowers.cli_skill_create.create_skill")
def test_skill_create_no_synced_commands(mock_create, mock_reg_cls, tmp_path):
    skill_dir = tmp_path / "basic"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text("name: basic")
    (skill_dir / "run.sh").write_text("#!/bin/bash")
    mock_create.return_value = skill_dir

    registry = MagicMock()
    registry.sync_slash_commands.return_value = []
    mock_reg_cls.return_value = registry

    runner = CliRunner()
    result = runner.invoke(
        skill_create,
        ["--name", "basic", "--description", "Basic skill", "--type", "bash"],
    )
    assert result.exit_code == 0
    assert "No slash_command skills to sync" in result.output


@patch("superpowers.cli_skill_create.SkillRegistry")
@patch("superpowers.cli_skill_create.create_skill")
def test_skill_create_defaults_no_perms_triggers(mock_create, mock_reg_cls, tmp_path):
    skill_dir = tmp_path / "bare"
    skill_dir.mkdir()
    (skill_dir / "run.sh").write_text("#!/bin/bash")
    mock_create.return_value = skill_dir

    registry = MagicMock()
    registry.sync_slash_commands.return_value = []
    mock_reg_cls.return_value = registry

    runner = CliRunner()
    result = runner.invoke(
        skill_create,
        ["--name", "bare", "--description", "Bare", "--type", "bash"],
    )
    assert result.exit_code == 0
    _, kwargs = mock_create.call_args
    assert kwargs["permissions"] is None
    assert kwargs["triggers"] is None
