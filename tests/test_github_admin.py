"""Tests for the GitHubAdmin module and github-admin skill."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from superpowers.github_admin import GH_BIN, GitHubAdmin

# ---------------------------------------------------------------------------
# Load the skill run.py for integration-style tests
# ---------------------------------------------------------------------------

_run_path = Path(__file__).resolve().parent.parent / "skills" / "github-admin" / "run.py"
_spec = importlib.util.spec_from_file_location("github_admin_run", _run_path)
_run_mod = importlib.util.module_from_spec(_spec)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin() -> GitHubAdmin:
    return GitHubAdmin(owner="testowner")


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    """Helper to build a CompletedProcess."""
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# GH binary path
# ---------------------------------------------------------------------------


class TestGhBinPath:
    def test_gh_bin_path(self):
        assert GH_BIN == (shutil.which("gh") or "/home/ray/.local/bin/gh")

    def test_default_gh_bin_on_instance(self):
        admin = GitHubAdmin()
        assert admin.gh == GH_BIN

    def test_custom_gh_bin(self):
        admin = GitHubAdmin(gh_bin="/usr/bin/gh")
        assert admin.gh == "/usr/bin/gh"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestIsAuthenticated:
    @patch("superpowers.github_admin.subprocess.run")
    def test_is_authenticated_success(self, mock_run, admin: GitHubAdmin):
        mock_run.return_value = _completed(
            returncode=0,
            stdout="Logged in to github.com as testuser\n",
            stderr="",
        )
        ok, output = admin.is_authenticated()

        assert ok is True
        assert "testuser" in output
        mock_run.assert_called_once_with(
            [admin.gh, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    @patch("superpowers.github_admin.subprocess.run")
    def test_is_authenticated_failure(self, mock_run, admin: GitHubAdmin):
        mock_run.return_value = _completed(
            returncode=1,
            stdout="",
            stderr="You are not logged into any GitHub hosts.",
        )
        ok, output = admin.is_authenticated()

        assert ok is False
        assert "not logged" in output


# ---------------------------------------------------------------------------
# list_repos
# ---------------------------------------------------------------------------


class TestListRepos:
    @patch("superpowers.github_admin.subprocess.run")
    def test_list_repos_success(self, mock_run, admin: GitHubAdmin):
        repos = [
            {
                "name": "repo1",
                "defaultBranchRef": {"name": "main"},
                "isPrivate": False,
                "isFork": False,
            },
            {
                "name": "repo2",
                "defaultBranchRef": {"name": "dev"},
                "isPrivate": True,
                "isFork": False,
            },
        ]
        mock_run.return_value = _completed(stdout=json.dumps(repos))

        result = admin.list_repos()

        assert len(result) == 2
        assert result[0]["name"] == "repo1"
        assert result[1]["isPrivate"] is True

    @patch("superpowers.github_admin.subprocess.run")
    def test_list_repos_failure(self, mock_run, admin: GitHubAdmin):
        mock_run.return_value = _completed(returncode=1, stderr="auth required")

        with pytest.raises(RuntimeError, match="Failed to list repos"):
            admin.list_repos()

    @patch("superpowers.github_admin.subprocess.run")
    def test_list_repos_empty(self, mock_run, admin: GitHubAdmin):
        mock_run.return_value = _completed(stdout="[]")

        result = admin.list_repos()
        assert result == []


# ---------------------------------------------------------------------------
# get_branch_protection
# ---------------------------------------------------------------------------


class TestGetBranchProtection:
    @patch("superpowers.github_admin.subprocess.run")
    def test_get_branch_protection_protected(self, mock_run, admin: GitHubAdmin):
        protection = {
            "enforce_admins": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
        }
        mock_run.return_value = _completed(stdout=json.dumps(protection))

        result = admin.get_branch_protection("myrepo", "main")

        assert result is not None
        assert result["enforce_admins"]["enabled"] is True
        mock_run.assert_called_once_with(
            [admin.gh, "api", "repos/testowner/myrepo/branches/main/protection"],
            capture_output=True,
            text=True,
            timeout=15,
        )

    @patch("superpowers.github_admin.subprocess.run")
    def test_get_branch_protection_unprotected(self, mock_run, admin: GitHubAdmin):
        mock_run.return_value = _completed(returncode=1, stderr="Not Found")

        result = admin.get_branch_protection("myrepo", "main")

        assert result is None


# ---------------------------------------------------------------------------
# enable_branch_protection
# ---------------------------------------------------------------------------


class TestEnableBranchProtection:
    @patch("superpowers.github_admin.subprocess.run")
    def test_enable_branch_protection_success(self, mock_run, admin: GitHubAdmin):
        mock_run.return_value = _completed(stdout='{"url": "..."}')

        ok, detail = admin.enable_branch_protection("myrepo", "main")

        assert ok is True
        assert detail == "protected"

        # Verify the call was made with --input -
        call_args = mock_run.call_args
        assert call_args[0][0][-2:] == ["--input", "-"]
        # Verify the payload was passed via stdin
        payload = json.loads(call_args[1]["input"])
        assert payload["enforce_admins"] is True
        assert payload["allow_force_pushes"] is False
        assert payload["allow_deletions"] is False
        assert payload["required_pull_request_reviews"]["required_approving_review_count"] == 1

    @patch("superpowers.github_admin.subprocess.run")
    def test_enable_branch_protection_failure(self, mock_run, admin: GitHubAdmin):
        mock_run.return_value = _completed(returncode=1, stderr="403 Forbidden")

        ok, detail = admin.enable_branch_protection("myrepo", "main")

        assert ok is False
        assert "403 Forbidden" in detail


# ---------------------------------------------------------------------------
# get_repo_branches
# ---------------------------------------------------------------------------


class TestGetRepoBranches:
    @patch("superpowers.github_admin.subprocess.run")
    def test_get_repo_branches_from_api(self, mock_run, admin: GitHubAdmin):
        repos = [
            {
                "name": "alpha",
                "defaultBranchRef": {"name": "main"},
                "isPrivate": False,
                "isFork": False,
            },
            {
                "name": "beta",
                "defaultBranchRef": {"name": "develop"},
                "isPrivate": True,
                "isFork": False,
            },
            {"name": "gamma", "defaultBranchRef": None, "isPrivate": False, "isFork": True},
        ]
        mock_run.return_value = _completed(stdout=json.dumps(repos))

        result = admin.get_repo_branches()

        assert len(result) == 3
        assert result[0] == {"repo": "alpha", "branch": "main"}
        assert result[1] == {"repo": "beta", "branch": "develop"}
        # None defaultBranchRef should fall back to "main"
        assert result[2] == {"repo": "gamma", "branch": "main"}

    @patch("superpowers.github_admin.subprocess.run")
    def test_get_repo_branches_fallback_on_error(self, mock_run, admin: GitHubAdmin):
        mock_run.side_effect = RuntimeError("network error")

        result = admin.get_repo_branches()

        # Should return the known fallback list
        assert len(result) == len(GitHubAdmin._KNOWN_REPOS)
        assert result[0]["repo"] == "k3s-cluster"

    @patch("superpowers.github_admin.subprocess.run")
    def test_get_repo_branches_fallback_on_empty(self, mock_run, admin: GitHubAdmin):
        mock_run.return_value = _completed(stdout="[]")

        result = admin.get_repo_branches()

        # Empty API result should fall back to known repos
        assert len(result) == len(GitHubAdmin._KNOWN_REPOS)

    @patch("superpowers.github_admin.subprocess.run")
    def test_get_repo_branches_dict_branch_ref(self, mock_run, admin: GitHubAdmin):
        """defaultBranchRef is a dict but missing 'name' key."""
        repos = [
            {"name": "delta", "defaultBranchRef": {}, "isPrivate": False, "isFork": False},
        ]
        mock_run.return_value = _completed(stdout=json.dumps(repos))

        result = admin.get_repo_branches()

        assert result[0] == {"repo": "delta", "branch": "main"}


# ---------------------------------------------------------------------------
# protect_all_repos
# ---------------------------------------------------------------------------


class TestProtectAllRepos:
    @patch("superpowers.github_admin.subprocess.run")
    def test_protect_all_repos_mixed_results(self, mock_run, admin: GitHubAdmin):
        # First call: list_repos (from get_repo_branches)
        repos = [
            {
                "name": "good",
                "defaultBranchRef": {"name": "main"},
                "isPrivate": False,
                "isFork": False,
            },
            {
                "name": "bad",
                "defaultBranchRef": {"name": "main"},
                "isPrivate": False,
                "isFork": False,
            },
        ]
        mock_run.side_effect = [
            # get_repo_branches -> list_repos
            _completed(stdout=json.dumps(repos)),
            # enable_branch_protection for "good" — success
            _completed(stdout='{"url": "..."}'),
            # enable_branch_protection for "bad" — failure
            _completed(returncode=1, stderr="403 Forbidden"),
        ]

        results = admin.protect_all_repos()

        assert len(results) == 2
        assert results[0]["ok"] is True
        assert results[0]["detail"] == "protected"
        assert results[1]["ok"] is False
        assert "403" in results[1]["detail"]

    @patch.object(GitHubAdmin, "get_repo_branches")
    @patch.object(GitHubAdmin, "enable_branch_protection")
    def test_protect_all_repos_custom_list(self, mock_protect, mock_branches, admin: GitHubAdmin):
        """Passing explicit repos list skips get_repo_branches."""
        custom = [{"repo": "custom-repo", "branch": "dev"}]
        mock_protect.return_value = (True, "protected")

        results = admin.protect_all_repos(repos=custom)

        mock_branches.assert_not_called()
        assert len(results) == 1
        assert results[0]["repo"] == "custom-repo"

    @patch.object(GitHubAdmin, "get_repo_branches")
    @patch.object(GitHubAdmin, "enable_branch_protection")
    def test_protect_all_repos_all_success(self, mock_protect, mock_branches, admin: GitHubAdmin):
        mock_branches.return_value = [
            {"repo": "a", "branch": "main"},
            {"repo": "b", "branch": "main"},
        ]
        mock_protect.return_value = (True, "protected")

        results = admin.protect_all_repos()

        assert all(r["ok"] for r in results)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# audit_protection
# ---------------------------------------------------------------------------


class TestAuditProtection:
    @patch.object(GitHubAdmin, "get_repo_branches")
    @patch.object(GitHubAdmin, "get_branch_protection")
    def test_audit_protection(self, mock_get_prot, mock_branches, admin: GitHubAdmin):
        mock_branches.return_value = [
            {"repo": "protected-repo", "branch": "main"},
            {"repo": "open-repo", "branch": "main"},
            {"repo": "also-protected", "branch": "dev"},
        ]
        mock_get_prot.side_effect = [
            {"enforce_admins": {"enabled": True}},  # protected-repo
            None,  # open-repo
            {"enforce_admins": {"enabled": False}},  # also-protected
        ]

        results = admin.audit_protection()

        assert len(results) == 3

        assert results[0]["repo"] == "protected-repo"
        assert results[0]["protected"] is True
        assert results[0]["details"] is not None

        assert results[1]["repo"] == "open-repo"
        assert results[1]["protected"] is False
        assert results[1]["details"] is None

        assert results[2]["repo"] == "also-protected"
        assert results[2]["protected"] is True

    @patch.object(GitHubAdmin, "get_repo_branches")
    @patch.object(GitHubAdmin, "get_branch_protection")
    def test_audit_protection_all_unprotected(
        self, mock_get_prot, mock_branches, admin: GitHubAdmin
    ):
        mock_branches.return_value = [
            {"repo": "a", "branch": "main"},
            {"repo": "b", "branch": "main"},
        ]
        mock_get_prot.return_value = None

        results = admin.audit_protection()

        assert len(results) == 2
        assert all(not r["protected"] for r in results)

    @patch.object(GitHubAdmin, "get_repo_branches")
    @patch.object(GitHubAdmin, "get_branch_protection")
    def test_audit_protection_all_protected(self, mock_get_prot, mock_branches, admin: GitHubAdmin):
        mock_branches.return_value = [
            {"repo": "x", "branch": "main"},
        ]
        mock_get_prot.return_value = {"enforce_admins": {"enabled": True}}

        results = admin.audit_protection()

        assert len(results) == 1
        assert results[0]["protected"] is True


# ---------------------------------------------------------------------------
# Owner / constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_default_owner(self):
        admin = GitHubAdmin()
        assert admin.owner == "smartmur"

    def test_custom_owner(self):
        admin = GitHubAdmin(owner="myorg")
        assert admin.owner == "myorg"


# ---------------------------------------------------------------------------
# Skill run.py subcommands (smoke tests via module import)
# ---------------------------------------------------------------------------


class TestSkillRunModule:
    def test_module_loads(self):
        """The skill run.py can be loaded as a module."""
        _spec.loader.exec_module(_run_mod)
        assert hasattr(_run_mod, "main")
        assert hasattr(_run_mod, "cmd_auth")
        assert hasattr(_run_mod, "cmd_repos")
        assert hasattr(_run_mod, "cmd_protect")
        assert hasattr(_run_mod, "cmd_audit")
