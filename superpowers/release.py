"""Release manager — prepare, tag, verify, and rollback releases with migration checking.

Provides ``ReleaseManager`` for managing the release lifecycle (changelog
generation, git tagging, verification, rollback) and ``MigrationChecker`` for
detecting breaking changes between versions.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z\-.]+))?(?:\+(?P<build>[0-9A-Za-z\-.]+))?$"
)

# Conventional-commit prefixes we recognise for changelog grouping
_COMMIT_TYPES = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "chore": "Chores",
    "docs": "Documentation",
    "ci": "CI / Build",
    "refactor": "Refactoring",
    "test": "Tests",
    "perf": "Performance",
    "style": "Style",
}


class ReleaseError(Exception):
    """Raised for any release-related error."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_git(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a git command with list args (no shell=True)."""
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd or _PROJECT_ROOT,
    )


def validate_semver(version: str) -> bool:
    """Return True if *version* is valid semver."""
    return _SEMVER_RE.match(version) is not None


def parse_semver(version: str) -> dict[str, str]:
    """Parse a semver string into its components. Raises ``ReleaseError`` on invalid input."""
    m = _SEMVER_RE.match(version)
    if not m:
        raise ReleaseError(f"Invalid semver: {version}")
    return {
        "major": m.group("major"),
        "minor": m.group("minor"),
        "patch": m.group("patch"),
        "pre": m.group("pre") or "",
        "build": m.group("build") or "",
    }


def _parse_commit_line(line: str) -> tuple[str, str]:
    """Parse a conventional-commit line into (type, message).

    Returns (``"other"``, *line*) when the line does not follow the convention.
    """
    m = re.match(r"^(\w+)(?:\(.+?\))?!?:\s*(.+)$", line)
    if m:
        return m.group(1).lower(), m.group(2).strip()
    return "other", line.strip()


# ---------------------------------------------------------------------------
# ReleaseManager
# ---------------------------------------------------------------------------


class ReleaseManager:
    """Manage the release lifecycle: prepare, tag, verify, rollback."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = Path(project_root) if project_root else _PROJECT_ROOT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare_release(self, version: str) -> dict[str, Any]:
        """Prepare a release: validate version, check git state, build changelog.

        Returns a summary dict with keys: ``version``, ``clean``, ``changelog``,
        ``pyproject_version``, ``ready``.
        """
        if not validate_semver(version):
            raise ReleaseError(f"Invalid semver version: {version}")

        clean = self._is_git_clean()
        pyproject_ver = self._read_pyproject_version()
        last_tag = self._get_last_tag()
        changelog = self.build_changelog(last_tag or "", "HEAD")

        ready = clean and (pyproject_ver == version)

        return {
            "version": version,
            "clean": clean,
            "changelog": changelog,
            "pyproject_version": pyproject_ver,
            "version_match": pyproject_ver == version,
            "last_tag": last_tag or "(none)",
            "ready": ready,
        }

    def build_changelog(self, from_tag: str, to_ref: str = "HEAD") -> str:
        """Generate a changelog grouped by commit type.

        Uses ``git log`` between *from_tag* and *to_ref*.  If *from_tag* is
        empty, logs from the beginning of history.
        """
        if from_tag:
            range_spec = f"{from_tag}..{to_ref}"
        else:
            range_spec = to_ref

        result = _run_git(
            ["log", "--pretty=format:%s", range_spec],
            cwd=self.project_root,
        )
        if result.returncode != 0:
            raise ReleaseError(f"git log failed: {result.stderr.strip()}")

        lines = [l for l in result.stdout.splitlines() if l.strip()]
        return self._format_changelog(lines)

    def create_tag(self, version: str, message: str = "") -> str:
        """Create an annotated git tag for the given version.

        Returns the tag name (``v{version}``).
        """
        if not validate_semver(version):
            raise ReleaseError(f"Invalid semver version: {version}")

        tag_name = f"v{version}"
        msg = message or f"Release {tag_name}"

        result = _run_git(
            ["tag", "-a", tag_name, "-m", msg],
            cwd=self.project_root,
        )
        if result.returncode != 0:
            raise ReleaseError(f"Failed to create tag: {result.stderr.strip()}")

        logger.info("Created tag %s", tag_name)
        return tag_name

    def verify_release(self, version: str) -> dict[str, Any]:
        """Post-release verification.

        Checks that the tag exists and pyproject.toml version matches.
        Returns a dict with ``tag_exists``, ``pyproject_match``, ``verified``.
        """
        if not validate_semver(version):
            raise ReleaseError(f"Invalid semver version: {version}")

        tag_name = f"v{version}"
        tag_exists = self._tag_exists(tag_name)
        pyproject_ver = self._read_pyproject_version()
        pyproject_match = pyproject_ver == version

        return {
            "version": version,
            "tag": tag_name,
            "tag_exists": tag_exists,
            "pyproject_version": pyproject_ver,
            "pyproject_match": pyproject_match,
            "verified": tag_exists and pyproject_match,
        }

    def rollback_release(self, version: str) -> dict[str, Any]:
        """Delete the local tag for a release and return rollback instructions.

        Returns a dict with ``tag_deleted``, ``instructions``.
        """
        if not validate_semver(version):
            raise ReleaseError(f"Invalid semver version: {version}")

        tag_name = f"v{version}"
        tag_deleted = False

        if self._tag_exists(tag_name):
            result = _run_git(["tag", "-d", tag_name], cwd=self.project_root)
            if result.returncode == 0:
                tag_deleted = True
                logger.info("Deleted local tag %s", tag_name)
            else:
                raise ReleaseError(f"Failed to delete tag: {result.stderr.strip()}")

        instructions = [
            f"Local tag {tag_name} {'deleted' if tag_deleted else 'not found (already removed?)'}.",
            "",
            "If the tag was pushed to remote, also run:",
            f"  git push origin :refs/tags/{tag_name}",
            "",
            "If a GitHub release was created, delete it via:",
            f"  gh release delete {tag_name} --yes",
            "",
            "To revert the version bump commit:",
            "  git revert HEAD",
        ]

        return {
            "version": version,
            "tag": tag_name,
            "tag_deleted": tag_deleted,
            "instructions": "\n".join(instructions),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_git_clean(self) -> bool:
        """Return True if the working tree has no uncommitted changes."""
        result = _run_git(["status", "--porcelain"], cwd=self.project_root)
        return result.returncode == 0 and not result.stdout.strip()

    def _get_last_tag(self) -> str | None:
        """Return the most recent tag reachable from HEAD, or None."""
        result = _run_git(["describe", "--tags", "--abbrev=0"], cwd=self.project_root)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    def _tag_exists(self, tag_name: str) -> bool:
        """Return True if a git tag with the given name exists."""
        result = _run_git(["tag", "--list", tag_name], cwd=self.project_root)
        return result.returncode == 0 and tag_name in result.stdout.splitlines()

    def _read_pyproject_version(self) -> str:
        """Read the version string from pyproject.toml."""
        pyproject = self.project_root / "pyproject.toml"
        if not pyproject.is_file():
            return ""
        for line in pyproject.read_text().splitlines():
            m = re.match(r'^version\s*=\s*"([^"]+)"', line)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _format_changelog(commit_lines: list[str]) -> str:
        """Group commit lines by type and format as Markdown changelog."""
        groups: dict[str, list[str]] = {}
        for line in commit_lines:
            ctype, msg = _parse_commit_line(line)
            heading = _COMMIT_TYPES.get(ctype, "Other")
            groups.setdefault(heading, []).append(msg)

        if not groups:
            return "No changes found.\n"

        sections = []
        # Output known types first (in defined order), then "Other"
        ordered_headings = list(_COMMIT_TYPES.values()) + ["Other"]
        for heading in ordered_headings:
            if heading in groups:
                items = groups[heading]
                section_lines = [f"### {heading}\n"]
                for item in items:
                    section_lines.append(f"- {item}")
                sections.append("\n".join(section_lines))

        return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# MigrationChecker
# ---------------------------------------------------------------------------


@dataclass
class CLICommand:
    """Represents a CLI command extracted from source."""

    name: str
    group: str = ""


@dataclass
class ConfigKey:
    """Represents a configuration key."""

    key: str
    file: str = ""


class MigrationChecker:
    """Detect breaking changes between versions and generate migration guides."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = Path(project_root) if project_root else _PROJECT_ROOT

    def check_breaking_changes(
        self, from_ver: str, to_ver: str
    ) -> dict[str, Any]:
        """Scan for breaking changes between two versions.

        Uses ``git diff`` to detect removed/renamed CLI commands, changed
        config keys, and removed Python APIs.

        Returns a dict with ``removed_commands``, ``changed_configs``,
        ``removed_apis``, ``has_breaking_changes``.
        """
        from_tag = f"v{from_ver}" if validate_semver(from_ver) else from_ver
        to_tag = f"v{to_ver}" if validate_semver(to_ver) else to_ver

        removed_commands = self._detect_removed_commands(from_tag, to_tag)
        changed_configs = self._detect_changed_configs(from_tag, to_tag)
        removed_apis = self._detect_removed_apis(from_tag, to_tag)

        has_breaking = bool(removed_commands or changed_configs or removed_apis)

        return {
            "from_version": from_ver,
            "to_version": to_ver,
            "removed_commands": removed_commands,
            "changed_configs": changed_configs,
            "removed_apis": removed_apis,
            "has_breaking_changes": has_breaking,
        }

    def generate_migration_guide(self, from_ver: str, to_ver: str) -> str:
        """Generate a Markdown migration guide between two versions."""
        changes = self.check_breaking_changes(from_ver, to_ver)

        lines = [
            f"# Migration Guide: v{from_ver} -> v{to_ver}\n",
        ]

        if not changes["has_breaking_changes"]:
            lines.append("No breaking changes detected. This is a drop-in upgrade.\n")
            lines.append("## Upgrade Steps\n")
            lines.append("1. Pull the latest code: `git pull origin main`")
            lines.append("2. Install dependencies: `pip install -e .`")
            lines.append("3. Verify: `claw --version`\n")
            return "\n".join(lines)

        lines.append("**WARNING: Breaking changes detected.** Review carefully before upgrading.\n")

        if changes["removed_commands"]:
            lines.append("## Removed CLI Commands\n")
            lines.append("The following CLI commands have been removed:\n")
            for cmd in changes["removed_commands"]:
                lines.append(f"- `claw {cmd}`")
            lines.append("")

        if changes["changed_configs"]:
            lines.append("## Changed Configuration Keys\n")
            lines.append("The following configuration keys have changed:\n")
            for key in changes["changed_configs"]:
                lines.append(f"- `{key}`")
            lines.append("")

        if changes["removed_apis"]:
            lines.append("## Removed Python APIs\n")
            lines.append("The following public functions/classes have been removed:\n")
            for api in changes["removed_apis"]:
                lines.append(f"- `{api}`")
            lines.append("")

        lines.append("## Upgrade Steps\n")
        lines.append("1. Review the breaking changes above")
        lines.append("2. Update your code/configuration to match the new version")
        lines.append("3. Pull the latest code: `git pull origin main`")
        lines.append("4. Install dependencies: `pip install -e .`")
        lines.append("5. Run tests: `pytest`")
        lines.append("6. Verify: `claw --version`\n")

        lines.append("## Rollback\n")
        lines.append(f"If you need to rollback to v{from_ver}:\n")
        lines.append(f"```bash")
        lines.append(f"git checkout v{from_ver}")
        lines.append(f"pip install -e .")
        lines.append(f"```\n")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal detection methods
    # ------------------------------------------------------------------

    def _detect_removed_commands(self, from_ref: str, to_ref: str) -> list[str]:
        """Detect CLI commands removed between two refs."""
        removed: list[str] = []

        result = _run_git(
            ["diff", from_ref, to_ref, "--", "superpowers/cli.py", "superpowers/cli_*.py"],
            cwd=self.project_root,
        )
        if result.returncode != 0:
            return removed

        # Look for removed click command/group decorators
        for line in result.stdout.splitlines():
            if line.startswith("-") and not line.startswith("---"):
                m = re.search(r'@\w+\.command\("([^"]+)"\)', line)
                if m:
                    removed.append(m.group(1))
                m = re.search(r'@click\.group\("([^"]+)"\)', line)
                if m:
                    removed.append(m.group(1))

        return removed

    def _detect_changed_configs(self, from_ref: str, to_ref: str) -> list[str]:
        """Detect changed/removed config keys between two refs."""
        changed: list[str] = []

        result = _run_git(
            ["diff", from_ref, to_ref, "--", "superpowers/config.py", ".env.example"],
            cwd=self.project_root,
        )
        if result.returncode != 0:
            return changed

        for line in result.stdout.splitlines():
            if line.startswith("-") and not line.startswith("---"):
                # Match env var references like _env("KEY_NAME")
                m = re.search(r'_env\("([^"]+)"', line)
                if m:
                    changed.append(m.group(1))
                # Match .env style KEY=VALUE
                m = re.match(r'^-([A-Z_][A-Z0-9_]*)=', line)
                if m:
                    changed.append(m.group(1))

        return changed

    def _detect_removed_apis(self, from_ref: str, to_ref: str) -> list[str]:
        """Detect removed public Python functions/classes between two refs."""
        removed: list[str] = []

        result = _run_git(
            ["diff", from_ref, to_ref, "--", "superpowers/*.py"],
            cwd=self.project_root,
        )
        if result.returncode != 0:
            return removed

        for line in result.stdout.splitlines():
            if line.startswith("-") and not line.startswith("---"):
                # Match removed class or function definitions (public only)
                m = re.match(r'^-(?:class|def)\s+([A-Z]\w+|[a-z]\w+)\s*[:(]', line)
                if m:
                    name = m.group(1)
                    if not name.startswith("_"):
                        removed.append(name)

        return removed
