from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def vault_list_keys() -> str:
        """List stored credential key names in the vault. Does NOT expose secret values."""
        try:
            from superpowers.vault import Vault

            vault = Vault()
            keys = vault.list_keys()
            if not keys:
                return "Vault is empty — no keys stored."
            return f"{len(keys)} key(s) in vault:\n" + "\n".join(f"  - {k}" for k in keys)
        except Exception as exc:
            return f"Error listing vault keys: {exc}"

    @mcp.tool()
    def vault_status() -> str:
        """Check if the encrypted vault is initialized and accessible."""
        try:
            from superpowers.vault import Vault

            vault = Vault()

            if not vault.identity_file.exists():
                return "Vault not initialized. Run `claw vault init` to create identity and vault file."

            if not vault.vault_path.exists():
                return f"Identity file exists at {vault.identity_file}, but vault file is missing at {vault.vault_path}. Run `claw vault init`."

            keys = vault.list_keys()
            return (
                f"Vault is initialized and accessible.\n"
                f"  Identity: {vault.identity_file}\n"
                f"  Vault: {vault.vault_path}\n"
                f"  Keys stored: {len(keys)}"
            )
        except Exception as exc:
            return f"Vault error: {exc}"
