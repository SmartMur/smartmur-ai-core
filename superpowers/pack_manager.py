"""Pack manager — install, update, uninstall, and validate skill/workflow/agent bundles.

A "pack" is a directory containing a ``pack.yaml`` manifest plus optional
``skills/``, ``workflows/``, and ``agents/`` subdirectories.  Packs can be
installed from a local directory or cloned from a git URL.

Installed pack metadata is tracked in
``~/.claude-superpowers/packs/registry.json``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from superpowers.config import get_data_dir

logger = logging.getLogger(__name__)

# Default project-level directories for skills, workflows, agents
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_skills_dir() -> Path:
    return _PROJECT_ROOT / "skills"


def _default_workflows_dir() -> Path:
    return _PROJECT_ROOT / "workflows"


def _default_agents_dir() -> Path:
    return _PROJECT_ROOT / "subagents"


# ---------------------------------------------------------------------------
# Dataclass: PackManifest
# ---------------------------------------------------------------------------


@dataclass
class PackManifest:
    """Parsed representation of a ``pack.yaml`` file."""

    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    skills: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    checksum: str = ""

    @classmethod
    def from_yaml(cls, path: Path) -> PackManifest:
        """Load a manifest from a ``pack.yaml`` file."""
        if not path.is_file():
            raise PackError(f"Manifest not found: {path}")
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise PackError(f"Invalid YAML in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise PackError(f"pack.yaml must be a mapping, got {type(data).__name__}")
        name = data.get("name")
        if not name or not isinstance(name, str):
            raise PackError("pack.yaml must contain a 'name' field")
        return cls(
            name=name,
            version=str(data.get("version", "0.0.0")),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            skills=_str_list(data.get("skills")),
            workflows=_str_list(data.get("workflows")),
            agents=_str_list(data.get("agents")),
            checksum=str(data.get("checksum", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PackError(Exception):
    """Raised for any pack-related error."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _str_list(val: Any) -> list[str]:
    """Coerce a YAML value into a list of strings."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val]
    return [str(val)]


def _sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a single file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_dir(directory: Path) -> str:
    """Return a deterministic SHA-256 digest over all files in *directory*.

    Files are sorted by their path relative to *directory* so the hash is
    reproducible regardless of filesystem ordering.
    """
    h = hashlib.sha256()
    for file_path in sorted(directory.rglob("*")):
        if file_path.is_file():
            rel = file_path.relative_to(directory)
            h.update(str(rel).encode())
            h.update(_sha256_file(file_path).encode())
    return h.hexdigest()


def _compute_pack_checksum(pack_dir: Path) -> str:
    """Compute the checksum of a pack directory (excluding pack.yaml's checksum field)."""
    h = hashlib.sha256()
    for file_path in sorted(pack_dir.rglob("*")):
        if file_path.is_file():
            rel = file_path.relative_to(pack_dir)
            # Skip the checksum value inside pack.yaml by hashing the whole
            # directory tree.  We include pack.yaml itself so that name/version
            # changes are detected, but the checksum field is stripped before
            # hashing.
            if rel == Path("pack.yaml"):
                # Hash pack.yaml with checksum field zeroed out
                data = yaml.safe_load(file_path.read_text()) or {}
                data["checksum"] = ""
                content = yaml.dump(data, sort_keys=True).encode()
                h.update(str(rel).encode())
                h.update(hashlib.sha256(content).hexdigest().encode())
            else:
                h.update(str(rel).encode())
                h.update(_sha256_file(file_path).encode())
    return h.hexdigest()


def _clone_git_repo(url: str, dest: Path) -> None:
    """Clone a git repository to *dest*."""
    result = subprocess.run(
        ["git", "clone", "--depth=1", url, str(dest)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise PackError(f"git clone failed: {result.stderr.strip()}")


# ---------------------------------------------------------------------------
# PackManager
# ---------------------------------------------------------------------------


class PackManager:
    """Install, update, list, uninstall, and validate packs."""

    def __init__(
        self,
        skills_dir: Path | None = None,
        workflows_dir: Path | None = None,
        agents_dir: Path | None = None,
        data_dir: Path | None = None,
    ):
        self.skills_dir = Path(skills_dir) if skills_dir else _default_skills_dir()
        self.workflows_dir = Path(workflows_dir) if workflows_dir else _default_workflows_dir()
        self.agents_dir = Path(agents_dir) if agents_dir else _default_agents_dir()
        self.data_dir = Path(data_dir) if data_dir else get_data_dir()
        self._registry_dir = self.data_dir / "packs"
        self._registry_file = self._registry_dir / "registry.json"

    # ------------------------------------------------------------------
    # Registry persistence
    # ------------------------------------------------------------------

    def _load_registry(self) -> dict[str, Any]:
        if not self._registry_file.is_file():
            return {}
        try:
            return json.loads(self._registry_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_registry(self, data: dict[str, Any]) -> None:
        self._registry_dir.mkdir(parents=True, exist_ok=True)
        self._registry_file.write_text(json.dumps(data, indent=2) + "\n")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self, source: str | Path) -> PackManifest:
        """Install a pack from a local directory or a git URL.

        Copies the pack's skills into ``skills_dir``, workflows into
        ``workflows_dir``, and agents into ``agents_dir``.  Records the
        installation in the registry.

        Returns the parsed manifest.
        """
        pack_dir = self._resolve_source(source)
        manifest = PackManifest.from_yaml(pack_dir / "pack.yaml")

        # Validate checksum if one is declared
        if manifest.checksum:
            actual = _compute_pack_checksum(pack_dir)
            if actual != manifest.checksum:
                raise PackError(
                    f"Checksum mismatch for pack '{manifest.name}': "
                    f"expected {manifest.checksum}, got {actual}"
                )

        # Validate that declared items exist in the pack
        errors = self._validate_contents(pack_dir, manifest)
        if errors:
            raise PackError(
                f"Pack '{manifest.name}' validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        # Copy artefacts
        self._copy_items(pack_dir, "skills", manifest.skills, self.skills_dir)
        self._copy_items(pack_dir, "workflows", manifest.workflows, self.workflows_dir)
        self._copy_items(pack_dir, "agents", manifest.agents, self.agents_dir)

        # Record in registry
        registry = self._load_registry()
        registry[manifest.name] = {
            **manifest.to_dict(),
            "source": str(source),
        }
        self._save_registry(registry)

        logger.info("Installed pack '%s' v%s", manifest.name, manifest.version)
        return manifest

    def update(self, name: str) -> PackManifest:
        """Re-fetch and update an installed pack.

        Reads the original source from the registry, re-installs from it.
        """
        registry = self._load_registry()
        if name not in registry:
            raise PackError(f"Pack '{name}' is not installed")

        source = registry[name].get("source", "")
        if not source:
            raise PackError(f"No source recorded for pack '{name}'")

        return self.install(source)

    def list_installed(self) -> list[dict[str, Any]]:
        """Return a list of installed pack metadata dicts."""
        registry = self._load_registry()
        return [
            {
                "name": name,
                "version": info.get("version", "?"),
                "description": info.get("description", ""),
                "author": info.get("author", ""),
                "skills": info.get("skills", []),
                "workflows": info.get("workflows", []),
                "agents": info.get("agents", []),
                "source": info.get("source", ""),
            }
            for name, info in sorted(registry.items())
        ]

    def uninstall(self, name: str) -> None:
        """Remove a pack and its installed artefacts."""
        registry = self._load_registry()
        if name not in registry:
            raise PackError(f"Pack '{name}' is not installed")

        info = registry[name]

        # Remove skills
        for skill in info.get("skills", []):
            target = self.skills_dir / skill
            if target.exists():
                shutil.rmtree(target)
                logger.debug("Removed skill: %s", target)

        # Remove workflows
        for wf in info.get("workflows", []):
            for suffix in (".yaml", ".yml"):
                target = self.workflows_dir / f"{wf}{suffix}"
                if target.exists():
                    target.unlink()
                    logger.debug("Removed workflow: %s", target)

        # Remove agents
        for agent in info.get("agents", []):
            target = self.agents_dir / agent
            if target.exists():
                shutil.rmtree(target)
                logger.debug("Removed agent: %s", target)

        del registry[name]
        self._save_registry(registry)
        logger.info("Uninstalled pack '%s'", name)

    def validate(self, source: str | Path) -> list[str]:
        """Validate a pack source and return a list of errors (empty = valid)."""
        try:
            pack_dir = self._resolve_source(source)
        except PackError as exc:
            return [str(exc)]

        manifest_path = pack_dir / "pack.yaml"
        if not manifest_path.is_file():
            return ["pack.yaml not found"]

        try:
            manifest = PackManifest.from_yaml(manifest_path)
        except PackError as exc:
            return [str(exc)]

        errors = self._validate_contents(pack_dir, manifest)

        # Checksum validation
        if manifest.checksum:
            actual = _compute_pack_checksum(pack_dir)
            if actual != manifest.checksum:
                errors.append(f"Checksum mismatch: expected {manifest.checksum}, got {actual}")

        return errors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_source(self, source: str | Path) -> Path:
        """Resolve a source to a local directory path.

        If *source* looks like a git URL, clone it to a temporary directory.
        Otherwise, treat it as a local path.
        """
        source_str = str(source)

        # Git URL detection
        if source_str.startswith(("https://", "git@", "ssh://", "git://")) or source_str.endswith(
            ".git"
        ):
            tmp_dir = Path(tempfile.mkdtemp(prefix="pack-"))
            _clone_git_repo(source_str, tmp_dir)
            return tmp_dir

        local = Path(source_str).resolve()
        if not local.is_dir():
            raise PackError(f"Source directory not found: {local}")
        return local

    @staticmethod
    def _validate_contents(pack_dir: Path, manifest: PackManifest) -> list[str]:
        """Validate that declared skills, workflows, and agents exist in the pack dir."""
        errors: list[str] = []

        skills_src = pack_dir / "skills"
        for skill in manifest.skills:
            skill_dir = skills_src / skill
            if not skill_dir.is_dir():
                errors.append(f"Skill directory not found: skills/{skill}")
            elif not (skill_dir / "skill.yaml").is_file():
                errors.append(f"Missing skill.yaml in skills/{skill}")

        workflows_src = pack_dir / "workflows"
        for wf in manifest.workflows:
            found = False
            for suffix in (".yaml", ".yml"):
                if (workflows_src / f"{wf}{suffix}").is_file():
                    found = True
                    break
            if not found:
                errors.append(f"Workflow file not found: workflows/{wf}.yaml")

        agents_src = pack_dir / "agents"
        for agent in manifest.agents:
            agent_dir = agents_src / agent
            if not agent_dir.is_dir():
                errors.append(f"Agent directory not found: agents/{agent}")

        return errors

    def _copy_items(
        self,
        pack_dir: Path,
        subdir: str,
        items: list[str],
        dest_base: Path,
    ) -> None:
        """Copy items from ``pack_dir/subdir/<item>`` to ``dest_base/<item>``."""
        src_base = pack_dir / subdir
        if not items:
            return

        dest_base.mkdir(parents=True, exist_ok=True)

        for item in items:
            src = src_base / item
            if not src.exists():
                # For workflows, the item might be a file not a directory
                for suffix in (".yaml", ".yml"):
                    candidate = src_base / f"{item}{suffix}"
                    if candidate.is_file():
                        dest = dest_base / f"{item}{suffix}"
                        if dest.exists():
                            dest.unlink()
                        shutil.copy2(candidate, dest)
                        break
                continue

            if src.is_dir():
                dest = dest_base / item
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
            elif src.is_file():
                dest = dest_base / item
                if dest.exists():
                    dest.unlink()
                shutil.copy2(src, dest)
