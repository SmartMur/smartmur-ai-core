"""GitHub administration — branch protection, repo settings, audit.

Wraps the ``gh`` CLI for common GitHub admin operations:
- Authentication status checks
- Repository listing
- Branch protection rules (get / set / audit)
- Bulk-protect all repos with sensible defaults
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

GH_BIN = shutil.which("gh") or "/home/ray/.local/bin/gh"


class GitHubAdmin:
    """Wraps gh CLI for GitHub admin operations.

    Parameters
    ----------
    owner : str
        GitHub user or organization that owns the target repos.
    gh_bin : str | Path
        Path to the ``gh`` binary.  Defaults to :data:`GH_BIN`.
    """

    def __init__(self, owner: str = "smartmur", gh_bin: str | Path = GH_BIN):
        self.owner = owner
        self.gh = str(gh_bin)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def is_authenticated(self) -> tuple[bool, str]:
        """Check if ``gh`` is authenticated.

        Returns
        -------
        tuple[bool, str]
            ``(True, output)`` when authenticated, ``(False, output)``
            otherwise.
        """
        if not shutil.which(self.gh) and not Path(self.gh).exists():
            return False, "gh CLI not found"
        try:
            result = subprocess.run(
                [self.gh, "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0, (result.stdout + result.stderr).strip()
        except FileNotFoundError:
            return False, "gh CLI not found"

    # ------------------------------------------------------------------
    # Repository listing
    # ------------------------------------------------------------------

    def list_repos(self) -> list[dict]:
        """List all repos for *self.owner*.

        Returns
        -------
        list[dict]
            Each dict contains ``name``, ``defaultBranchRef``,
            ``isPrivate``, ``isFork``.

        Raises
        ------
        RuntimeError
            If the ``gh`` command fails.
        """
        result = subprocess.run(
            [
                self.gh,
                "repo",
                "list",
                self.owner,
                "--json",
                "name,defaultBranchRef,isPrivate,isFork",
                "--limit",
                "100",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to list repos: {result.stderr}")
        return json.loads(result.stdout)

    # ------------------------------------------------------------------
    # Branch protection — read
    # ------------------------------------------------------------------

    def get_branch_protection(self, repo: str, branch: str) -> dict | None:
        """Get branch protection rules for *repo*/*branch*.

        Returns
        -------
        dict | None
            Protection payload if the branch is protected, ``None``
            otherwise.
        """
        result = subprocess.run(
            [
                self.gh,
                "api",
                f"repos/{self.owner}/{repo}/branches/{branch}/protection",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)

    # ------------------------------------------------------------------
    # Branch protection — write
    # ------------------------------------------------------------------

    def enable_branch_protection(self, repo: str, branch: str) -> tuple[bool, str]:
        """Enable branch protection with sensible defaults.

        Defaults applied:
        - Enforce admins
        - Require 1 approving review, dismiss stale reviews
        - Disallow force pushes and deletions

        Returns
        -------
        tuple[bool, str]
            ``(True, "protected")`` on success, ``(False, error_msg)``
            on failure.
        """
        payload = json.dumps(
            {
                "required_status_checks": None,
                "enforce_admins": True,
                "required_pull_request_reviews": {
                    "dismiss_stale_reviews": True,
                    "required_approving_review_count": 1,
                },
                "restrictions": None,
                "allow_force_pushes": False,
                "allow_deletions": False,
            }
        )
        result = subprocess.run(
            [
                self.gh,
                "api",
                "-X",
                "PUT",
                f"repos/{self.owner}/{repo}/branches/{branch}/protection",
                "--input",
                "-",
            ],
            input=payload,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, "protected"

    # ------------------------------------------------------------------
    # Repo + branch discovery
    # ------------------------------------------------------------------

    # Known repos/branches as a fallback when the API is unreachable.
    _KNOWN_REPOS: list[dict] = [
        {"repo": "k3s-cluster", "branch": "main"},
        {"repo": "homelab", "branch": "main"},
        {"repo": "dotfiles", "branch": "main"},
        {"repo": "home_media", "branch": "master"},
        {"repo": "Lighthouse-AI", "branch": "main"},
        {"repo": "Smoke", "branch": "main"},
        {"repo": "design-os", "branch": "main"},
        {"repo": "claude-code-tresor", "branch": "main"},
        {"repo": "agent-os", "branch": "main"},
        {"repo": "claude-code-skill-factory", "branch": "dev"},
    ]

    def get_repo_branches(self) -> list[dict]:
        """Get all repos with their default branch names.

        Tries the GitHub API first; falls back to a hard-coded list on
        error.

        Returns
        -------
        list[dict]
            Each dict has ``repo`` and ``branch`` keys.
        """
        try:
            api_repos = self.list_repos()
            result: list[dict] = []
            for r in api_repos:
                branch_ref = r.get("defaultBranchRef")
                branch = branch_ref.get("name", "main") if isinstance(branch_ref, dict) else "main"
                result.append({"repo": r["name"], "branch": branch})
            return result if result else list(self._KNOWN_REPOS)
        except (RuntimeError, subprocess.SubprocessError, OSError, json.JSONDecodeError, KeyError, TypeError):
            return list(self._KNOWN_REPOS)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def protect_all_repos(self, repos: list[dict] | None = None) -> list[dict]:
        """Enable branch protection on every repo.

        Parameters
        ----------
        repos : list[dict] | None
            Override list of ``{"repo": ..., "branch": ...}`` dicts.
            Defaults to :meth:`get_repo_branches`.

        Returns
        -------
        list[dict]
            One entry per repo with ``repo``, ``branch``, ``ok``, and
            ``detail`` fields.
        """
        if repos is None:
            repos = self.get_repo_branches()
        results: list[dict] = []
        for r in repos:
            ok, detail = self.enable_branch_protection(r["repo"], r["branch"])
            results.append(
                {
                    "repo": r["repo"],
                    "branch": r["branch"],
                    "ok": ok,
                    "detail": detail,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def audit_protection(self) -> list[dict]:
        """Audit branch protection status across all repos.

        Returns
        -------
        list[dict]
            One entry per repo with ``repo``, ``branch``, ``protected``
            (bool), and ``details`` (dict | None) fields.
        """
        repos = self.get_repo_branches()
        results: list[dict] = []
        for r in repos:
            protection = self.get_branch_protection(r["repo"], r["branch"])
            results.append(
                {
                    "repo": r["repo"],
                    "branch": r["branch"],
                    "protected": protection is not None,
                    "details": protection,
                }
            )
        return results
