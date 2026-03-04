"""Tests for CLI skill subcommands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_skill import (
    skill_auto_install,
    skill_info,
    skill_link,
    skill_list,
    skill_run,
    skill_validate,
    sync_diff,
    sync_list,
    sync_pull,
    sync_push,
)
from superpowers.skill_registry import Skill


def _make_skill(**kwargs):
    defaults = dict(
        name="test-skill",
        description="A test skill",
        version="1.0.0",
        author="tester",
        script_path=Path("/skills/test-skill/run.sh"),
        triggers=[],
        dependencies=[],
        slash_command=True,
        permissions=["vault"],
    )
    defaults.update(kwargs)
    return Skill(**defaults)


# --- skill list ---


@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_list_happy(mock_cls):
    registry = MagicMock()
    registry.discover.return_value = [_make_skill(), _make_skill(name="other", slash_command=False)]
    mock_cls.return_value = registry
    runner = CliRunner()
    result = runner.invoke(skill_list)
    assert result.exit_code == 0
    assert "test-skill" in result.output
    assert "other" in result.output


@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_list_empty(mock_cls):
    registry = MagicMock()
    registry.discover.return_value = []
    mock_cls.return_value = registry
    runner = CliRunner()
    result = runner.invoke(skill_list)
    assert result.exit_code == 0


# --- skill info ---


@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_info_found(mock_cls):
    registry = MagicMock()
    registry.get.return_value = _make_skill()
    mock_cls.return_value = registry
    runner = CliRunner()
    result = runner.invoke(skill_info, ["test-skill"])
    assert result.exit_code == 0
    assert "test-skill" in result.output
    assert "1.0.0" in result.output
    assert "vault" in result.output


@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_info_not_found(mock_cls):
    registry = MagicMock()
    registry.get.side_effect = KeyError("nope")
    mock_cls.return_value = registry
    runner = CliRunner()
    result = runner.invoke(skill_info, ["missing"])
    assert result.exit_code != 0
    assert "Skill not found" in result.output


# --- skill run ---


@patch("superpowers.cli_skill.SkillLoader")
@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_run_success(mock_reg_cls, mock_loader_cls):
    registry = MagicMock()
    registry.get.return_value = _make_skill()
    mock_reg_cls.return_value = registry

    loader = MagicMock()
    run_result = MagicMock(stdout="output line\n", stderr="", returncode=0)
    loader.run.return_value = run_result
    mock_loader_cls.return_value = loader

    runner = CliRunner()
    result = runner.invoke(skill_run, ["test-skill"])
    assert result.exit_code == 0
    assert "output line" in result.output


@patch("superpowers.cli_skill.SkillLoader")
@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_run_with_args(mock_reg_cls, mock_loader_cls):
    skill = _make_skill()
    registry = MagicMock()
    registry.get.return_value = skill
    mock_reg_cls.return_value = registry

    loader = MagicMock()
    loader.run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    mock_loader_cls.return_value = loader

    runner = CliRunner()
    result = runner.invoke(skill_run, ["test-skill", "key=value", "flag"])
    assert result.exit_code == 0
    loader.run.assert_called_once_with(skill, {"key": "value", "flag": "true"})


@patch("superpowers.cli_skill.SkillLoader")
@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_run_not_found(mock_reg_cls, mock_loader_cls):
    registry = MagicMock()
    registry.get.side_effect = KeyError("nope")
    mock_reg_cls.return_value = registry
    runner = CliRunner()
    result = runner.invoke(skill_run, ["missing"])
    assert result.exit_code != 0
    assert "Skill not found" in result.output


@patch("superpowers.cli_skill.SkillLoader")
@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_run_nonzero_exit(mock_reg_cls, mock_loader_cls):
    registry = MagicMock()
    registry.get.return_value = _make_skill()
    mock_reg_cls.return_value = registry

    loader = MagicMock()
    loader.run.return_value = MagicMock(stdout="", stderr="fail msg", returncode=2)
    mock_loader_cls.return_value = loader

    runner = CliRunner()
    result = runner.invoke(skill_run, ["test-skill"])
    assert result.exit_code != 0
    assert "Exited with code 2" in result.output


# --- skill link ---


@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_link(mock_cls):
    registry = MagicMock()
    link1 = MagicMock()
    link1.resolve.return_value = Path("/skills/test-skill/command.md")
    link1.__str__ = lambda self: "/home/user/.claude/commands/test-skill.md"
    registry.sync_slash_commands.return_value = [link1]
    mock_cls.return_value = registry
    runner = CliRunner()
    result = runner.invoke(skill_link)
    assert result.exit_code == 0
    assert "Synced 1 slash command" in result.output


# --- skill validate ---


@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_validate_ok(mock_cls, tmp_path):
    registry = MagicMock()
    registry.validate.return_value = []
    mock_cls.return_value = registry

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(skill_validate, [str(skill_dir)])
    assert result.exit_code == 0
    assert "Skill is valid" in result.output


@patch("superpowers.cli_skill.SkillRegistry")
def test_skill_validate_errors(mock_cls, tmp_path):
    registry = MagicMock()
    registry.validate.return_value = ["missing skill.yaml", "no script field"]
    mock_cls.return_value = registry

    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(skill_validate, [str(skill_dir)])
    assert result.exit_code != 0
    assert "missing skill.yaml" in result.output


# --- skill auto-install ---


@patch("superpowers.cli_skill.suggest_skill")
def test_skill_auto_install_dry_run(mock_suggest):
    mock_suggest.return_value = {
        "name": "port-scanner",
        "description": "Scans network ports",
        "tags": ["network", "security"],
        "script_type": "python",
        "template": "network-scan",
    }
    runner = CliRunner()
    result = runner.invoke(skill_auto_install, ["scan network ports", "--dry-run"])
    assert result.exit_code == 0
    assert "port-scanner" in result.output
    assert "network-scan" in result.output


@patch("superpowers.cli_skill.install_from_template")
def test_skill_auto_install_from_template(mock_install):
    mock_install.return_value = "heartbeat"
    runner = CliRunner()
    result = runner.invoke(skill_auto_install, ["install heartbeat", "-t", "heartbeat"])
    assert result.exit_code == 0
    assert "Installed template" in result.output


@patch("superpowers.cli_skill.install_from_template")
def test_skill_auto_install_template_error(mock_install):
    mock_install.side_effect = ValueError("unknown template 'xyz'")
    runner = CliRunner()
    result = runner.invoke(skill_auto_install, ["whatever", "-t", "xyz"])
    assert result.exit_code != 0
    assert "unknown template" in result.output


@patch("superpowers.cli_skill.check_and_install")
def test_skill_auto_install_from_description(mock_check):
    mock_check.return_value = "auto-skill"
    runner = CliRunner()
    result = runner.invoke(skill_auto_install, ["check disk space"])
    assert result.exit_code == 0
    assert "Skill ready" in result.output


@patch("superpowers.cli_skill.check_and_install")
def test_skill_auto_install_failed(mock_check):
    mock_check.return_value = None
    runner = CliRunner()
    result = runner.invoke(skill_auto_install, ["impossible task"])
    assert result.exit_code != 0
    assert "Could not create" in result.output


# --- sync push ---


@patch("superpowers.skillhub.SkillHub")
def test_sync_push_success(mock_cls):
    hub = MagicMock()
    hub.push.return_value = MagicMock(action="pushed", message="ok")
    mock_cls.return_value = hub
    runner = CliRunner()
    result = runner.invoke(sync_push, ["my-skill"])
    assert result.exit_code == 0
    assert "Pushed" in result.output


@patch("superpowers.skillhub.SkillHub")
def test_sync_push_error(mock_cls):
    hub = MagicMock()
    hub.push.return_value = MagicMock(action="error", message="no remote")
    mock_cls.return_value = hub
    runner = CliRunner()
    result = runner.invoke(sync_push, ["my-skill"])
    assert result.exit_code != 0
    assert "no remote" in result.output


@patch("superpowers.skillhub.SkillHub")
def test_sync_push_up_to_date(mock_cls):
    hub = MagicMock()
    hub.push.return_value = MagicMock(action="up-to-date", message="")
    mock_cls.return_value = hub
    runner = CliRunner()
    result = runner.invoke(sync_push, ["my-skill"])
    assert result.exit_code == 0
    assert "up to date" in result.output


# --- sync pull ---


@patch("superpowers.skillhub.SkillHub")
def test_sync_pull_success(mock_cls):
    hub = MagicMock()
    hub.pull.return_value = [MagicMock(action="pulled", skill_name="a", message="")]
    mock_cls.return_value = hub
    runner = CliRunner()
    result = runner.invoke(sync_pull, ["a"])
    assert result.exit_code == 0
    assert "Pulled" in result.output


@patch("superpowers.skillhub.SkillHub")
def test_sync_pull_error(mock_cls):
    hub = MagicMock()
    hub.pull.return_value = [MagicMock(action="error", skill_name="x", message="not found")]
    mock_cls.return_value = hub
    runner = CliRunner()
    result = runner.invoke(sync_pull, ["x"])
    assert result.exit_code != 0
    assert "not found" in result.output


# --- sync list ---


@patch("superpowers.skillhub.SkillHub")
def test_sync_list_with_skills(mock_cls):
    hub = MagicMock()
    hub.list_remote.return_value = [{"name": "sk1", "version": "1.0", "description": "Skill 1"}]
    mock_cls.return_value = hub
    runner = CliRunner()
    result = runner.invoke(sync_list)
    assert result.exit_code == 0
    assert "sk1" in result.output


@patch("superpowers.skillhub.SkillHub")
def test_sync_list_empty(mock_cls):
    hub = MagicMock()
    hub.list_remote.return_value = []
    mock_cls.return_value = hub
    runner = CliRunner()
    result = runner.invoke(sync_list)
    assert result.exit_code == 0
    assert "No skills found" in result.output


# --- sync diff ---


@patch("superpowers.skillhub.SkillHub")
def test_sync_diff(mock_cls):
    hub = MagicMock()
    hub.diff.return_value = "--- local\n+++ remote\n@@ diff @@"
    mock_cls.return_value = hub
    runner = CliRunner()
    result = runner.invoke(sync_diff, ["my-skill"])
    assert result.exit_code == 0
    assert "diff" in result.output
