"""Tests for the encrypted vault module."""

from __future__ import annotations

import subprocess

import pytest

from superpowers.vault import Vault, VaultError


@pytest.fixture
def vault(tmp_path):
    vault_path = tmp_path / "vault.enc"
    identity_file = tmp_path / "age-identity.txt"
    v = Vault(vault_path=vault_path, identity_file=identity_file)
    return v


@pytest.fixture
def initialized_vault(vault):
    vault.init()
    return vault


class TestInit:
    def test_creates_identity_file(self, vault):
        vault.init()
        assert vault.identity_file.exists()

    def test_creates_vault_file(self, vault):
        vault.init()
        assert vault.vault_path.exists()

    def test_identity_has_restricted_permissions(self, vault):
        vault.init()
        mode = vault.identity_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_returns_public_key(self, vault):
        pubkey = vault.init()
        assert pubkey.startswith("age1")

    def test_idempotent(self, vault):
        key1 = vault.init()
        key2 = vault.init()
        assert key1 == key2


class TestSetGet:
    def test_roundtrip(self, initialized_vault):
        initialized_vault.set("API_KEY", "sk-test-12345")
        assert initialized_vault.get("API_KEY") == "sk-test-12345"

    def test_get_missing_key(self, initialized_vault):
        assert initialized_vault.get("NONEXISTENT") is None

    def test_overwrite(self, initialized_vault):
        initialized_vault.set("KEY", "old")
        initialized_vault.set("KEY", "new")
        assert initialized_vault.get("KEY") == "new"

    def test_multiple_keys(self, initialized_vault):
        initialized_vault.set("A", "1")
        initialized_vault.set("B", "2")
        initialized_vault.set("C", "3")
        assert initialized_vault.get("A") == "1"
        assert initialized_vault.get("B") == "2"
        assert initialized_vault.get("C") == "3"


class TestListKeys:
    def test_empty_vault(self, initialized_vault):
        assert initialized_vault.list_keys() == []

    def test_returns_sorted_keys(self, initialized_vault):
        initialized_vault.set("ZEBRA", "z")
        initialized_vault.set("ALPHA", "a")
        initialized_vault.set("MIDDLE", "m")
        assert initialized_vault.list_keys() == ["ALPHA", "MIDDLE", "ZEBRA"]

    def test_no_values_leaked(self, initialized_vault):
        initialized_vault.set("SECRET", "super-secret-value")
        keys = initialized_vault.list_keys()
        assert "super-secret-value" not in keys


class TestDelete:
    def test_delete_existing(self, initialized_vault):
        initialized_vault.set("KEY", "val")
        initialized_vault.delete("KEY")
        assert initialized_vault.get("KEY") is None

    def test_delete_missing_raises(self, initialized_vault):
        with pytest.raises(VaultError, match="Key not found"):
            initialized_vault.delete("NONEXISTENT")

    def test_delete_preserves_other_keys(self, initialized_vault):
        initialized_vault.set("KEEP", "yes")
        initialized_vault.set("DROP", "no")
        initialized_vault.delete("DROP")
        assert initialized_vault.get("KEEP") == "yes"
        assert initialized_vault.list_keys() == ["KEEP"]


class TestExportEnv:
    def test_export_all(self, initialized_vault):
        initialized_vault.set("A", "1")
        initialized_vault.set("B", "2")
        result = initialized_vault.export_env()
        assert result == {"A": "1", "B": "2"}

    def test_export_subset(self, initialized_vault):
        initialized_vault.set("A", "1")
        initialized_vault.set("B", "2")
        initialized_vault.set("C", "3")
        result = initialized_vault.export_env(["A", "C"])
        assert result == {"A": "1", "C": "3"}

    def test_export_missing_key_skipped(self, initialized_vault):
        initialized_vault.set("A", "1")
        result = initialized_vault.export_env(["A", "NOPE"])
        assert result == {"A": "1"}


class TestAtomicWrite:
    def test_no_tmp_files_left(self, initialized_vault):
        initialized_vault.set("KEY", "val")
        parent = initialized_vault.vault_path.parent
        tmp_files = list(parent.glob(".vault-*.tmp"))
        assert tmp_files == []


class TestDecryptEmptyVault:
    def test_missing_vault_file(self, vault):
        """_decrypt returns empty dict when vault file doesn't exist."""
        assert not vault.vault_path.exists()
        data = vault._decrypt()
        assert data == {}
