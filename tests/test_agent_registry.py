"""Tests for the agent registry and CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from superpowers.agent_registry import (
    AgentManifest,
    AgentRegistry,
    _parse_body,
    _parse_frontmatter,
    get_agent_body,
)
from superpowers.cli_agent import agent_group

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_FRONTMATTER = {
    "name": "test-agent",
    "description": "A test agent for unit tests",
    "tags": ["test", "debug"],
    "skills": ["qa-guardian"],
    "triggers": ["test", "debug", "check"],
}


def _make_agent(parent: Path, name: str = "test-agent", **overrides) -> Path:
    """Create a minimal agent.md inside parent/<name>/."""
    agent_dir = parent / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    data = {**SAMPLE_FRONTMATTER, "name": name, **overrides}
    content = f"---\n{yaml.dump(data, default_flow_style=False)}---\n\nYou are the {name} agent.\n"
    (agent_dir / "agent.md").write_text(content)
    return agent_dir


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        text = "---\nname: foo\ndescription: bar\n---\nBody text."
        result = _parse_frontmatter(text)
        assert result["name"] == "foo"
        assert result["description"] == "bar"

    def test_no_frontmatter(self):
        text = "Just some markdown text."
        result = _parse_frontmatter(text)
        assert result == {}

    def test_invalid_yaml_frontmatter(self):
        text = "---\n: : : invalid\n---\nBody."
        result = _parse_frontmatter(text)
        # Should return empty dict on parse error
        assert isinstance(result, dict)

    def test_non_dict_frontmatter(self):
        text = "---\n- item1\n- item2\n---\nBody."
        result = _parse_frontmatter(text)
        assert result == {}

    def test_frontmatter_with_lists(self):
        text = "---\nname: x\ntags:\n  - a\n  - b\n---\nBody."
        result = _parse_frontmatter(text)
        assert result["tags"] == ["a", "b"]


class TestParseBody:
    def test_body_after_frontmatter(self):
        text = "---\nname: x\n---\n\nHello world."
        assert _parse_body(text) == "Hello world."

    def test_body_without_frontmatter(self):
        text = "Just plain text."
        assert _parse_body(text) == "Just plain text."

    def test_empty_body(self):
        text = "---\nname: x\n---\n"
        assert _parse_body(text) == ""

    def test_multiline_body(self):
        text = "---\nname: x\n---\n\nLine one.\nLine two.\nLine three."
        body = _parse_body(text)
        assert "Line one." in body
        assert "Line three." in body


# ---------------------------------------------------------------------------
# AgentRegistry.discover
# ---------------------------------------------------------------------------


class TestDiscover:
    def test_discovers_agents(self, tmp_path):
        _make_agent(tmp_path, "alpha")
        _make_agent(tmp_path, "beta")
        registry = AgentRegistry(subagents_dir=tmp_path)
        agents = registry.discover()
        names = [a.name for a in agents]
        assert "alpha" in names
        assert "beta" in names
        assert len(agents) == 2

    def test_empty_directory(self, tmp_path):
        registry = AgentRegistry(subagents_dir=tmp_path)
        agents = registry.discover()
        assert agents == []

    def test_nonexistent_directory(self, tmp_path):
        registry = AgentRegistry(subagents_dir=tmp_path / "nonexistent")
        agents = registry.discover()
        assert agents == []

    def test_skips_underscore_prefixed_dirs(self, tmp_path):
        _make_agent(tmp_path, "_internal")
        _make_agent(tmp_path, "visible")
        registry = AgentRegistry(subagents_dir=tmp_path)
        agents = registry.discover()
        names = [a.name for a in agents]
        assert "_internal" not in names
        assert "visible" in names

    def test_skips_nested_agents(self, tmp_path):
        _make_agent(tmp_path, "top-level")
        # Create a deeply nested agent.md
        nested = tmp_path / "top-level" / "sub" / "deep"
        nested.mkdir(parents=True)
        (nested / "agent.md").write_text("---\nname: deep\n---\nNested.")
        registry = AgentRegistry(subagents_dir=tmp_path)
        agents = registry.discover()
        names = [a.name for a in agents]
        assert "deep" not in names
        assert "top-level" in names

    def test_skips_invalid_agent_md(self, tmp_path):
        # Create an agent.md with no name field
        bad_dir = tmp_path / "bad-agent"
        bad_dir.mkdir()
        (bad_dir / "agent.md").write_text("---\ndescription: no name\n---\nBody.")
        _make_agent(tmp_path, "good-agent")
        registry = AgentRegistry(subagents_dir=tmp_path)
        agents = registry.discover()
        names = [a.name for a in agents]
        assert "good-agent" in names
        assert len(agents) == 1

    def test_skips_corrupt_yaml(self, tmp_path):
        bad_dir = tmp_path / "corrupt"
        bad_dir.mkdir()
        (bad_dir / "agent.md").write_text("---\n\x00\x01\x02\n---\nBody.")
        registry = AgentRegistry(subagents_dir=tmp_path)
        agents = registry.discover()
        assert agents == []

    def test_discover_clears_cache(self, tmp_path):
        _make_agent(tmp_path, "agent-a")
        registry = AgentRegistry(subagents_dir=tmp_path)
        registry.discover()
        assert "agent-a" in registry._cache
        # Remove agent-a, add agent-b
        import shutil

        shutil.rmtree(tmp_path / "agent-a")
        _make_agent(tmp_path, "agent-b")
        registry.discover()
        assert "agent-a" not in registry._cache
        assert "agent-b" in registry._cache


# ---------------------------------------------------------------------------
# AgentRegistry.get / list / names
# ---------------------------------------------------------------------------


class TestGetListNames:
    def test_get_existing(self, tmp_path):
        _make_agent(tmp_path, "my-agent")
        registry = AgentRegistry(subagents_dir=tmp_path)
        registry.discover()
        agent = registry.get("my-agent")
        assert agent.name == "my-agent"
        assert agent.description == "A test agent for unit tests"

    def test_get_missing_raises_keyerror(self, tmp_path):
        _make_agent(tmp_path, "exists")
        registry = AgentRegistry(subagents_dir=tmp_path)
        registry.discover()
        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent")

    def test_get_auto_discovers(self, tmp_path):
        _make_agent(tmp_path, "auto")
        registry = AgentRegistry(subagents_dir=tmp_path)
        # Don't call discover() first
        agent = registry.get("auto")
        assert agent.name == "auto"

    def test_list_returns_all(self, tmp_path):
        _make_agent(tmp_path, "a")
        _make_agent(tmp_path, "b")
        _make_agent(tmp_path, "c")
        registry = AgentRegistry(subagents_dir=tmp_path)
        agents = registry.list()
        assert len(agents) == 3

    def test_names_returns_all_names(self, tmp_path):
        _make_agent(tmp_path, "x")
        _make_agent(tmp_path, "y")
        registry = AgentRegistry(subagents_dir=tmp_path)
        names = registry.names()
        assert set(names) == {"x", "y"}


# ---------------------------------------------------------------------------
# AgentRegistry.recommend
# ---------------------------------------------------------------------------


class TestRecommend:
    def test_recommend_matches_tags(self, tmp_path):
        _make_agent(tmp_path, "security-auditor", tags=["security", "audit"], triggers=["security"])
        _make_agent(tmp_path, "docs-writer", tags=["docs", "documentation"], triggers=["docs"])
        registry = AgentRegistry(subagents_dir=tmp_path)
        results = registry.recommend("run a security audit on the codebase")
        assert len(results) >= 1
        assert results[0][0].name == "security-auditor"
        assert results[0][1] > 0

    def test_recommend_matches_triggers(self, tmp_path):
        _make_agent(tmp_path, "test-writer", tags=["test"], triggers=["test", "coverage", "pytest"])
        _make_agent(tmp_path, "docs-writer", tags=["docs"], triggers=["docs"])
        registry = AgentRegistry(subagents_dir=tmp_path)
        results = registry.recommend("write tests and check coverage")
        agent_names = [r[0].name for r in results]
        assert "test-writer" in agent_names

    def test_recommend_ranking_order(self, tmp_path):
        _make_agent(tmp_path, "security", tags=["security"], triggers=["security", "scan"])
        _make_agent(tmp_path, "generic", tags=["general"], triggers=["scan"])
        registry = AgentRegistry(subagents_dir=tmp_path)
        results = registry.recommend("security scan of the system")
        # security agent should rank higher (more keyword matches)
        assert results[0][0].name == "security"
        assert results[0][1] > results[1][1]

    def test_recommend_no_matches(self, tmp_path):
        _make_agent(tmp_path, "security", tags=["security"], triggers=["audit"])
        registry = AgentRegistry(subagents_dir=tmp_path)
        results = registry.recommend("bake a chocolate cake")
        assert results == []

    def test_recommend_case_insensitive(self, tmp_path):
        _make_agent(tmp_path, "devops", tags=["Docker", "CI"], triggers=["Deploy"])
        registry = AgentRegistry(subagents_dir=tmp_path)
        results = registry.recommend("docker deploy pipeline")
        assert len(results) == 1
        assert results[0][0].name == "devops"

    def test_recommend_auto_discovers(self, tmp_path):
        _make_agent(tmp_path, "agent1", tags=["alpha"], triggers=["alpha"])
        registry = AgentRegistry(subagents_dir=tmp_path)
        # Don't call discover() first
        results = registry.recommend("alpha task")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# AgentManifest dataclass
# ---------------------------------------------------------------------------


class TestAgentManifest:
    def test_defaults(self):
        m = AgentManifest(name="test", description="desc")
        assert m.tags == []
        assert m.skills == []
        assert m.triggers == []
        assert m.path == Path(".")

    def test_all_fields(self, tmp_path):
        p = tmp_path / "agent.md"
        m = AgentManifest(
            name="full",
            description="Full agent",
            tags=["a", "b"],
            skills=["s1"],
            triggers=["t1", "t2"],
            path=p,
        )
        assert m.name == "full"
        assert m.tags == ["a", "b"]
        assert m.skills == ["s1"]
        assert m.triggers == ["t1", "t2"]
        assert m.path == p


# ---------------------------------------------------------------------------
# get_agent_body
# ---------------------------------------------------------------------------


class TestGetAgentBody:
    def test_returns_body(self, tmp_path):
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        agent_md = agent_dir / "agent.md"
        agent_md.write_text("---\nname: x\n---\n\nSystem prompt body here.")
        body = get_agent_body(agent_md)
        assert body == "System prompt body here."

    def test_returns_full_text_without_frontmatter(self, tmp_path):
        agent_md = tmp_path / "agent.md"
        agent_md.write_text("No frontmatter, just text.")
        body = get_agent_body(agent_md)
        assert body == "No frontmatter, just text."


# ---------------------------------------------------------------------------
# Real subagents discovery (integration-ish)
# ---------------------------------------------------------------------------


class TestRealSubagents:
    """Test against the actual subagents/ directory in the repo."""

    def test_discovers_repo_agents(self):
        repo_dir = Path(__file__).resolve().parent.parent / "subagents"
        if not repo_dir.exists():
            pytest.skip("subagents/ directory not present")
        registry = AgentRegistry(subagents_dir=repo_dir)
        agents = registry.discover()
        names = [a.name for a in agents]
        assert "security-auditor" in names
        assert "code-reviewer" in names
        assert "devops-engineer" in names
        assert "test-writer" in names
        assert "docs-writer" in names
        assert len(agents) >= 5

    def test_all_agents_have_descriptions(self):
        repo_dir = Path(__file__).resolve().parent.parent / "subagents"
        if not repo_dir.exists():
            pytest.skip("subagents/ directory not present")
        registry = AgentRegistry(subagents_dir=repo_dir)
        for agent in registry.discover():
            assert agent.description, f"Agent '{agent.name}' has no description"

    def test_all_agents_have_tags(self):
        repo_dir = Path(__file__).resolve().parent.parent / "subagents"
        if not repo_dir.exists():
            pytest.skip("subagents/ directory not present")
        registry = AgentRegistry(subagents_dir=repo_dir)
        for agent in registry.discover():
            assert len(agent.tags) > 0, f"Agent '{agent.name}' has no tags"


# ---------------------------------------------------------------------------
# CLI: agent list
# ---------------------------------------------------------------------------


class TestCLIAgentList:
    @patch("superpowers.cli_agent._registry")
    def test_list_with_agents(self, mock_registry_fn):
        registry = MagicMock()
        registry.discover.return_value = [
            AgentManifest(
                name="sec",
                description="Security auditor",
                tags=["security"],
                skills=["qa-guardian"],
            ),
            AgentManifest(
                name="docs",
                description="Documentation writer",
                tags=["docs"],
            ),
        ]
        mock_registry_fn.return_value = registry
        runner = CliRunner()
        result = runner.invoke(agent_group, ["list"])
        assert result.exit_code == 0
        assert "sec" in result.output
        assert "docs" in result.output

    @patch("superpowers.cli_agent._registry")
    def test_list_empty(self, mock_registry_fn):
        registry = MagicMock()
        registry.discover.return_value = []
        mock_registry_fn.return_value = registry
        runner = CliRunner()
        result = runner.invoke(agent_group, ["list"])
        assert result.exit_code == 0
        assert "No agents found" in result.output


# ---------------------------------------------------------------------------
# CLI: agent info
# ---------------------------------------------------------------------------


class TestCLIAgentInfo:
    @patch("superpowers.cli_agent._registry")
    def test_info_existing_agent(self, mock_registry_fn):
        registry = MagicMock()
        registry.get.return_value = AgentManifest(
            name="sec",
            description="Security auditor",
            tags=["security", "audit"],
            skills=["qa-guardian"],
            triggers=["security", "scan"],
            path=Path("/tmp/sec/agent.md"),
        )
        mock_registry_fn.return_value = registry
        runner = CliRunner()
        result = runner.invoke(agent_group, ["info", "sec"])
        assert result.exit_code == 0
        assert "sec" in result.output
        assert "Security auditor" in result.output

    @patch("superpowers.cli_agent._registry")
    def test_info_missing_agent(self, mock_registry_fn):
        registry = MagicMock()
        registry.get.side_effect = KeyError("Agent not found: nope")
        mock_registry_fn.return_value = registry
        runner = CliRunner()
        result = runner.invoke(agent_group, ["info", "nope"])
        assert result.exit_code != 0
        assert "not found" in result.output


# ---------------------------------------------------------------------------
# CLI: agent recommend
# ---------------------------------------------------------------------------


class TestCLIAgentRecommend:
    @patch("superpowers.cli_agent._registry")
    def test_recommend_with_matches(self, mock_registry_fn):
        sec = AgentManifest(name="sec", description="Security scanner", tags=["security"])
        registry = MagicMock()
        registry.recommend.return_value = [(sec, 3)]
        mock_registry_fn.return_value = registry
        runner = CliRunner()
        result = runner.invoke(agent_group, ["recommend", "security scan"])
        assert result.exit_code == 0
        assert "sec" in result.output
        assert "3" in result.output

    @patch("superpowers.cli_agent._registry")
    def test_recommend_no_matches(self, mock_registry_fn):
        registry = MagicMock()
        registry.recommend.return_value = []
        mock_registry_fn.return_value = registry
        runner = CliRunner()
        result = runner.invoke(agent_group, ["recommend", "bake a cake"])
        assert result.exit_code == 0
        assert "No matching agents" in result.output


# ---------------------------------------------------------------------------
# CLI: agent run
# ---------------------------------------------------------------------------


class TestCLIAgentRun:
    @patch("superpowers.cli_agent._registry")
    def test_run_missing_agent(self, mock_registry_fn):
        registry = MagicMock()
        registry.get.side_effect = KeyError("Agent not found: nope")
        mock_registry_fn.return_value = registry
        runner = CliRunner()
        result = runner.invoke(agent_group, ["run", "nope"])
        assert result.exit_code != 0
        assert "not found" in result.output

    @patch("superpowers.cli_agent.get_default_provider")
    @patch("superpowers.cli_agent.get_agent_body", return_value="Agent body.")
    @patch("superpowers.cli_agent._registry")
    def test_run_no_claude_binary(self, mock_registry_fn, mock_body, mock_provider_fn):
        registry = MagicMock()
        registry.get.return_value = AgentManifest(
            name="sec", description="x", path=Path("/tmp/sec/agent.md")
        )
        mock_registry_fn.return_value = registry
        provider = MagicMock()
        provider.available.return_value = False
        mock_provider_fn.return_value = provider
        runner = CliRunner()
        result = runner.invoke(agent_group, ["run", "sec"])
        assert result.exit_code != 0
        assert "No LLM provider available" in result.output

    @patch("superpowers.cli_agent.get_default_provider")
    @patch("superpowers.cli_agent.get_agent_body", return_value="You are a security agent.")
    @patch("superpowers.cli_agent._registry")
    def test_run_success(self, mock_registry_fn, mock_body, mock_provider_fn):
        registry = MagicMock()
        registry.get.return_value = AgentManifest(
            name="sec", description="x", path=Path("/tmp/sec/agent.md")
        )
        mock_registry_fn.return_value = registry
        provider = MagicMock()
        provider.available.return_value = True
        provider.invoke.return_value = "Scan complete."
        mock_provider_fn.return_value = provider
        runner = CliRunner()
        result = runner.invoke(agent_group, ["run", "sec", "--task", "scan the code"])
        assert result.exit_code == 0
        assert "Scan complete." in result.output

    @patch("superpowers.cli_agent.get_default_provider")
    @patch("superpowers.cli_agent.get_agent_body", return_value="Agent body.")
    @patch("superpowers.cli_agent._registry")
    def test_run_nonzero_exit(self, mock_registry_fn, mock_body, mock_provider_fn):
        registry = MagicMock()
        registry.get.return_value = AgentManifest(
            name="sec", description="x", path=Path("/tmp/sec/agent.md")
        )
        mock_registry_fn.return_value = registry
        provider = MagicMock()
        provider.available.return_value = True
        provider.invoke.side_effect = RuntimeError("error occurred")
        mock_provider_fn.return_value = provider
        runner = CliRunner()
        result = runner.invoke(agent_group, ["run", "sec"])
        assert result.exit_code != 0
        assert "error occurred" in result.output
