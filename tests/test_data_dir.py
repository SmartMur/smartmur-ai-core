"""Tests for the config-driven data directory (get_data_dir)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest


def test_get_data_dir_default():
    """Without any env vars, get_data_dir returns ~/.claude-superpowers."""
    from superpowers.config import get_data_dir

    with mock.patch.dict(os.environ, {}, clear=True):
        # Remove both env vars if present
        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPERPOWERS_DATA_DIR", "CLAUDE_SUPERPOWERS_DATA_DIR")}
        with mock.patch.dict(os.environ, env, clear=True):
            result = get_data_dir()
            assert result == Path.home() / ".claude-superpowers"


def test_get_data_dir_superpowers_env(tmp_path):
    """SUPERPOWERS_DATA_DIR overrides the default."""
    from superpowers.config import get_data_dir

    custom = str(tmp_path / "custom-data")
    with mock.patch.dict(os.environ, {"SUPERPOWERS_DATA_DIR": custom}, clear=False):
        # Remove legacy var if set
        os.environ.pop("CLAUDE_SUPERPOWERS_DATA_DIR", None)
        result = get_data_dir()
        assert result == Path(custom)


def test_get_data_dir_legacy_env(tmp_path):
    """CLAUDE_SUPERPOWERS_DATA_DIR (legacy) also works."""
    from superpowers.config import get_data_dir

    custom = str(tmp_path / "legacy-data")
    with mock.patch.dict(os.environ, {"CLAUDE_SUPERPOWERS_DATA_DIR": custom}, clear=False):
        os.environ.pop("SUPERPOWERS_DATA_DIR", None)
        result = get_data_dir()
        assert result == Path(custom)


def test_get_data_dir_preferred_over_legacy(tmp_path):
    """SUPERPOWERS_DATA_DIR takes precedence over CLAUDE_SUPERPOWERS_DATA_DIR."""
    from superpowers.config import get_data_dir

    preferred = str(tmp_path / "preferred")
    legacy = str(tmp_path / "legacy")
    with mock.patch.dict(os.environ, {
        "SUPERPOWERS_DATA_DIR": preferred,
        "CLAUDE_SUPERPOWERS_DATA_DIR": legacy,
    }, clear=False):
        result = get_data_dir()
        assert result == Path(preferred)


def test_settings_data_dir_default():
    """Settings().data_dir defaults to get_data_dir()."""
    from superpowers.config import Settings, get_data_dir

    with mock.patch.dict(os.environ, {}, clear=True):
        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPERPOWERS_DATA_DIR", "CLAUDE_SUPERPOWERS_DATA_DIR")}
        with mock.patch.dict(os.environ, env, clear=True):
            s = Settings()
            assert s.data_dir == get_data_dir()


def test_settings_load_respects_env(tmp_path):
    """Settings.load() picks up the data dir from the env var."""
    from superpowers.config import Settings

    custom = str(tmp_path / "from-load")
    with mock.patch.dict(os.environ, {"SUPERPOWERS_DATA_DIR": custom}, clear=False):
        os.environ.pop("CLAUDE_SUPERPOWERS_DATA_DIR", None)
        s = Settings.load(dotenv_path=tmp_path / "nonexistent.env")
        assert s.data_dir == Path(custom)


def test_get_data_dir_returns_path():
    """get_data_dir always returns a Path object."""
    from superpowers.config import get_data_dir

    assert isinstance(get_data_dir(), Path)


def test_audit_log_uses_data_dir(tmp_path):
    """AuditLog default path should come from get_data_dir."""
    from superpowers.config import get_data_dir

    custom = str(tmp_path / "audit-test")
    with mock.patch.dict(os.environ, {"SUPERPOWERS_DATA_DIR": custom}, clear=False):
        os.environ.pop("CLAUDE_SUPERPOWERS_DATA_DIR", None)
        from superpowers.audit import AuditLog
        audit = AuditLog()
        assert audit.path == Path(custom) / "audit.log"


def test_memory_store_uses_data_dir(tmp_path):
    """MemoryStore default path should come from get_data_dir."""
    custom = str(tmp_path / "mem-test")
    with mock.patch.dict(os.environ, {"SUPERPOWERS_DATA_DIR": custom}, clear=False):
        os.environ.pop("CLAUDE_SUPERPOWERS_DATA_DIR", None)
        from superpowers.memory.store import MemoryStore
        store = MemoryStore()
        assert store.db_path == Path(custom) / "memory.db"


def test_vault_uses_data_dir(tmp_path):
    """Vault default paths should come from get_data_dir."""
    custom = str(tmp_path / "vault-test")
    with mock.patch.dict(os.environ, {"SUPERPOWERS_DATA_DIR": custom}, clear=False):
        os.environ.pop("CLAUDE_SUPERPOWERS_DATA_DIR", None)
        from superpowers.vault import Vault
        v = Vault()
        assert v.vault_path == Path(custom) / "vault.enc"
        assert v.identity_file == Path(custom) / "age-identity.txt"
