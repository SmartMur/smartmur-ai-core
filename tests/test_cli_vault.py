"""Tests for CLI vault subcommands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from superpowers.cli_vault import vault_group
from superpowers.vault import VaultError


# --- vault init ---


@patch("superpowers.cli_vault.Vault")
def test_vault_init_ok(mock_cls):
    v = MagicMock()
    v.init.return_value = "age1xyz..."
    v.identity_file = "/home/user/.age-key"
    v.vault_path = "/home/user/.vault.enc"
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["init"])
    assert result.exit_code == 0
    assert "Vault initialized" in result.output
    assert "age1xyz" in result.output


@patch("superpowers.cli_vault.Vault")
def test_vault_init_error(mock_cls):
    v = MagicMock()
    v.init.side_effect = VaultError("age-keygen not found")
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["init"])
    assert result.exit_code != 0
    assert "age-keygen not found" in result.output


# --- vault set ---


@patch("superpowers.cli_vault.Vault")
def test_vault_set_ok(mock_cls):
    v = MagicMock()
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["set", "API_KEY", "secret123"])
    assert result.exit_code == 0
    assert "Set" in result.output
    assert "API_KEY" in result.output
    v.set.assert_called_once_with("API_KEY", "secret123")


@patch("superpowers.cli_vault.Vault")
def test_vault_set_error(mock_cls):
    v = MagicMock()
    v.set.side_effect = VaultError("vault not initialized")
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["set", "K", "V"])
    assert result.exit_code != 0
    assert "vault not initialized" in result.output


# --- vault get ---


@patch("superpowers.cli_vault.Vault")
def test_vault_get_masked(mock_cls):
    v = MagicMock()
    v.get.return_value = "supersecret123"
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["get", "API_KEY"])
    assert result.exit_code == 0
    assert "API_KEY" in result.output
    # Should be masked: first 2 + last 2 visible
    assert "su" in result.output
    assert "23" in result.output
    assert "supersecret123" not in result.output


@patch("superpowers.cli_vault.Vault")
def test_vault_get_revealed(mock_cls):
    v = MagicMock()
    v.get.return_value = "supersecret123"
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["get", "API_KEY", "--reveal"])
    assert result.exit_code == 0
    assert "supersecret123" in result.output


@patch("superpowers.cli_vault.Vault")
def test_vault_get_not_found(mock_cls):
    v = MagicMock()
    v.get.return_value = None
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["get", "MISSING"])
    assert result.exit_code != 0
    assert "Key not found" in result.output


@patch("superpowers.cli_vault.Vault")
def test_vault_get_short_value(mock_cls):
    v = MagicMock()
    v.get.return_value = "ab"  # <= 4 chars
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["get", "SHORT"])
    assert result.exit_code == 0
    assert "****" in result.output


# --- vault list ---


@patch("superpowers.cli_vault.Vault")
def test_vault_list_with_keys(mock_cls):
    v = MagicMock()
    v.list_keys.return_value = ["API_KEY", "DB_PASS", "SSH_KEY"]
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["list"])
    assert result.exit_code == 0
    assert "API_KEY" in result.output
    assert "DB_PASS" in result.output
    assert "SSH_KEY" in result.output


@patch("superpowers.cli_vault.Vault")
def test_vault_list_empty(mock_cls):
    v = MagicMock()
    v.list_keys.return_value = []
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["list"])
    assert result.exit_code == 0
    assert "Vault is empty" in result.output


@patch("superpowers.cli_vault.Vault")
def test_vault_list_error(mock_cls):
    v = MagicMock()
    v.list_keys.side_effect = VaultError("decrypt fail")
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["list"])
    assert result.exit_code != 0
    assert "decrypt fail" in result.output


# --- vault delete ---


@patch("superpowers.cli_vault.Vault")
def test_vault_delete_ok(mock_cls):
    v = MagicMock()
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["delete", "OLD_KEY"])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    assert "OLD_KEY" in result.output
    v.delete.assert_called_once_with("OLD_KEY")


@patch("superpowers.cli_vault.Vault")
def test_vault_delete_error(mock_cls):
    v = MagicMock()
    v.delete.side_effect = VaultError("key not found")
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["delete", "MISSING"])
    assert result.exit_code != 0
    assert "key not found" in result.output


# --- rotation check ---


@patch("superpowers.credential_rotation.CredentialRotationChecker")
@patch("superpowers.cli_vault.Vault")
def test_rotation_check_with_alerts(mock_vault_cls, mock_checker_cls):
    from superpowers.credential_rotation import AlertStatus

    v = MagicMock()
    v.list_keys.return_value = ["API_KEY", "OLD_KEY"]
    mock_vault_cls.return_value = v

    alert1 = MagicMock()
    alert1.key = "API_KEY"
    alert1.age_days = 10
    alert1.max_age_days = 90
    alert1.status = AlertStatus.ok

    alert2 = MagicMock()
    alert2.key = "OLD_KEY"
    alert2.age_days = 100
    alert2.max_age_days = 90
    alert2.status = AlertStatus.expired

    checker = MagicMock()
    checker.check_all.return_value = [alert1, alert2]
    mock_checker_cls.return_value = checker

    runner = CliRunner()
    result = runner.invoke(vault_group, ["rotation", "check"])
    assert result.exit_code == 0
    assert "API_KEY" in result.output
    assert "OLD_KEY" in result.output


@patch("superpowers.cli_vault.Vault")
def test_rotation_check_empty_vault(mock_cls):
    v = MagicMock()
    v.list_keys.return_value = []
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["rotation", "check"])
    assert result.exit_code == 0
    assert "Vault is empty" in result.output


@patch("superpowers.cli_vault.Vault")
def test_rotation_check_vault_error(mock_cls):
    v = MagicMock()
    v.list_keys.side_effect = VaultError("decrypt fail")
    mock_cls.return_value = v
    runner = CliRunner()
    result = runner.invoke(vault_group, ["rotation", "check"])
    assert result.exit_code != 0
    assert "decrypt fail" in result.output


# --- rotation policy set ---


@patch("superpowers.credential_rotation.CredentialRotationChecker")
def test_rotation_policy_set_ok(mock_cls):
    checker = MagicMock()
    mock_cls.return_value = checker
    runner = CliRunner()
    result = runner.invoke(vault_group, ["rotation", "policy", "set", "API_KEY", "90"])
    assert result.exit_code == 0
    assert "Policy set" in result.output
    assert "90" in result.output
    checker.set_policy.assert_called_once_with("API_KEY", 90)


@patch("superpowers.credential_rotation.CredentialRotationChecker")
def test_rotation_policy_set_zero(mock_cls):
    runner = CliRunner()
    result = runner.invoke(vault_group, ["rotation", "policy", "set", "K", "0"])
    assert result.exit_code != 0
    assert "days must be >= 1" in result.output


# --- rotation policy list ---


@patch("superpowers.credential_rotation.CredentialRotationChecker")
def test_rotation_policy_list_with_policies(mock_cls):
    checker = MagicMock()
    policy = MagicMock()
    policy.max_age_days = 90
    policy.last_rotated = "2026-01-01"
    checker.list_policies.return_value = {"API_KEY": policy}
    mock_cls.return_value = checker
    runner = CliRunner()
    result = runner.invoke(vault_group, ["rotation", "policy", "list"])
    assert result.exit_code == 0
    assert "API_KEY" in result.output
    assert "90" in result.output


@patch("superpowers.credential_rotation.CredentialRotationChecker")
def test_rotation_policy_list_empty(mock_cls):
    checker = MagicMock()
    checker.list_policies.return_value = {}
    mock_cls.return_value = checker
    runner = CliRunner()
    result = runner.invoke(vault_group, ["rotation", "policy", "list"])
    assert result.exit_code == 0
    assert "No rotation policies configured" in result.output
