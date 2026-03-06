"""Tests for superpowers.release and superpowers.cli_release."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from superpowers.cli_release import release_group
from superpowers.release import (
    MigrationChecker,
    ReleaseError,
    ReleaseManager,
    _parse_commit_line,
    parse_semver,
    validate_semver,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed(stdout: str = "", stderr: str = "", rc: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# validate_semver / parse_semver
# ---------------------------------------------------------------------------


class TestValidateSemver:
    def test_valid_basic(self):
        assert validate_semver("1.2.3") is True

    def test_valid_with_pre(self):
        assert validate_semver("1.0.0-alpha.1") is True

    def test_valid_with_build(self):
        assert validate_semver("1.0.0+build.123") is True

    def test_valid_with_pre_and_build(self):
        assert validate_semver("0.1.0-rc.1+20260306") is True

    def test_valid_zero(self):
        assert validate_semver("0.0.0") is True

    def test_invalid_two_parts(self):
        assert validate_semver("1.2") is False

    def test_invalid_leading_v(self):
        assert validate_semver("v1.2.3") is False

    def test_invalid_letters(self):
        assert validate_semver("abc") is False

    def test_invalid_empty(self):
        assert validate_semver("") is False

    def test_invalid_leading_zero(self):
        assert validate_semver("01.2.3") is False


class TestParseSemver:
    def test_parse_basic(self):
        parts = parse_semver("1.2.3")
        assert parts["major"] == "1"
        assert parts["minor"] == "2"
        assert parts["patch"] == "3"
        assert parts["pre"] == ""
        assert parts["build"] == ""

    def test_parse_with_pre(self):
        parts = parse_semver("2.0.0-beta.1")
        assert parts["pre"] == "beta.1"

    def test_parse_invalid_raises(self):
        with pytest.raises(ReleaseError, match="Invalid semver"):
            parse_semver("not-a-version")


# ---------------------------------------------------------------------------
# _parse_commit_line
# ---------------------------------------------------------------------------


class TestParseCommitLine:
    def test_feat(self):
        ctype, msg = _parse_commit_line("feat: add new widget")
        assert ctype == "feat"
        assert msg == "add new widget"

    def test_fix_with_scope(self):
        ctype, msg = _parse_commit_line("fix(core): null pointer")
        assert ctype == "fix"
        assert msg == "null pointer"

    def test_breaking(self):
        ctype, msg = _parse_commit_line("feat!: remove old API")
        assert ctype == "feat"
        assert msg == "remove old API"

    def test_unconventional(self):
        ctype, msg = _parse_commit_line("random commit message")
        assert ctype == "other"
        assert msg == "random commit message"


# ---------------------------------------------------------------------------
# ReleaseManager
# ---------------------------------------------------------------------------


class TestReleaseManagerPrepare:
    @patch("superpowers.release._run_git")
    def test_prepare_valid(self, mock_git, tmp_path):
        # Create a minimal pyproject.toml
        (tmp_path / "pyproject.toml").write_text('version = "1.0.0"\n')

        # Mock git status --porcelain (clean)
        # Mock git describe --tags --abbrev=0 (last tag)
        # Mock git log
        def side_effect(args, **kwargs):
            if args[0] == "status":
                return _completed("")
            if args[0] == "describe":
                return _completed("v0.9.0")
            if args[0] == "log":
                return _completed("feat: new feature\nfix: bug fix\n")
            return _completed()

        mock_git.side_effect = side_effect

        rm = ReleaseManager(project_root=tmp_path)
        info = rm.prepare_release("1.0.0")

        assert info["version"] == "1.0.0"
        assert info["clean"] is True
        assert info["version_match"] is True
        assert info["ready"] is True
        assert "Features" in info["changelog"]

    def test_prepare_invalid_version(self, tmp_path):
        rm = ReleaseManager(project_root=tmp_path)
        with pytest.raises(ReleaseError, match="Invalid semver"):
            rm.prepare_release("bad")

    @patch("superpowers.release._run_git")
    def test_prepare_dirty_tree(self, mock_git, tmp_path):
        (tmp_path / "pyproject.toml").write_text('version = "1.0.0"\n')

        def side_effect(args, **kwargs):
            if args[0] == "status":
                return _completed(" M superpowers/cli.py")
            if args[0] == "describe":
                return _completed("", rc=1)
            if args[0] == "log":
                return _completed("")
            return _completed()

        mock_git.side_effect = side_effect

        rm = ReleaseManager(project_root=tmp_path)
        info = rm.prepare_release("1.0.0")
        assert info["clean"] is False
        assert info["ready"] is False


class TestBuildChangelog:
    @patch("superpowers.release._run_git")
    def test_grouped_output(self, mock_git, tmp_path):
        mock_git.return_value = _completed(
            "feat: add widget\nfeat: add button\nfix: null check\nchore: update deps\n"
        )
        rm = ReleaseManager(project_root=tmp_path)
        changelog = rm.build_changelog("v0.1.0", "HEAD")

        assert "### Features" in changelog
        assert "- add widget" in changelog
        assert "- add button" in changelog
        assert "### Bug Fixes" in changelog
        assert "- null check" in changelog
        assert "### Chores" in changelog

    @patch("superpowers.release._run_git")
    def test_empty_changelog(self, mock_git, tmp_path):
        mock_git.return_value = _completed("")
        rm = ReleaseManager(project_root=tmp_path)
        changelog = rm.build_changelog("v0.1.0", "HEAD")
        assert "No changes found" in changelog

    @patch("superpowers.release._run_git")
    def test_git_failure(self, mock_git, tmp_path):
        mock_git.return_value = _completed("", stderr="fatal: bad ref", rc=128)
        rm = ReleaseManager(project_root=tmp_path)
        with pytest.raises(ReleaseError, match="git log failed"):
            rm.build_changelog("v0.1.0", "HEAD")

    @patch("superpowers.release._run_git")
    def test_from_empty_tag(self, mock_git, tmp_path):
        mock_git.return_value = _completed("feat: initial\n")
        rm = ReleaseManager(project_root=tmp_path)
        changelog = rm.build_changelog("", "HEAD")
        # Verify git log was called with just HEAD (no range)
        call_args = mock_git.call_args[0][0]
        assert "..HEAD" not in " ".join(call_args)


class TestCreateTag:
    @patch("superpowers.release._run_git")
    def test_create_success(self, mock_git, tmp_path):
        mock_git.return_value = _completed()
        rm = ReleaseManager(project_root=tmp_path)
        tag = rm.create_tag("1.0.0", "Release v1.0.0")
        assert tag == "v1.0.0"
        call_args = mock_git.call_args[0][0]
        assert "tag" in call_args
        assert "-a" in call_args
        assert "v1.0.0" in call_args

    @patch("superpowers.release._run_git")
    def test_create_failure(self, mock_git, tmp_path):
        mock_git.return_value = _completed("", stderr="tag already exists", rc=1)
        rm = ReleaseManager(project_root=tmp_path)
        with pytest.raises(ReleaseError, match="Failed to create tag"):
            rm.create_tag("1.0.0")

    def test_create_invalid_version(self, tmp_path):
        rm = ReleaseManager(project_root=tmp_path)
        with pytest.raises(ReleaseError, match="Invalid semver"):
            rm.create_tag("nope")

    @patch("superpowers.release._run_git")
    def test_default_message(self, mock_git, tmp_path):
        mock_git.return_value = _completed()
        rm = ReleaseManager(project_root=tmp_path)
        rm.create_tag("2.0.0")
        call_args = mock_git.call_args[0][0]
        msg_idx = call_args.index("-m") + 1
        assert "Release v2.0.0" in call_args[msg_idx]


class TestVerifyRelease:
    @patch("superpowers.release._run_git")
    def test_verified(self, mock_git, tmp_path):
        (tmp_path / "pyproject.toml").write_text('version = "1.0.0"\n')

        def side_effect(args, **kwargs):
            if args[0] == "tag" and args[1] == "--list":
                return _completed("v1.0.0\n")
            return _completed()

        mock_git.side_effect = side_effect
        rm = ReleaseManager(project_root=tmp_path)
        info = rm.verify_release("1.0.0")
        assert info["verified"] is True
        assert info["tag_exists"] is True
        assert info["pyproject_match"] is True

    @patch("superpowers.release._run_git")
    def test_tag_missing(self, mock_git, tmp_path):
        (tmp_path / "pyproject.toml").write_text('version = "1.0.0"\n')

        mock_git.return_value = _completed("")
        rm = ReleaseManager(project_root=tmp_path)
        info = rm.verify_release("1.0.0")
        assert info["tag_exists"] is False
        assert info["verified"] is False

    @patch("superpowers.release._run_git")
    def test_version_mismatch(self, mock_git, tmp_path):
        (tmp_path / "pyproject.toml").write_text('version = "0.9.0"\n')

        def side_effect(args, **kwargs):
            if args[0] == "tag" and args[1] == "--list":
                return _completed("v1.0.0\n")
            return _completed()

        mock_git.side_effect = side_effect
        rm = ReleaseManager(project_root=tmp_path)
        info = rm.verify_release("1.0.0")
        assert info["pyproject_match"] is False
        assert info["verified"] is False

    def test_verify_invalid_version(self, tmp_path):
        rm = ReleaseManager(project_root=tmp_path)
        with pytest.raises(ReleaseError, match="Invalid semver"):
            rm.verify_release("xyz")


class TestRollbackRelease:
    @patch("superpowers.release._run_git")
    def test_rollback_existing_tag(self, mock_git, tmp_path):
        def side_effect(args, **kwargs):
            if args[0] == "tag" and args[1] == "--list":
                return _completed("v1.0.0\n")
            if args[0] == "tag" and args[1] == "-d":
                return _completed()
            return _completed()

        mock_git.side_effect = side_effect
        rm = ReleaseManager(project_root=tmp_path)
        info = rm.rollback_release("1.0.0")
        assert info["tag_deleted"] is True
        assert "git push origin :refs/tags/v1.0.0" in info["instructions"]

    @patch("superpowers.release._run_git")
    def test_rollback_no_tag(self, mock_git, tmp_path):
        mock_git.return_value = _completed("")
        rm = ReleaseManager(project_root=tmp_path)
        info = rm.rollback_release("1.0.0")
        assert info["tag_deleted"] is False

    def test_rollback_invalid_version(self, tmp_path):
        rm = ReleaseManager(project_root=tmp_path)
        with pytest.raises(ReleaseError, match="Invalid semver"):
            rm.rollback_release("bad")

    @patch("superpowers.release._run_git")
    def test_rollback_delete_fails(self, mock_git, tmp_path):
        def side_effect(args, **kwargs):
            if args[0] == "tag" and args[1] == "--list":
                return _completed("v1.0.0\n")
            if args[0] == "tag" and args[1] == "-d":
                return _completed("", stderr="error", rc=1)
            return _completed()

        mock_git.side_effect = side_effect
        rm = ReleaseManager(project_root=tmp_path)
        with pytest.raises(ReleaseError, match="Failed to delete tag"):
            rm.rollback_release("1.0.0")


# ---------------------------------------------------------------------------
# MigrationChecker
# ---------------------------------------------------------------------------


class TestMigrationChecker:
    @patch("superpowers.release._run_git")
    def test_no_breaking_changes(self, mock_git, tmp_path):
        mock_git.return_value = _completed("")
        mc = MigrationChecker(project_root=tmp_path)
        result = mc.check_breaking_changes("0.1.0", "0.2.0")
        assert result["has_breaking_changes"] is False
        assert result["removed_commands"] == []
        assert result["changed_configs"] == []
        assert result["removed_apis"] == []

    @patch("superpowers.release._run_git")
    def test_detect_removed_command(self, mock_git, tmp_path):
        diff_output = (
            '--- a/superpowers/cli_foo.py\n'
            '+++ b/superpowers/cli_foo.py\n'
            '-@click.group("old-cmd")\n'
            '+@click.group("new-cmd")\n'
        )

        def side_effect(args, **kwargs):
            if "cli.py" in " ".join(args):
                return _completed(diff_output)
            return _completed("")

        mock_git.side_effect = side_effect
        mc = MigrationChecker(project_root=tmp_path)
        result = mc.check_breaking_changes("0.1.0", "0.2.0")
        assert "old-cmd" in result["removed_commands"]
        assert result["has_breaking_changes"] is True

    @patch("superpowers.release._run_git")
    def test_detect_changed_config(self, mock_git, tmp_path):
        diff_output = (
            '--- a/superpowers/config.py\n'
            '+++ b/superpowers/config.py\n'
            '-    host = _env("OLD_HOST", "localhost")\n'
            '+    host = _env("NEW_HOST", "localhost")\n'
        )

        def side_effect(args, **kwargs):
            if "config.py" in " ".join(args):
                return _completed(diff_output)
            return _completed("")

        mock_git.side_effect = side_effect
        mc = MigrationChecker(project_root=tmp_path)
        result = mc.check_breaking_changes("0.1.0", "0.2.0")
        assert "OLD_HOST" in result["changed_configs"]

    @patch("superpowers.release._run_git")
    def test_detect_removed_api(self, mock_git, tmp_path):
        diff_output = (
            '--- a/superpowers/foo.py\n'
            '+++ b/superpowers/foo.py\n'
            '-class OldManager:\n'
            '-def old_helper(x):\n'
        )

        def side_effect(args, **kwargs):
            if "superpowers/*.py" in " ".join(args):
                return _completed(diff_output)
            return _completed("")

        mock_git.side_effect = side_effect
        mc = MigrationChecker(project_root=tmp_path)
        result = mc.check_breaking_changes("0.1.0", "0.2.0")
        assert "OldManager" in result["removed_apis"]
        assert "old_helper" in result["removed_apis"]

    @patch("superpowers.release._run_git")
    def test_private_apis_ignored(self, mock_git, tmp_path):
        diff_output = '-def _private_func():\n'

        def side_effect(args, **kwargs):
            if "superpowers/*.py" in " ".join(args):
                return _completed(diff_output)
            return _completed("")

        mock_git.side_effect = side_effect
        mc = MigrationChecker(project_root=tmp_path)
        result = mc.check_breaking_changes("0.1.0", "0.2.0")
        assert result["removed_apis"] == []

    @patch("superpowers.release._run_git")
    def test_generate_guide_no_breaking(self, mock_git, tmp_path):
        mock_git.return_value = _completed("")
        mc = MigrationChecker(project_root=tmp_path)
        guide = mc.generate_migration_guide("0.1.0", "0.2.0")
        assert "No breaking changes" in guide
        assert "drop-in upgrade" in guide

    @patch("superpowers.release._run_git")
    def test_generate_guide_with_breaking(self, mock_git, tmp_path):
        diff_cli = '-@click.group("removed-cmd")\n'
        diff_config = '-    x = _env("REMOVED_KEY")\n'

        def side_effect(args, **kwargs):
            joined = " ".join(args)
            if "cli.py" in joined:
                return _completed(diff_cli)
            if "config.py" in joined:
                return _completed(diff_config)
            return _completed("")

        mock_git.side_effect = side_effect
        mc = MigrationChecker(project_root=tmp_path)
        guide = mc.generate_migration_guide("0.1.0", "0.2.0")
        assert "WARNING: Breaking changes" in guide
        assert "removed-cmd" in guide
        assert "REMOVED_KEY" in guide
        assert "Rollback" in guide


# ---------------------------------------------------------------------------
# CLI (via CliRunner)
# ---------------------------------------------------------------------------


class TestCLI:
    def setup_method(self):
        self.runner = CliRunner()

    @patch("superpowers.cli_release.ReleaseManager")
    def test_prepare_success(self, MockRM):
        instance = MockRM.return_value
        instance.prepare_release.return_value = {
            "version": "1.0.0",
            "clean": True,
            "changelog": "### Features\n- stuff\n",
            "pyproject_version": "1.0.0",
            "version_match": True,
            "last_tag": "v0.9.0",
            "ready": True,
        }
        result = self.runner.invoke(release_group, ["prepare", "1.0.0"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    @patch("superpowers.cli_release.ReleaseManager")
    def test_prepare_error(self, MockRM):
        instance = MockRM.return_value
        instance.prepare_release.side_effect = ReleaseError("Invalid semver version: bad")
        result = self.runner.invoke(release_group, ["prepare", "bad"])
        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("superpowers.cli_release.ReleaseManager")
    def test_changelog(self, MockRM):
        instance = MockRM.return_value
        instance._get_last_tag.return_value = "v0.1.0"
        instance.build_changelog.return_value = "### Features\n- foo\n"
        result = self.runner.invoke(release_group, ["changelog"])
        assert result.exit_code == 0
        assert "Features" in result.output

    @patch("superpowers.cli_release.ReleaseManager")
    def test_tag_success(self, MockRM):
        instance = MockRM.return_value
        instance.create_tag.return_value = "v1.0.0"
        result = self.runner.invoke(release_group, ["tag", "1.0.0"])
        assert result.exit_code == 0
        assert "v1.0.0" in result.output

    @patch("superpowers.cli_release.ReleaseManager")
    def test_tag_error(self, MockRM):
        instance = MockRM.return_value
        instance.create_tag.side_effect = ReleaseError("Failed to create tag")
        result = self.runner.invoke(release_group, ["tag", "1.0.0"])
        assert result.exit_code == 1

    @patch("superpowers.cli_release.ReleaseManager")
    def test_verify_success(self, MockRM):
        instance = MockRM.return_value
        instance.verify_release.return_value = {
            "version": "1.0.0",
            "tag": "v1.0.0",
            "tag_exists": True,
            "pyproject_version": "1.0.0",
            "pyproject_match": True,
            "verified": True,
        }
        result = self.runner.invoke(release_group, ["verify", "1.0.0"])
        assert result.exit_code == 0

    @patch("superpowers.cli_release.ReleaseManager")
    def test_verify_failure(self, MockRM):
        instance = MockRM.return_value
        instance.verify_release.return_value = {
            "version": "1.0.0",
            "tag": "v1.0.0",
            "tag_exists": False,
            "pyproject_version": "0.9.0",
            "pyproject_match": False,
            "verified": False,
        }
        result = self.runner.invoke(release_group, ["verify", "1.0.0"])
        assert result.exit_code == 1

    @patch("superpowers.cli_release.ReleaseManager")
    def test_rollback_deleted(self, MockRM):
        instance = MockRM.return_value
        instance.rollback_release.return_value = {
            "version": "1.0.0",
            "tag": "v1.0.0",
            "tag_deleted": True,
            "instructions": "Deleted tag.\ngit push origin :refs/tags/v1.0.0",
        }
        result = self.runner.invoke(release_group, ["rollback", "1.0.0"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    @patch("superpowers.cli_release.ReleaseManager")
    def test_rollback_not_found(self, MockRM):
        instance = MockRM.return_value
        instance.rollback_release.return_value = {
            "version": "1.0.0",
            "tag": "v1.0.0",
            "tag_deleted": False,
            "instructions": "Tag not found.",
        }
        result = self.runner.invoke(release_group, ["rollback", "1.0.0"])
        assert result.exit_code == 0
        assert "not found" in result.output

    @patch("superpowers.cli_release.MigrationChecker")
    def test_migrate(self, MockMC):
        instance = MockMC.return_value
        instance.generate_migration_guide.return_value = "# Migration Guide\nNo breaking changes.\n"
        result = self.runner.invoke(release_group, ["migrate", "0.1.0", "0.2.0"])
        assert result.exit_code == 0
        assert "Migration Guide" in result.output


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_read_pyproject_no_file(self, tmp_path):
        rm = ReleaseManager(project_root=tmp_path)
        assert rm._read_pyproject_version() == ""

    def test_read_pyproject_no_version(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        rm = ReleaseManager(project_root=tmp_path)
        assert rm._read_pyproject_version() == ""

    @patch("superpowers.release._run_git")
    def test_get_last_tag_none(self, mock_git, tmp_path):
        mock_git.return_value = _completed("", rc=128)
        rm = ReleaseManager(project_root=tmp_path)
        assert rm._get_last_tag() is None

    @patch("superpowers.release._run_git")
    def test_git_diff_failure_returns_empty(self, mock_git, tmp_path):
        mock_git.return_value = _completed("", rc=1)
        mc = MigrationChecker(project_root=tmp_path)
        result = mc.check_breaking_changes("0.1.0", "0.2.0")
        assert result["has_breaking_changes"] is False
