from __future__ import annotations

import re
from pathlib import Path

from superpowers.skill_creator import create_skill
from superpowers.skill_registry import SkillRegistry

# Built-in templates: name -> (description, script_type, tags, script_body)
BUILTIN_TEMPLATES: dict[str, dict] = {
    "network-scan": {
        "description": "Scan local network for active hosts using nmap or ping sweep",
        "script_type": "bash",
        "tags": ["network", "scan", "hosts", "nmap", "ping"],
        "script": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n\n"
            'SUBNET="${1:-192.168.1.0/24}"\n'
            'echo "[network-scan] scanning $SUBNET ..."\n\n'
            "if command -v nmap &>/dev/null; then\n"
            '    nmap -sn "$SUBNET" | grep -E "Nmap scan|Host is"\n'
            "else\n"
            "    # Fallback: ping sweep\n"
            '    BASE="${SUBNET%.*}"\n'
            "    for i in $(seq 1 254); do\n"
            '        ping -c1 -W1 "${BASE}.${i}" &>/dev/null && echo "${BASE}.${i} is up" &\n'
            "    done\n"
            "    wait\n"
            "fi\n"
        ),
    },
    "disk-usage": {
        "description": "Report disk usage for all mounted volumes with alerts for high usage",
        "script_type": "bash",
        "tags": ["disk", "usage", "storage", "space", "df"],
        "script": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n\n"
            'THRESHOLD="${1:-80}"\n'
            'echo "[disk-usage] volumes above ${THRESHOLD}% usage:"\n'
            'echo ""\n'
            "df -h | awk -v t=\"$THRESHOLD\" 'NR>1 && +$5 >= t {print $0}'\n"
            'echo ""\n'
            'echo "[disk-usage] full report:"\n'
            "df -h\n"
        ),
    },
    "git-stats": {
        "description": "Show git repository statistics: commits, contributors, churn",
        "script_type": "bash",
        "tags": ["git", "stats", "commits", "contributors", "repo"],
        "script": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n\n"
            'echo "[git-stats] Repository: $(basename "$(git rev-parse --show-toplevel)")"\n'
            'echo ""\n'
            'echo "Total commits: $(git rev-list --count HEAD)"\n'
            'echo "Contributors:"\n'
            "git shortlog -sn --no-merges | head -10\n"
            'echo ""\n'
            'echo "Recent activity (last 7 days):"\n'
            'git log --oneline --since="7 days ago" | head -20\n'
        ),
    },
    "docker-health": {
        "description": "Check health status of all Docker containers and images",
        "script_type": "bash",
        "tags": ["docker", "health", "containers", "images", "status"],
        "script": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n\n"
            'echo "[docker-health] Container status:"\n'
            'docker ps -a --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}" 2>/dev/null || echo "Docker not available"\n'
            'echo ""\n'
            'echo "[docker-health] Disk usage:"\n'
            "docker system df 2>/dev/null || true\n"
        ),
    },
    "log-search": {
        "description": "Search system and application logs for patterns",
        "script_type": "bash",
        "tags": ["log", "search", "grep", "syslog", "errors"],
        "script": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n\n"
            'PATTERN="${1:-error}"\n'
            'LINES="${2:-50}"\n'
            'echo "[log-search] searching for: $PATTERN (last $LINES matches)"\n'
            'echo ""\n\n'
            'if [[ "$(uname)" == "Darwin" ]]; then\n'
            '    log show --predicate "eventMessage CONTAINS[c] \'$PATTERN\'" --last 1h --style compact 2>/dev/null | tail -"$LINES"\n'
            "else\n"
            '    journalctl --no-pager -n "$LINES" --grep="$PATTERN" 2>/dev/null || \\\n'
            '        grep -ri "$PATTERN" /var/log/syslog /var/log/messages 2>/dev/null | tail -"$LINES"\n'
            "fi\n"
        ),
    },
}

# Keyword mapping: words in a description -> template name
_KEYWORD_MAP: dict[str, list[str]] = {
    "network-scan": ["network", "scan", "nmap", "ping", "hosts", "subnet", "ip", "discovery"],
    "disk-usage": ["disk", "usage", "storage", "space", "volume", "mount", "df", "full"],
    "git-stats": ["git", "repo", "commit", "contributor", "stats", "history", "churn"],
    "docker-health": ["docker", "container", "image", "health", "compose", "status"],
    "log-search": ["log", "search", "error", "syslog", "journal", "grep", "debug"],
}


def _kebab(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return re.sub(r"-+", "-", s)


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in re.split(r"[^a-zA-Z0-9]+", text) if len(w) > 1}


def _match_template(description: str) -> str | None:
    tokens = _tokenize(description)
    best_name: str | None = None
    best_score = 0
    for tpl_name, keywords in _KEYWORD_MAP.items():
        score = len(tokens & set(keywords))
        if score > best_score:
            best_score = score
            best_name = tpl_name
    return best_name if best_score >= 1 else None


def suggest_skill(description: str) -> dict:
    """Analyze description and return a suggested skill.yaml config."""
    template_match = _match_template(description)

    if template_match and template_match in BUILTIN_TEMPLATES:
        tpl = BUILTIN_TEMPLATES[template_match]
        return {
            "name": template_match,
            "description": tpl["description"],
            "tags": tpl["tags"],
            "script_type": tpl["script_type"],
            "template": template_match,
        }

    # No template match -- derive a name from the description
    name = _kebab(description)[:40].rstrip("-")
    return {
        "name": name,
        "description": description,
        "tags": list(_tokenize(description))[:5],
        "script_type": "bash",
        "template": None,
    }


def install_from_template(
    template_name: str,
    skills_dir: Path | None = None,
    registry: SkillRegistry | None = None,
) -> str:
    """Install a skill from a built-in template. Returns the skill name."""
    if template_name not in BUILTIN_TEMPLATES:
        available = ", ".join(sorted(BUILTIN_TEMPLATES))
        raise ValueError(f"Unknown template: {template_name}. Available: {available}")

    tpl = BUILTIN_TEMPLATES[template_name]

    # Scaffold via SkillCreator
    skill_dir = create_skill(
        name=template_name,
        description=tpl["description"],
        script_type=tpl["script_type"],
        skills_dir=skills_dir,
    )

    # Overwrite the stub script with the real template body
    script_file = "run.py" if tpl["script_type"] == "python" else "run.sh"
    (skill_dir / script_file).write_text(tpl["script"])

    # Register with the registry
    if registry is not None:
        _register(registry, skill_dir)

    return template_name


def _register(registry: SkillRegistry, skill_dir: Path) -> None:
    """Register a skill, handling the case where it's already in-place."""
    resolved_skill = skill_dir.resolve()
    resolved_dest = (registry.skills_dir / skill_dir.name).resolve()
    if resolved_skill == resolved_dest:
        # Already in the right place -- just re-discover
        registry.discover()
    else:
        registry.install(skill_dir)


def check_and_install(
    capability_description: str,
    skills_dir: Path | None = None,
    registry: SkillRegistry | None = None,
) -> str | None:
    """Check if a matching skill exists; if not, create and register one.

    Returns the skill name if installed, or None if nothing could be done.
    """
    if registry is None:
        registry = SkillRegistry(skills_dir)

    # 1. Check if a skill already exists that matches
    registry.discover()
    tokens = _tokenize(capability_description)
    for skill in registry.list_skills():
        skill_tokens = _tokenize(skill.name) | _tokenize(skill.description)
        overlap = tokens & skill_tokens
        if len(overlap) >= 1:
            return skill.name

    # 2. Try to match a built-in template
    template_match = _match_template(capability_description)
    if template_match:
        return install_from_template(
            template_match,
            skills_dir=skills_dir or registry.skills_dir,
            registry=registry,
        )

    # 3. No template -- scaffold a generic skill
    name = _kebab(capability_description)[:40].rstrip("-")
    if not name:
        return None

    target_dir = skills_dir or registry.skills_dir
    skill_dir = create_skill(
        name=name,
        description=capability_description,
        script_type="bash",
        skills_dir=target_dir,
    )
    _register(registry, skill_dir)
    return name
