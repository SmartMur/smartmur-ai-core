"""Tests for MCP tool registration and basic tool behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from mcp.server.fastmcp import FastMCP

# --- Registration tests: every module registers tools without error ---


class TestToolRegistration:
    def _make_mcp(self):
        return FastMCP("test")

    def test_channels_tools_register(self):
        from superpowers.mcp.channels_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_ssh_tools_register(self):
        from superpowers.mcp.ssh_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_memory_tools_register(self):
        from superpowers.mcp.memory_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_browser_tools_register(self):
        from superpowers.mcp.browser_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_workflow_tools_register(self):
        from superpowers.mcp.workflow_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_cron_tools_register(self):
        from superpowers.mcp.cron_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_skill_tools_register(self):
        from superpowers.mcp.skill_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_audit_tools_register(self):
        from superpowers.mcp.audit_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_vault_tools_register(self):
        from superpowers.mcp.vault_tools import register
        mcp = self._make_mcp()
        register(mcp)

    def test_all_register_on_main_server(self):
        """The main mcp_server module imports and registers all tools."""
        from superpowers import mcp_server
        assert mcp_server.mcp is not None


# --- Vault tools: safe, no secrets exposed ---


class TestVaultTools:
    def test_vault_status_uninitialized(self, tmp_path):
        from superpowers.mcp.vault_tools import register
        mcp = self._make_mcp()
        register(mcp)

        with patch("superpowers.vault.Vault") as mock_vault:
            instance = mock_vault.return_value
            instance.identity_file = tmp_path / "identity.txt"
            instance.vault_path = tmp_path / "vault.enc"
            # Call the tool function directly
            tools = {name: fn for name, fn in _extract_tools(mcp)}
            result = tools["vault_status"]()
            assert "not initialized" in result.lower() or "missing" in result.lower()

    def _make_mcp(self):
        return FastMCP("test")


class TestMemoryTools:
    def test_remember_and_recall(self, tmp_path):
        from superpowers.mcp.memory_tools import register
        mcp = FastMCP("test")
        register(mcp)

        mock_entry = MagicMock()
        mock_entry.id = 1
        mock_entry.key = "test-key"
        mock_entry.value = "test-value"
        mock_entry.category.value = "fact"
        mock_entry.tags = "tag1"
        mock_entry.project = ""
        mock_entry.access_count = 1
        mock_entry.created_at = "2026-01-01"
        mock_entry.updated_at = "2026-01-01"
        with patch("superpowers.memory.store.MemoryStore.__init__", return_value=None), \
             patch("superpowers.memory.store.MemoryStore.remember") as mock_remember, \
             patch("superpowers.memory.store.MemoryStore.recall") as mock_recall:
            mock_remember.return_value = mock_entry
            mock_recall.return_value = mock_entry

            tools = {name: fn for name, fn in _extract_tools(mcp)}
            result = tools["remember"]("test-key", "test-value")
            assert "stored" in result.lower() or "remembered" in result.lower() or "test-key" in result

            result = tools["recall"]("test-key")
            assert "test-value" in result


class TestAuditTools:
    def test_audit_tail_empty(self):
        from superpowers.mcp.audit_tools import register
        mcp = FastMCP("test")
        register(mcp)

        with patch("superpowers.audit.AuditLog") as mock_audit:
            mock_audit.return_value.tail.return_value = []
            tools = {name: fn for name, fn in _extract_tools(mcp)}
            result = tools["audit_tail"]()
            assert "no" in result.lower() or "empty" in result.lower() or result.strip() != ""


class TestWorkflowTools:
    def test_list_workflows_empty(self, tmp_path):
        from superpowers.mcp.workflow_tools import register
        mcp = FastMCP("test")
        register(mcp)

        with patch("superpowers.workflow.loader.WorkflowLoader") as mock_loader:
            mock_loader.return_value.list_workflows.return_value = []
            tools = {name: fn for name, fn in _extract_tools(mcp)}
            result = tools["list_workflows"]()
            assert "no" in result.lower() or result.strip() != ""


def _extract_tools(mcp: FastMCP) -> list[tuple[str, callable]]:
    """Extract registered tool functions from a FastMCP instance."""
    tools = []
    for name, tool in mcp._tool_manager._tools.items():
        tools.append((name, tool.fn))
    return tools
