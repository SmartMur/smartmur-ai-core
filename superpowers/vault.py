"""Encrypted credential vault using age CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

AGE_BIN = shutil.which("age") or "age"
AGE_KEYGEN_BIN = shutil.which("age-keygen") or "age-keygen"

def _default_vault_dir() -> Path:
    from superpowers.config import get_data_dir
    return get_data_dir()

KEYCHAIN_SERVICE = "claude-superpowers-vault"
KEYCHAIN_ACCOUNT = "age-identity"


class VaultError(Exception):
    pass


class Vault:
    def __init__(
        self,
        vault_path: str | Path | None = None,
        identity_file: str | Path | None = None,
    ):
        dd = _default_vault_dir()
        self.vault_path = Path(vault_path) if vault_path else dd / "vault.enc"
        self.identity_file = Path(identity_file) if identity_file else dd / "age-identity.txt"
        self._pubkey: str | None = None

    @property
    def pubkey(self) -> str:
        if self._pubkey is None:
            self._pubkey = self._read_pubkey()
        return self._pubkey

    def _read_pubkey(self) -> str:
        if not self.identity_file.exists():
            raise VaultError(f"Identity file not found: {self.identity_file}. Run `claw vault init`.")
        text = self.identity_file.read_text()
        for line in text.splitlines():
            if line.startswith("# public key:"):
                return line.split(":", 1)[1].strip()
        raise VaultError("Could not parse public key from identity file.")

    def init(self) -> str:
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self.identity_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.identity_file.exists():
            result = subprocess.run(
                [AGE_KEYGEN_BIN],
                capture_output=True,
                text=True,
                check=True,
            )
            self.identity_file.write_text(result.stdout)
            self.identity_file.chmod(0o600)

        self._pubkey = self._read_pubkey()

        # Store identity path in macOS Keychain (best-effort)
        self._store_keychain()

        if not self.vault_path.exists():
            self._encrypt({})

        return self.pubkey

    def _store_keychain(self):
        try:
            # Delete existing entry first (ignore errors if not present)
            subprocess.run(
                [
                    "security",
                    "delete-generic-password",
                    "-s", KEYCHAIN_SERVICE,
                    "-a", KEYCHAIN_ACCOUNT,
                ],
                capture_output=True,
            )
            subprocess.run(
                [
                    "security",
                    "add-generic-password",
                    "-s", KEYCHAIN_SERVICE,
                    "-a", KEYCHAIN_ACCOUNT,
                    "-w", str(self.identity_file),
                    "-U",
                ],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # non-macOS or keychain unavailable

    def _decrypt(self) -> dict:
        if not self.vault_path.exists():
            return {}

        # Empty file means empty vault
        if self.vault_path.stat().st_size == 0:
            return {}

        result = subprocess.run(
            [AGE_BIN, "-d", "-i", str(self.identity_file)],
            input=self.vault_path.read_bytes(),
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            raise VaultError(f"Decryption failed: {stderr}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise VaultError(f"Vault data corrupted: {exc}") from exc

    def _encrypt(self, data: dict):
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2).encode()

        result = subprocess.run(
            [AGE_BIN, "-r", self.pubkey],
            input=payload,
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            raise VaultError(f"Encryption failed: {stderr}")

        # Atomic write: write to tmp then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=self.vault_path.parent,
            prefix=".vault-",
            suffix=".tmp",
        )
        try:
            os.write(fd, result.stdout)
            os.close(fd)
            os.replace(tmp_path, self.vault_path)
        except BaseException:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        self.vault_path.chmod(0o600)

    def get(self, key: str) -> str | None:
        data = self._decrypt()
        return data.get(key)

    def set(self, key: str, value: str):
        data = self._decrypt()
        data[key] = value
        self._encrypt(data)

    def delete(self, key: str):
        data = self._decrypt()
        if key not in data:
            raise VaultError(f"Key not found: {key}")
        del data[key]
        self._encrypt(data)

    def list_keys(self) -> list[str]:
        data = self._decrypt()
        return sorted(data.keys())

    def export_env(self, keys: list[str] | None = None) -> dict[str, str]:
        data = self._decrypt()
        if keys is None:
            return dict(data)
        return {k: data[k] for k in keys if k in data}
