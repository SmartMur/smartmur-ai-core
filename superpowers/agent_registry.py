"""Agent Registry — discover and recommend subagents from agent.md files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SUBAGENTS_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "subagents"


@dataclass
class AgentManifest:
    """Parsed agent definition from an agent.md file."""

    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    path: Path = field(default_factory=lambda: Path("."))


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a markdown file.

    Expects the file to start with ``---`` followed by YAML content
    and closed by another ``---``.  Returns an empty dict if no
    frontmatter is found or parsing fails.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, ValueError):
        return {}


def _parse_body(text: str) -> str:
    """Extract the markdown body (everything after frontmatter)."""
    match = re.match(r"^---\s*\n.*?\n---\s*\n?(.*)", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _parse_agent_md(agent_md: Path) -> AgentManifest:
    """Parse an agent.md file into an AgentManifest."""
    text = agent_md.read_text()
    data = _parse_frontmatter(text)

    if not data.get("name"):
        raise ValueError(f"agent.md missing required 'name' field: {agent_md}")

    return AgentManifest(
        name=data["name"],
        description=data.get("description", ""),
        tags=[str(t) for t in data.get("tags", [])],
        skills=[str(s) for s in data.get("skills", [])],
        triggers=[str(t) for t in data.get("triggers", [])],
        path=agent_md,
    )


def get_agent_body(agent_md: Path) -> str:
    """Return the system-prompt body of an agent.md file."""
    return _parse_body(agent_md.read_text())


class AgentRegistry:
    """Discovers and manages subagent definitions."""

    def __init__(self, subagents_dir: Path | str | None = None):
        self.subagents_dir = Path(subagents_dir) if subagents_dir else SUBAGENTS_DIR_DEFAULT
        self._cache: dict[str, AgentManifest] = {}

    def discover(self) -> list[AgentManifest]:
        """Scan the subagents directory for agent.md files.

        Returns a list of all successfully parsed agent manifests.
        Populates the internal cache.
        """
        self._cache.clear()
        agents: list[AgentManifest] = []

        if not self.subagents_dir.exists():
            return agents

        for agent_md in sorted(self.subagents_dir.rglob("agent.md")):
            # Only pick up direct children: subagents/<name>/agent.md
            if agent_md.parent.parent != self.subagents_dir:
                continue
            # Skip directories prefixed with _
            if agent_md.parent.name.startswith("_"):
                continue
            try:
                manifest = _parse_agent_md(agent_md)
                self._cache[manifest.name] = manifest
                agents.append(manifest)
            except (yaml.YAMLError, OSError, KeyError, ValueError):
                continue

        return agents

    def list(self) -> list[AgentManifest]:
        """Return all discovered agents (runs discover if cache is empty)."""
        if not self._cache:
            self.discover()
        return list(self._cache.values())

    def get(self, name: str) -> AgentManifest:
        """Get a specific agent by name. Raises KeyError if not found."""
        if not self._cache:
            self.discover()
        if name not in self._cache:
            raise KeyError(f"Agent not found: {name}")
        return self._cache[name]

    def recommend(self, task_description: str) -> list[tuple[AgentManifest, int]]:
        """Rank agents by relevance to a task description.

        Returns a list of (AgentManifest, score) tuples sorted by score
        descending.  Score is the count of matching keywords found in the
        agent's tags and triggers.  Agents with zero matches are excluded.
        """
        if not self._cache:
            self.discover()

        task_lower = task_description.lower()
        task_words = set(re.findall(r"[a-z0-9]+", task_lower))

        scored: list[tuple[AgentManifest, int]] = []

        for agent in self._cache.values():
            score = 0
            keywords = [t.lower() for t in agent.tags + agent.triggers]
            for kw in keywords:
                # Check if the keyword appears in the task text
                if kw in task_lower:
                    score += 1
                # Also check if any task word matches a keyword
                elif kw in task_words:
                    score += 1
            if score > 0:
                scored.append((agent, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def names(self) -> list[str]:
        """Return names of all discovered agents."""
        if not self._cache:
            self.discover()
        return list(self._cache.keys())
