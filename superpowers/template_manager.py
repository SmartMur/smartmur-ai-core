"""Template manager for claude-superpowers managed configuration files.

Tracks shipped templates (workflow YAMLs, docker-compose, doc files),
detects user modifications, and supports upgrade with backup.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from superpowers.config import get_data_dir

# Default shipped template sources (relative to project root)
DEFAULT_TEMPLATE_SOURCES: dict[str, str] = {
    "docker-compose.yaml": "docker-compose.yaml",
    "docker-compose.prod.yaml": "docker-compose.prod.yaml",
    "workflows/deploy.yaml": "workflows/deploy.yaml",
    "workflows/backup.yaml": "workflows/backup.yaml",
    "workflows/morning-brief.yaml": "workflows/morning-brief.yaml",
    ".env.example": ".env.example",
}


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_copy(src: Path, dest: Path) -> None:
    """Copy src to dest, handling the case where they are the same file."""
    try:
        src_resolved = src.resolve()
        dest_resolved = dest.resolve()
    except OSError:
        src_resolved = src
        dest_resolved = dest

    if src_resolved == dest_resolved:
        # Same file — nothing to copy
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


class TemplateManager:
    """Manage shipped configuration templates with user-customization tracking.

    Tracks managed files in a JSON manifest at ``data_dir/templates.json``.
    Each entry records the template name, the shipped hash, the installed hash,
    and the destination path.
    """

    def __init__(
        self,
        project_dir: Path | None = None,
        data_dir: Path | None = None,
        template_sources: dict[str, str] | None = None,
    ):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.data_dir = Path(data_dir) if data_dir else get_data_dir()
        self.template_sources = template_sources or DEFAULT_TEMPLATE_SOURCES
        self.manifest_path = self.data_dir / "templates.json"

    # ------------------------------------------------------------------
    # Manifest I/O
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict[str, dict[str, str]]:
        """Load the template manifest from disk."""
        if not self.manifest_path.exists():
            return {}
        try:
            return json.loads(self.manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_manifest(self, manifest: dict[str, dict[str, str]]) -> None:
        """Persist the template manifest to disk."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def init(self) -> list[str]:
        """Copy managed templates to user's config directory.

        Only copies templates that do not yet exist at the destination.
        Returns a list of template names that were installed.
        """
        manifest = self._load_manifest()
        installed: list[str] = []

        for name, rel_path in self.template_sources.items():
            src = self.project_dir / rel_path
            dest = self.project_dir / name

            if not src.exists():
                continue

            # If destination already exists and is tracked, skip
            if dest.exists() and name in manifest:
                continue

            # If destination does not exist, copy from source
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                _safe_copy(src, dest)

            # Record in manifest
            src_hash = _sha256(src)
            dest_hash = _sha256(dest)
            manifest[name] = {
                "shipped_hash": src_hash,
                "installed_hash": dest_hash,
                "dest": str(dest),
                "installed_at": datetime.now(timezone.utc).isoformat(),
            }
            installed.append(name)

        self._save_manifest(manifest)
        return installed

    def list_templates(self) -> list[dict[str, Any]]:
        """List all tracked templates and their status.

        Returns a list of dicts with keys: name, dest, status.
        Status is one of: 'current', 'modified', 'missing', 'untracked'.
        """
        manifest = self._load_manifest()
        result: list[dict[str, Any]] = []

        for name in self.template_sources:
            entry = manifest.get(name)
            dest = Path(entry["dest"]) if entry else self.project_dir / name

            if entry is None:
                status = "untracked"
            elif not dest.exists():
                status = "missing"
            else:
                current_hash = _sha256(dest)
                if current_hash == entry.get("shipped_hash"):
                    status = "current"
                else:
                    status = "modified"

            result.append({
                "name": name,
                "dest": str(dest),
                "status": status,
            })

        return result

    def diff(self, name: str | None = None) -> dict[str, str]:
        """Show differences between current files and shipped versions.

        Args:
            name: Specific template name, or None for all templates.

        Returns:
            Dict mapping template name to unified diff string.
            Empty string means no differences.
        """
        manifest = self._load_manifest()
        targets = [name] if name else list(self.template_sources.keys())
        diffs: dict[str, str] = {}

        for tname in targets:
            rel_path = self.template_sources.get(tname)
            if rel_path is None:
                continue

            src = self.project_dir / rel_path
            entry = manifest.get(tname)
            dest = Path(entry["dest"]) if entry else self.project_dir / tname

            if not src.exists() or not dest.exists():
                diffs[tname] = ""
                continue

            src_lines = src.read_text().splitlines(keepends=True)
            dest_lines = dest.read_text().splitlines(keepends=True)

            diff_lines = list(
                difflib.unified_diff(
                    src_lines,
                    dest_lines,
                    fromfile=f"shipped/{tname}",
                    tofile=f"current/{tname}",
                )
            )
            diffs[tname] = "".join(diff_lines)

        return diffs

    def reset(self, name: str) -> bool:
        """Restore a template to its shipped version.

        Creates a backup of the current file before overwriting.
        Returns True if the reset was performed.
        """
        rel_path = self.template_sources.get(name)
        if rel_path is None:
            return False

        src = self.project_dir / rel_path
        if not src.exists():
            return False

        manifest = self._load_manifest()
        entry = manifest.get(name)
        dest = Path(entry["dest"]) if entry else self.project_dir / name

        # Create backup if current file exists and differs
        if dest.exists():
            backup = dest.with_suffix(dest.suffix + ".bak")
            shutil.copy2(dest, backup)

        # Copy shipped version
        _safe_copy(src, dest)

        # Update manifest
        src_hash = _sha256(src)
        manifest[name] = {
            "shipped_hash": src_hash,
            "installed_hash": src_hash,
            "dest": str(dest),
            "installed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_manifest(manifest)
        return True

    def upgrade(self) -> dict[str, str]:
        """Apply template updates, preserving user customizations.

        For each template:
        - If unmodified by user: replace with new shipped version.
        - If modified by user: create backup, replace with shipped version.
        - If missing: skip (user removed it intentionally).

        Returns dict mapping template name to action taken:
        'updated', 'backup_and_updated', 'skipped', 'missing_source'.
        """
        manifest = self._load_manifest()
        actions: dict[str, str] = {}

        for name, rel_path in self.template_sources.items():
            src = self.project_dir / rel_path
            if not src.exists():
                actions[name] = "missing_source"
                continue

            entry = manifest.get(name)
            dest = Path(entry["dest"]) if entry else self.project_dir / name

            src_hash = _sha256(src)

            if not dest.exists():
                # File was removed by user — don't recreate
                actions[name] = "skipped"
                continue

            current_hash = _sha256(dest)

            if entry and current_hash != entry.get("shipped_hash"):
                # User has modified this file — backup first
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                backup = dest.with_suffix(f"{dest.suffix}.{timestamp}.bak")
                shutil.copy2(dest, backup)
                _safe_copy(src, dest)
                actions[name] = "backup_and_updated"
            else:
                # Unmodified or first time — just overwrite
                _safe_copy(src, dest)
                actions[name] = "updated"

            # Update manifest
            manifest[name] = {
                "shipped_hash": src_hash,
                "installed_hash": src_hash,
                "dest": str(dest),
                "installed_at": datetime.now(timezone.utc).isoformat(),
            }

        self._save_manifest(manifest)
        return actions
