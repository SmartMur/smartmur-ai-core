"""Intelligent agent routing — detect tech stacks and auto-select agents for tasks.

Combines file-system tech-stack detection with keyword-based agent matching
to recommend the best subagent(s) for any given task.  Designed to be called
from the job runner (``agent: auto``) and from the dashboard recommendation API.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from superpowers.agent_registry import AgentManifest, AgentRegistry

# ---------------------------------------------------------------------------
# Language detection by file extension
# ---------------------------------------------------------------------------

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyx": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".swift": "swift",
    ".php": "php",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".pl": "perl",
    ".pm": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".dart": "dart",
    ".vue": "vue",
    ".svelte": "svelte",
}

# Framework detection — config file -> framework name
_FRAMEWORK_SIGNALS: dict[str, str] = {
    "package.json": "node",
    "pyproject.toml": "python-packaging",
    "setup.py": "python-packaging",
    "setup.cfg": "python-packaging",
    "Cargo.toml": "rust-cargo",
    "go.mod": "go-modules",
    "Gemfile": "ruby-bundler",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "composer.json": "php-composer",
    "mix.exs": "elixir-mix",
    "pubspec.yaml": "dart-pub",
    "requirements.txt": "pip",
    "Pipfile": "pipenv",
    "poetry.lock": "poetry",
    "next.config.js": "nextjs",
    "next.config.mjs": "nextjs",
    "next.config.ts": "nextjs",
    "nuxt.config.js": "nuxtjs",
    "nuxt.config.ts": "nuxtjs",
    "angular.json": "angular",
    "svelte.config.js": "sveltekit",
    "vite.config.ts": "vite",
    "vite.config.js": "vite",
    "webpack.config.js": "webpack",
    "tsconfig.json": "typescript",
    "tailwind.config.js": "tailwind",
    "tailwind.config.ts": "tailwind",
    ".eslintrc.json": "eslint",
    ".eslintrc.js": "eslint",
    "jest.config.js": "jest",
    "jest.config.ts": "jest",
    "pytest.ini": "pytest",
    "conftest.py": "pytest",
    ".flake8": "flake8",
    "ruff.toml": "ruff",
}

# Tool/infra detection
_TOOL_SIGNALS: dict[str, str] = {
    "Dockerfile": "docker",
    "docker-compose.yaml": "docker-compose",
    "docker-compose.yml": "docker-compose",
    "compose.yaml": "docker-compose",
    "compose.yml": "docker-compose",
    ".dockerignore": "docker",
    "Makefile": "make",
    "CMakeLists.txt": "cmake",
    "Jenkinsfile": "jenkins",
    ".github/workflows": "github-actions",
    ".gitlab-ci.yml": "gitlab-ci",
    ".circleci/config.yml": "circleci",
    "terraform.tf": "terraform",
    "main.tf": "terraform",
    "ansible.cfg": "ansible",
    "playbook.yml": "ansible",
    "Chart.yaml": "helm",
    "helmfile.yaml": "helm",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "kustomization.yaml": "kubernetes",
    "skaffold.yaml": "skaffold",
    "Vagrantfile": "vagrant",
    "Procfile": "heroku",
    "fly.toml": "fly-io",
    "vercel.json": "vercel",
    "netlify.toml": "netlify",
    ".env": "dotenv",
    ".env.example": "dotenv",
    "redis.conf": "redis",
    "nginx.conf": "nginx",
}

# Directories to always skip when scanning
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        "vendor",
        "bower_components",
        ".eggs",
    }
)

# Max files to scan (avoid huge repos)
_MAX_FILES = 5000

# ---------------------------------------------------------------------------
# Tech stack detection
# ---------------------------------------------------------------------------


@dataclass
class TechStack:
    """Detected technology profile for a repository."""

    languages: dict[str, int] = field(default_factory=dict)
    frameworks: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    primary_language: str = ""

    def all_keywords(self) -> set[str]:
        """Return all tech keywords for matching against agent tags."""
        kw: set[str] = set()
        for lang in self.languages:
            kw.add(lang)
        for fw in self.frameworks:
            kw.add(fw)
            # Also add base names (e.g., "python-packaging" -> "python")
            if "-" in fw:
                kw.add(fw.split("-")[0])
        for tool in self.tools:
            kw.add(tool)
            if "-" in tool:
                kw.add(tool.split("-")[0])
        if self.primary_language:
            kw.add(self.primary_language)
        return kw


def detect_tech_stack(repo_path: str | Path) -> TechStack:
    """Scan a repository path and detect languages, frameworks, and tools.

    Walks the file tree (skipping common vendor/build directories) and
    counts file extensions for language detection, checks for config files
    for framework detection, and checks for tool-specific files.

    Parameters
    ----------
    repo_path:
        Root directory of the repository to scan.

    Returns
    -------
    TechStack:
        Detected technologies with language file counts, framework list,
        tool list, and the primary (most common) language.
    """
    root = Path(repo_path)
    if not root.is_dir():
        return TechStack()

    lang_counts: Counter[str] = Counter()
    frameworks: set[str] = set()
    tools: set[str] = set()
    files_scanned = 0

    # Check top-level config files for frameworks and tools
    for config_file, framework in _FRAMEWORK_SIGNALS.items():
        if (root / config_file).exists():
            frameworks.add(framework)

    for tool_file, tool in _TOOL_SIGNALS.items():
        target = root / tool_file
        if target.exists():
            tools.add(tool)

    # Walk the tree for language detection
    try:
        for item in _walk_files(root):
            if files_scanned >= _MAX_FILES:
                break
            files_scanned += 1

            suffix = item.suffix.lower() if item.suffix != ".R" else item.suffix
            lang = _EXTENSION_MAP.get(suffix)
            if lang:
                lang_counts[lang] += 1
    except (PermissionError, OSError):
        pass

    primary = lang_counts.most_common(1)[0][0] if lang_counts else ""

    return TechStack(
        languages=dict(lang_counts.most_common()),
        frameworks=sorted(frameworks),
        tools=sorted(tools),
        primary_language=primary,
    )


def _walk_files(root: Path):
    """Yield files under *root*, skipping vendor/build directories."""
    try:
        entries = sorted(root.iterdir())
    except (PermissionError, OSError):
        return

    for entry in entries:
        if entry.is_dir():
            if entry.name in _SKIP_DIRS:
                continue
            yield from _walk_files(entry)
        elif entry.is_file():
            yield entry


# ---------------------------------------------------------------------------
# Agent selection
# ---------------------------------------------------------------------------

# Task keyword -> agent tag boost mapping
_TASK_KEYWORD_BOOSTS: dict[str, list[str]] = {
    "review": ["code-reviewer", "code", "review"],
    "refactor": ["code-reviewer", "code", "refactor"],
    "test": ["test-writer", "testing", "test"],
    "coverage": ["test-writer", "coverage"],
    "deploy": ["devops-engineer", "deploy", "docker"],
    "docker": ["devops-engineer", "docker", "container"],
    "ci": ["devops-engineer", "ci", "pipeline"],
    "pipeline": ["devops-engineer", "ci", "pipeline"],
    "infrastructure": ["devops-engineer", "infrastructure"],
    "kubernetes": ["devops-engineer", "kubernetes"],
    "k8s": ["devops-engineer", "kubernetes"],
    "helm": ["devops-engineer", "kubernetes"],
    "docs": ["docs-writer", "documentation"],
    "documentation": ["docs-writer", "documentation"],
    "readme": ["docs-writer", "readme"],
    "guide": ["docs-writer", "guide"],
    "security": ["security-auditor", "security", "audit"],
    "audit": ["security-auditor", "audit"],
    "vulnerability": ["security-auditor", "vulnerability"],
    "scan": ["security-auditor", "scan"],
    "lint": ["code-reviewer", "lint", "quality"],
    "quality": ["code-reviewer", "quality"],
}

# Tech stack -> agent relevance boosts
_TECH_AGENT_MAP: dict[str, list[str]] = {
    "python": ["code-reviewer", "test-writer", "security-auditor"],
    "javascript": ["code-reviewer", "test-writer", "security-auditor"],
    "typescript": ["code-reviewer", "test-writer", "security-auditor"],
    "go": ["code-reviewer", "test-writer", "security-auditor"],
    "rust": ["code-reviewer", "test-writer", "security-auditor"],
    "docker": ["devops-engineer"],
    "docker-compose": ["devops-engineer"],
    "github-actions": ["devops-engineer", "security-auditor"],
    "kubernetes": ["devops-engineer"],
    "helm": ["devops-engineer"],
    "terraform": ["devops-engineer"],
    "ansible": ["devops-engineer"],
    "pytest": ["test-writer"],
    "jest": ["test-writer"],
    "ruff": ["code-reviewer"],
    "eslint": ["code-reviewer"],
    "flake8": ["code-reviewer"],
}


@dataclass
class AgentSelection:
    """A recommended agent with relevance score and reasoning."""

    agent: AgentManifest
    score: float
    reasons: list[str] = field(default_factory=list)


def select_agents(
    task_description: str,
    repo_path: str | Path | None = None,
    registry: AgentRegistry | None = None,
    top_n: int = 5,
) -> list[AgentSelection]:
    """Recommend the best agent(s) for a task, optionally boosted by repo tech stack.

    Combines ``AgentRegistry.recommend()`` keyword scores with tech-stack
    relevance signals and task-keyword boosts to produce a ranked list.

    Parameters
    ----------
    task_description:
        Natural-language description of the task.
    repo_path:
        Optional path to a repository to scan for tech-stack signals.
    registry:
        Optional pre-configured ``AgentRegistry``.  A default one is
        created if not provided.
    top_n:
        Maximum number of agent recommendations to return.

    Returns
    -------
    list[AgentSelection]:
        Agents ranked by score (descending), with human-readable reasons.
    """
    if registry is None:
        registry = AgentRegistry()

    # Ensure agents are discovered
    agents = registry.list()
    if not agents:
        return []

    # Base scores from registry keyword matching
    base_scores = registry.recommend(task_description)
    score_map: dict[str, float] = {}
    for agent, score in base_scores:
        score_map[agent.name] = float(score)

    # Ensure all agents have an entry (even if zero base score)
    for agent in agents:
        if agent.name not in score_map:
            score_map[agent.name] = 0.0

    reasons_map: dict[str, list[str]] = {a.name: [] for a in agents}

    # Record base keyword matches
    for agent, score in base_scores:
        if score > 0:
            reasons_map[agent.name].append(f"keyword match (base score: {score})")

    # Task keyword boosts
    task_lower = task_description.lower()
    task_words = set(re.findall(r"[a-z0-9]+", task_lower))

    for keyword, boost_targets in _TASK_KEYWORD_BOOSTS.items():
        if keyword in task_words or keyword in task_lower:
            for target in boost_targets:
                # Check if target is an agent name
                if target in score_map:
                    score_map[target] += 2.0
                    reasons_map[target].append(f"task keyword '{keyword}' boost")

    # Tech stack boosts
    tech_stack: TechStack | None = None
    if repo_path:
        tech_stack = detect_tech_stack(repo_path)
        tech_keywords = tech_stack.all_keywords()

        for tech_kw in tech_keywords:
            agent_names = _TECH_AGENT_MAP.get(tech_kw, [])
            for agent_name in agent_names:
                if agent_name in score_map:
                    score_map[agent_name] += 1.5
                    reasons_map[agent_name].append(f"tech stack signal: {tech_kw}")

        # Primary language extra boost
        if tech_stack.primary_language:
            lang_agents = _TECH_AGENT_MAP.get(tech_stack.primary_language, [])
            for agent_name in lang_agents:
                if agent_name in score_map:
                    score_map[agent_name] += 1.0
                    reasons_map[agent_name].append(
                        f"primary language: {tech_stack.primary_language}"
                    )

    # Build selections, filter out zero-score agents
    agent_lookup = {a.name: a for a in agents}
    selections: list[AgentSelection] = []

    for name, score in score_map.items():
        if score > 0 and name in agent_lookup:
            # Deduplicate reasons
            unique_reasons = list(dict.fromkeys(reasons_map.get(name, [])))
            selections.append(
                AgentSelection(
                    agent=agent_lookup[name],
                    score=score,
                    reasons=unique_reasons,
                )
            )

    # Sort by score descending, then by name for stability
    selections.sort(key=lambda s: (-s.score, s.agent.name))

    return selections[:top_n]
