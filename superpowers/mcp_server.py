"""MCP server exposing all Claude Superpowers as native Claude Code tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "claude-superpowers",
    instructions="Claw superpowers: messaging, SSH, browser, workflows, cron, skills, memory, vault, audit",
)

# Register all tool modules
from superpowers.mcp.channels_tools import register as reg_channels
from superpowers.mcp.ssh_tools import register as reg_ssh
from superpowers.mcp.memory_tools import register as reg_memory
from superpowers.mcp.browser_tools import register as reg_browser
from superpowers.mcp.workflow_tools import register as reg_workflow
from superpowers.mcp.cron_tools import register as reg_cron
from superpowers.mcp.skill_tools import register as reg_skills
from superpowers.mcp.audit_tools import register as reg_audit
from superpowers.mcp.vault_tools import register as reg_vault

reg_channels(mcp)
reg_ssh(mcp)
reg_memory(mcp)
reg_browser(mcp)
reg_workflow(mcp)
reg_cron(mcp)
reg_skills(mcp)
reg_audit(mcp)
reg_vault(mcp)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
