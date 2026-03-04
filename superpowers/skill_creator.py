from __future__ import annotations

import re
import shutil
import stat
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

BASH_TEMPLATE = """\
#!/usr/bin/env bash
set -euo pipefail

# {name} — {description}

usage() {{
    echo "Usage: $(basename "$0") [options]"
    echo ""
    echo "  {description}"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    exit 0
}}

[[ "${{1:-}}" == "-h" || "${{1:-}}" == "--help" ]] && usage

main() {{
    echo "[{name}] running..."
    # TODO: implement skill logic
}}

main "$@"
"""

PYTHON_TEMPLATE = """\
#!/usr/bin/env python3
\"\"\"
{name} — {description}
\"\"\"
from __future__ import annotations

import argparse
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="{description}")
    # TODO: add arguments
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[{name}] running...")
    # TODO: implement skill logic
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

COMMAND_MD_TEMPLATE = """\
# {title}

{description}

## Usage

Run this skill:
```bash
{script_path}
```

## What This Skill Does

{description}

## Guidelines

- This skill should be idempotent where possible
- Check exit codes for success/failure
"""


def _kebab(name: str) -> str:
    """Normalise a skill name to kebab-case."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return re.sub(r"-+", "-", s)


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_skill(
    name: str,
    description: str,
    script_type: str = "bash",
    permissions: list[str] | None = None,
    triggers: list[str] | None = None,
    skills_dir: Path | None = None,
) -> Path:
    """Scaffold a new skill directory with manifest, script, and command.md."""
    name = _kebab(name)
    base = Path(skills_dir) if skills_dir else SKILLS_DIR
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Determine script filename
    if script_type == "python":
        script_file = "run.py"
    else:
        script_file = "run.sh"

    # --- skill.yaml ---
    manifest = {
        "name": name,
        "version": "0.1.0",
        "description": description,
        "author": "dre",
        "script": script_file,
        "slash_command": True,
        "permissions": permissions or [],
        "triggers": triggers or [],
    }
    (skill_dir / "skill.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False)
    )

    # --- run.sh / run.py ---
    script_path = skill_dir / script_file
    if script_type == "python":
        script_path.write_text(PYTHON_TEMPLATE.format(name=name, description=description))
    else:
        script_path.write_text(BASH_TEMPLATE.format(name=name, description=description))
    _make_executable(script_path)

    # --- command.md ---
    title = name.replace("-", " ").title()
    (skill_dir / "command.md").write_text(
        COMMAND_MD_TEMPLATE.format(
            title=title,
            description=description,
            script_path=str(script_path),
        )
    )

    return skill_dir


def _detect_script_type(source: Path) -> str:
    """Detect whether a script is bash or python by inspecting it."""
    try:
        first_line = source.read_text().split("\n", 1)[0]
    except (OSError, ValueError):
        return "bash"

    if "python" in first_line:
        return "python"
    if source.suffix == ".py":
        return "python"
    return "bash"


def scaffold_from_existing(
    source_script: Path,
    name: str,
    description: str,
    skills_dir: Path | None = None,
) -> Path:
    """Create a skill directory from an existing script file."""
    source_script = Path(source_script)
    if not source_script.is_file():
        raise FileNotFoundError(f"Source script not found: {source_script}")

    name = _kebab(name)
    script_type = _detect_script_type(source_script)
    base = Path(skills_dir) if skills_dir else SKILLS_DIR
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Copy script with canonical name
    script_file = "run.py" if script_type == "python" else "run.sh"
    dest_script = skill_dir / script_file
    shutil.copy2(source_script, dest_script)
    _make_executable(dest_script)

    # --- skill.yaml ---
    manifest = {
        "name": name,
        "version": "0.1.0",
        "description": description,
        "author": "dre",
        "script": script_file,
        "slash_command": True,
        "permissions": [],
        "triggers": [],
    }
    (skill_dir / "skill.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False)
    )

    # --- command.md ---
    title = name.replace("-", " ").title()
    (skill_dir / "command.md").write_text(
        COMMAND_MD_TEMPLATE.format(
            title=title,
            description=description,
            script_path=str(dest_script),
        )
    )

    return skill_dir
