"""Browser profile management — persistent browser contexts."""

from __future__ import annotations

import shutil
from pathlib import Path

from superpowers.browser.base import BrowserError


class ProfileManager:
    def __init__(self, profiles_dir: Path | None = None):
        if profiles_dir is None:
            from superpowers.config import get_data_dir

            profiles_dir = get_data_dir() / "browser" / "profiles"
        self._profiles_dir = profiles_dir
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[str]:
        if not self._profiles_dir.exists():
            return []
        return sorted(d.name for d in self._profiles_dir.iterdir() if d.is_dir())

    def delete_profile(self, name: str) -> None:
        path = self._profiles_dir / name
        if not path.exists():
            raise BrowserError(f"Profile not found: {name}")
        shutil.rmtree(path)

    def profile_path(self, name: str) -> Path:
        path = self._profiles_dir / name
        path.mkdir(parents=True, exist_ok=True)
        return path
