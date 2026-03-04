"""Tests for CLI setup subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_setup import setup_group


# --- setup run ---


@patch("superpowers.cli_setup.SetupWizard", create=True)
def test_setup_run_interactive(mock_cls):
    # SetupWizard is imported lazily inside the command, so we patch at module level
    wizard = MagicMock()
    mock_cls.return_value = wizard
    runner = CliRunner()
    with patch("superpowers.setup_wizard.SetupWizard", mock_cls):
        result = runner.invoke(setup_group, ["run"])
    assert result.exit_code == 0


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_run_non_interactive(mock_cls):
    wizard = MagicMock()
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["run", "--non-interactive"])
    assert result.exit_code == 0
    mock_cls.assert_called_once_with(non_interactive=True)
    wizard.run.assert_called_once()


# --- setup check ---


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_check_all_ok(mock_cls):
    wizard = MagicMock()
    wizard.check_prereqs.return_value = {"python": True, "docker": True, "redis": True}
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["check"])
    assert result.exit_code == 0
    assert "All prerequisites satisfied" in result.output


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_check_missing(mock_cls):
    wizard = MagicMock()
    wizard.check_prereqs.return_value = {"python": True, "docker": False, "age": False}
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["check"])
    assert result.exit_code == 0
    assert "Missing" in result.output
    assert "docker" in result.output
    assert "age" in result.output


# --- setup env ---


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_env_happy(mock_cls):
    wizard = MagicMock()
    wizard.create_env.return_value = "/home/ray/claude-superpowers/.env"
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["env"])
    assert result.exit_code == 0
    assert "Created" in result.output


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_env_not_found(mock_cls):
    wizard = MagicMock()
    wizard.create_env.side_effect = FileNotFoundError(".env.example not found")
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["env"])
    assert result.exit_code != 0
    assert ".env.example" in result.output


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_env_non_interactive(mock_cls):
    wizard = MagicMock()
    wizard.create_env.return_value = "/path/.env"
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["env", "--non-interactive"])
    assert result.exit_code == 0
    mock_cls.assert_called_once_with(non_interactive=True)


# --- setup vault ---


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_vault_ok(mock_cls):
    wizard = MagicMock()
    wizard.init_vault.return_value = True
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["vault"])
    assert result.exit_code == 0
    assert "Vault initialized" in result.output


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_vault_skipped(mock_cls):
    wizard = MagicMock()
    wizard.init_vault.return_value = False
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["vault"])
    assert result.exit_code == 0
    assert "skipped" in result.output


# --- setup telegram ---


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_telegram_valid(mock_cls):
    wizard = MagicMock()
    wizard.setup_telegram.return_value = {
        "valid": True,
        "bot_info": {"username": "test_bot"},
        "webhook_set": True,
        "config": {"ALLOWED_CHAT_IDS": "123,456"},
    }
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(
        setup_group,
        ["telegram", "--token", "123:ABC", "--webhook-url", "https://x.com/hook", "--chat-ids", "123,456"],
    )
    assert result.exit_code == 0
    assert "Bot validated" in result.output
    assert "test_bot" in result.output
    assert "Webhook configured" in result.output


@patch("superpowers.setup_wizard.SetupWizard")
def test_setup_telegram_invalid(mock_cls):
    wizard = MagicMock()
    wizard.setup_telegram.return_value = {
        "valid": False,
        "bot_info": {},
        "webhook_set": False,
        "config": {},
    }
    mock_cls.return_value = wizard
    runner = CliRunner()
    result = runner.invoke(setup_group, ["telegram"])
    assert result.exit_code == 0
    assert "not provided or invalid" in result.output
