"""Tests for CLI template subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_template import template_group

# --- template init ---


@patch("superpowers.template_manager.TemplateManager")
def test_template_init_installed(mock_cls):
    tm = MagicMock()
    tm.init.return_value = ["hosts.yaml", "profiles.yaml"]
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["init"])
    assert result.exit_code == 0
    assert "hosts.yaml" in result.output
    assert "profiles.yaml" in result.output
    assert "2 template(s) initialized" in result.output


@patch("superpowers.template_manager.TemplateManager")
def test_template_init_already_done(mock_cls):
    tm = MagicMock()
    tm.init.return_value = []
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["init"])
    assert result.exit_code == 0
    assert "All templates already installed" in result.output


# --- template list ---


@patch("superpowers.template_manager.TemplateManager")
def test_template_list_with_templates(mock_cls):
    tm = MagicMock()
    tm.list_templates.return_value = [
        {"name": "hosts.yaml", "dest": "~/.claude-superpowers/hosts.yaml", "status": "current"},
        {
            "name": "profiles.yaml",
            "dest": "~/.claude-superpowers/profiles.yaml",
            "status": "modified",
        },
        {"name": "cron.yaml", "dest": "~/.claude-superpowers/cron.yaml", "status": "missing"},
    ]
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["list"])
    assert result.exit_code == 0
    assert "hosts.yaml" in result.output
    assert "current" in result.output
    assert "modified" in result.output
    assert "missing" in result.output


# --- template diff ---


@patch("superpowers.template_manager.TemplateManager")
def test_template_diff_with_changes(mock_cls):
    tm = MagicMock()
    tm.diff.return_value = {
        "hosts.yaml": "--- shipped\n+++ local\n-old line\n+new line",
        "profiles.yaml": "",
    }
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["diff"])
    assert result.exit_code == 0
    assert "hosts.yaml" in result.output
    assert "+new line" in result.output


@patch("superpowers.template_manager.TemplateManager")
def test_template_diff_no_changes(mock_cls):
    tm = MagicMock()
    tm.diff.return_value = {"hosts.yaml": "", "profiles.yaml": ""}
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["diff"])
    assert result.exit_code == 0
    assert "No differences found" in result.output


@patch("superpowers.template_manager.TemplateManager")
def test_template_diff_specific_name(mock_cls):
    tm = MagicMock()
    tm.diff.return_value = {"hosts.yaml": "some diff"}
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["diff", "hosts.yaml"])
    assert result.exit_code == 0
    tm.diff.assert_called_once_with("hosts.yaml")


# --- template reset ---


@patch("superpowers.template_manager.TemplateManager")
def test_template_reset_ok(mock_cls):
    tm = MagicMock()
    tm.reset.return_value = True
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["reset", "hosts.yaml"])
    assert result.exit_code == 0
    assert "Reset" in result.output
    assert "backup created" in result.output


@patch("superpowers.template_manager.TemplateManager")
def test_template_reset_not_found(mock_cls):
    tm = MagicMock()
    tm.reset.return_value = False
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["reset", "missing.yaml"])
    assert result.exit_code != 0
    assert "not found" in result.output


# --- template upgrade ---


@patch("superpowers.template_manager.TemplateManager")
def test_template_upgrade(mock_cls):
    tm = MagicMock()
    tm.upgrade.return_value = {
        "hosts.yaml": "updated",
        "profiles.yaml": "backup_and_updated",
        "cron.yaml": "skipped",
    }
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["upgrade"])
    assert result.exit_code == 0
    assert "updated" in result.output
    assert "skipped" in result.output
    assert "Upgrade complete" in result.output


@patch("superpowers.template_manager.TemplateManager")
def test_template_upgrade_missing_source(mock_cls):
    tm = MagicMock()
    tm.upgrade.return_value = {"broken.yaml": "missing_source"}
    mock_cls.return_value = tm
    runner = CliRunner()
    result = runner.invoke(template_group, ["upgrade"])
    assert result.exit_code == 0
    assert "source missing" in result.output
