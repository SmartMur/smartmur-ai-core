"""Tests for Phase E — Setup Wizard and Template Manager.

Covers:
- E1: SetupWizard prereq checking, env creation, vault init, run()
- E2: Telegram setup (mocked API calls)
- E3: TemplateManager init, diff, reset, upgrade
- E4: CLI integration smoke tests
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# =====================================================================
# E1: SetupWizard — prerequisite checking
# =====================================================================


class TestCheckPrereqs:
    """Test SetupWizard.check_prereqs()."""

    def test_returns_dict_of_bools(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(project_dir=tmp_path, data_dir=tmp_path / "data")
        results = wizard.check_prereqs()

        assert isinstance(results, dict)
        assert "python" in results
        assert "docker" in results
        assert "age" in results
        for v in results.values():
            assert isinstance(v, bool)

    def test_python_always_found(self, tmp_path):
        """The current Python interpreter should be detected."""
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(project_dir=tmp_path, data_dir=tmp_path / "data")
        results = wizard.check_prereqs()
        # We are running tests with Python so it must be found
        assert results["python"] is True

    def test_python_version_check(self, tmp_path):
        """Python version below minimum should report False."""
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(project_dir=tmp_path, data_dir=tmp_path / "data")

        with patch.object(sys, "version_info", (3, 10, 0, "final", 0)):
            results = wizard.check_prereqs()
            assert results["python"] is False

    def test_missing_tool_reports_false(self, tmp_path):
        """A tool that doesn't exist should return False."""
        from superpowers.setup_wizard import PREREQS, SetupWizard

        wizard = SetupWizard(project_dir=tmp_path, data_dir=tmp_path / "data")

        with patch.dict(
            PREREQS,
            {"fake-tool": ["nonexistent-binary-xyz", "--version"]},
            clear=False,
        ):
            results = wizard.check_prereqs()
            assert results["fake-tool"] is False

    def test_check_command_success(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        # "true" is a command that always succeeds
        assert SetupWizard._check_command(["true"]) is True

    def test_check_command_not_found(self):
        from superpowers.setup_wizard import SetupWizard

        assert SetupWizard._check_command(["nonexistent_xyz_123"]) is False


# =====================================================================
# E1: SetupWizard — .env creation
# =====================================================================


class TestCreateEnv:
    """Test SetupWizard.create_env()."""

    def _make_example(self, project_dir: Path) -> Path:
        """Write a minimal .env.example."""
        example = project_dir / ".env.example"
        example.write_text(
            "# Config\nREDIS_URL=redis://localhost:6379/0\nSLACK_BOT_TOKEN=\nSMTP_PORT=587\n"
        )
        return example

    def test_create_env_non_interactive_defaults(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        self._make_example(tmp_path)
        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        env_path = wizard.create_env()
        assert env_path.exists()
        content = env_path.read_text()
        assert "REDIS_URL=redis://localhost:6379/0" in content
        assert "SLACK_BOT_TOKEN=" in content
        assert "SMTP_PORT=587" in content

    def test_create_env_with_values_dict(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        self._make_example(tmp_path)
        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
            values={"SLACK_BOT_TOKEN": "xoxb-test-token"},
        )

        env_path = wizard.create_env()
        content = env_path.read_text()
        assert "SLACK_BOT_TOKEN=xoxb-test-token" in content
        # Other values keep defaults
        assert "REDIS_URL=redis://localhost:6379/0" in content

    def test_create_env_preserves_comments(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        self._make_example(tmp_path)
        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        env_path = wizard.create_env()
        content = env_path.read_text()
        assert "# Config" in content

    def test_create_env_file_permissions(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        self._make_example(tmp_path)
        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        env_path = wizard.create_env()
        mode = oct(env_path.stat().st_mode & 0o777)
        assert mode == "0o600"

    def test_create_env_custom_target(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        self._make_example(tmp_path)
        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        custom = tmp_path / "custom.env"
        env_path = wizard.create_env(target=custom)
        assert env_path == custom
        assert custom.exists()

    def test_create_env_missing_example_raises(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        with pytest.raises(FileNotFoundError):
            wizard.create_env()


# =====================================================================
# E1: SetupWizard — vault initialization
# =====================================================================


class TestInitVault:
    """Test SetupWizard.init_vault()."""

    def test_init_vault_no_age(self, tmp_path):
        """Without age-keygen, init_vault returns False."""
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
        )

        with patch("shutil.which", return_value=None):
            assert wizard.init_vault() is False

    def test_init_vault_with_age(self, tmp_path):
        """With age-keygen available, vault should be initialized."""
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
        )

        mock_vault = MagicMock()
        with (
            patch("superpowers.setup_wizard.shutil.which", return_value="/usr/bin/age-keygen"),
            patch("superpowers.vault.Vault", return_value=mock_vault),
        ):
            result = wizard.init_vault()
            assert result is True
            mock_vault.init.assert_called_once()


# =====================================================================
# E1: SetupWizard — run() orchestration
# =====================================================================


class TestWizardRun:
    """Test the full run() orchestration."""

    def test_run_non_interactive(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        # Create .env.example
        (tmp_path / ".env.example").write_text("REDIS_URL=redis://localhost:6379/0\n")

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        with patch("shutil.which", return_value=None):
            summary = wizard.run()

        assert "prereqs" in summary
        assert summary["data_dir"] == str(tmp_path / "data")
        assert summary["env_created"] is True
        assert (tmp_path / ".env").exists()

    def test_run_skips_existing_env(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        (tmp_path / ".env.example").write_text("KEY=val\n")
        (tmp_path / ".env").write_text("KEY=existing\n")

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        with patch("shutil.which", return_value=None):
            summary = wizard.run()

        assert summary["env_created"] is False
        # Original .env should be untouched
        assert (tmp_path / ".env").read_text() == "KEY=existing\n"

    def test_run_skips_vault_when_exists(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        (tmp_path / ".env.example").write_text("KEY=val\n")
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "vault.enc").write_text("encrypted")

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=data_dir,
            non_interactive=True,
        )

        summary = wizard.run()
        assert summary["vault_initialized"] is True

    def test_run_creates_data_dirs(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        (tmp_path / ".env.example").write_text("KEY=val\n")
        data_dir = tmp_path / "data"

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=data_dir,
            non_interactive=True,
        )

        with patch("shutil.which", return_value=None):
            wizard.run()

        assert data_dir.exists()
        assert (data_dir / "skills").is_dir()
        assert (data_dir / "cron").is_dir()
        assert (data_dir / "logs").is_dir()


# =====================================================================
# E2: Telegram setup
# =====================================================================


class TestTelegramSetup:
    """Test SetupWizard.setup_telegram()."""

    def test_no_token_returns_invalid(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        result = wizard.setup_telegram()
        assert result["valid"] is False
        assert result["bot_info"] is None

    def test_valid_token(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        fake_bot = {"id": 123, "username": "testbot", "is_bot": True}
        with patch.object(SetupWizard, "_validate_telegram_token", return_value=fake_bot):
            result = wizard.setup_telegram(bot_token="123:ABC")

        assert result["valid"] is True
        assert result["bot_info"]["username"] == "testbot"
        assert result["config"]["TELEGRAM_BOT_TOKEN"] == "123:ABC"
        assert result["config"]["TELEGRAM_MODE"] == "polling"

    def test_with_webhook(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        fake_bot = {"id": 123, "username": "testbot", "is_bot": True}
        with (
            patch.object(SetupWizard, "_validate_telegram_token", return_value=fake_bot),
            patch.object(SetupWizard, "_set_telegram_webhook", return_value=True),
        ):
            result = wizard.setup_telegram(
                bot_token="123:ABC",
                webhook_url="https://example.com/webhook",
            )

        assert result["webhook_set"] is True
        assert result["config"]["TELEGRAM_MODE"] == "webhook"
        assert result["config"]["TELEGRAM_WEBHOOK_URL"] == "https://example.com/webhook"

    def test_with_allowed_chat_ids(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        with patch.object(
            SetupWizard, "_validate_telegram_token", return_value={"username": "bot"}
        ):
            result = wizard.setup_telegram(
                bot_token="123:ABC",
                allowed_chat_ids="111,222,333",
            )

        assert result["config"]["ALLOWED_CHAT_IDS"] == "111,222,333"

    def test_invalid_token(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        with patch.object(SetupWizard, "_validate_telegram_token", return_value=None):
            result = wizard.setup_telegram(bot_token="bad-token")

        assert result["valid"] is False
        assert result["webhook_set"] is False

    def test_token_from_values_dict(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
            values={"TELEGRAM_BOT_TOKEN": "from-values"},
        )

        with patch.object(
            SetupWizard,
            "_validate_telegram_token",
            return_value={"username": "vbot"},
        ):
            result = wizard.setup_telegram()

        assert result["valid"] is True
        assert result["config"]["TELEGRAM_BOT_TOKEN"] == "from-values"

    def test_print_instructions_no_error(self, tmp_path):
        """Smoke test: print_telegram_instructions should not raise."""
        from superpowers.setup_wizard import SetupWizard

        # Just ensure it does not error out
        SetupWizard.print_telegram_instructions()


# =====================================================================
# E3: TemplateManager — init
# =====================================================================


class TestTemplateInit:
    """Test TemplateManager.init()."""

    def _setup_project(self, tmp_path: Path) -> tuple[Path, dict[str, str]]:
        """Create a minimal project with template source files."""
        project = tmp_path / "project"
        project.mkdir()

        # Create source templates
        (project / "workflows").mkdir()
        (project / "workflows" / "deploy.yaml").write_text("name: deploy\nversion: 1\n")
        (project / "docker-compose.yaml").write_text("services:\n  redis: {}\n")

        sources = {
            "workflows/deploy.yaml": "workflows/deploy.yaml",
            "docker-compose.yaml": "docker-compose.yaml",
        }
        return project, sources

    def test_init_installs_templates(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project, sources = self._setup_project(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources=sources,
        )

        installed = tm.init()
        # All source files exist at dest already (src == dest), so they get tracked
        assert len(installed) == 2
        assert "workflows/deploy.yaml" in installed
        assert "docker-compose.yaml" in installed

        # Manifest should be written
        manifest_path = data_dir / "templates.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert "workflows/deploy.yaml" in manifest
        assert "docker-compose.yaml" in manifest

    def test_init_skips_already_tracked(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project, sources = self._setup_project(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources=sources,
        )

        # First init
        tm.init()
        # Second init should install nothing new
        installed = tm.init()
        assert installed == []

    def test_init_copies_missing_dest(self, tmp_path):
        """If source exists but dest does not, init copies it."""
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        src_dir = project / "shipped"
        src_dir.mkdir()
        (src_dir / "config.yaml").write_text("key: value\n")

        # Dest file doesn't exist yet
        sources = {"config.yaml": "shipped/config.yaml"}
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources=sources,
        )

        installed = tm.init()
        assert "config.yaml" in installed
        assert (project / "config.yaml").exists()
        assert (project / "config.yaml").read_text() == "key: value\n"


# =====================================================================
# E3: TemplateManager — list
# =====================================================================


class TestTemplateList:
    """Test TemplateManager.list_templates()."""

    def test_list_untracked(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()
        (project / "file.yaml").write_text("data\n")

        tm = TemplateManager(
            project_dir=project,
            data_dir=tmp_path / "data",
            template_sources={"file.yaml": "file.yaml"},
        )

        templates = tm.list_templates()
        assert len(templates) == 1
        assert templates[0]["status"] == "untracked"

    def test_list_current(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()
        (project / "file.yaml").write_text("data\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"file.yaml": "file.yaml"},
        )

        tm.init()
        templates = tm.list_templates()
        assert templates[0]["status"] == "current"

    def test_list_modified(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()
        (project / "file.yaml").write_text("original\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"file.yaml": "file.yaml"},
        )

        tm.init()
        # Modify the file after tracking
        (project / "file.yaml").write_text("modified\n")

        templates = tm.list_templates()
        assert templates[0]["status"] == "modified"

    def test_list_missing(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()
        (project / "file.yaml").write_text("data\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"file.yaml": "file.yaml"},
        )

        tm.init()
        # Remove the file
        (project / "file.yaml").unlink()

        templates = tm.list_templates()
        assert templates[0]["status"] == "missing"


# =====================================================================
# E3: TemplateManager — diff
# =====================================================================


class TestTemplateDiff:
    """Test TemplateManager.diff()."""

    def test_diff_no_changes(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()
        (project / "file.yaml").write_text("data\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"file.yaml": "file.yaml"},
        )

        tm.init()
        diffs = tm.diff()
        assert diffs["file.yaml"] == ""

    def test_diff_with_changes(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        # Source stays original
        shipped = project / "shipped"
        shipped.mkdir()
        (shipped / "config.yaml").write_text("key: original\n")

        # Dest is modified
        (project / "config.yaml").write_text("key: modified\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"config.yaml": "shipped/config.yaml"},
        )

        tm.init()
        diffs = tm.diff("config.yaml")
        assert "config.yaml" in diffs
        assert "-key: original" in diffs["config.yaml"]
        assert "+key: modified" in diffs["config.yaml"]

    def test_diff_missing_file(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()
        (project / "file.yaml").write_text("data\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"file.yaml": "file.yaml"},
        )

        tm.init()
        (project / "file.yaml").unlink()
        diffs = tm.diff("file.yaml")
        assert diffs["file.yaml"] == ""

    def test_diff_specific_template(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()
        (project / "a.yaml").write_text("a\n")
        (project / "b.yaml").write_text("b\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={
                "a.yaml": "a.yaml",
                "b.yaml": "b.yaml",
            },
        )

        tm.init()
        diffs = tm.diff("a.yaml")
        assert "a.yaml" in diffs
        assert "b.yaml" not in diffs


# =====================================================================
# E3: TemplateManager — reset
# =====================================================================


class TestTemplateReset:
    """Test TemplateManager.reset()."""

    def test_reset_restores_shipped(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        shipped = project / "shipped"
        shipped.mkdir()
        (shipped / "config.yaml").write_text("original\n")
        (project / "config.yaml").write_text("modified by user\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"config.yaml": "shipped/config.yaml"},
        )

        tm.init()
        # Verify it's still the user's version
        assert (project / "config.yaml").read_text() == "modified by user\n"

        ok = tm.reset("config.yaml")
        assert ok is True
        assert (project / "config.yaml").read_text() == "original\n"

    def test_reset_creates_backup(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        shipped = project / "shipped"
        shipped.mkdir()
        (shipped / "config.yaml").write_text("original\n")
        (project / "config.yaml").write_text("user changes\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"config.yaml": "shipped/config.yaml"},
        )

        tm.init()
        tm.reset("config.yaml")

        # Backup should exist
        backup = project / "config.yaml.bak"
        assert backup.exists()
        assert backup.read_text() == "user changes\n"

    def test_reset_unknown_template(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        tm = TemplateManager(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            template_sources={},
        )

        assert tm.reset("nonexistent") is False

    def test_reset_missing_source(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=tmp_path / "data",
            template_sources={"gone.yaml": "gone.yaml"},
        )

        assert tm.reset("gone.yaml") is False


# =====================================================================
# E3: TemplateManager — upgrade
# =====================================================================


class TestTemplateUpgrade:
    """Test TemplateManager.upgrade()."""

    def test_upgrade_unmodified_file(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        shipped = project / "shipped"
        shipped.mkdir()
        (shipped / "file.yaml").write_text("v1\n")
        (project / "file.yaml").write_text("v1\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"file.yaml": "shipped/file.yaml"},
        )

        tm.init()

        actions = tm.upgrade()
        assert actions["file.yaml"] == "updated"

    def test_upgrade_modified_file_creates_backup(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        shipped = project / "shipped"
        shipped.mkdir()
        (shipped / "config.yaml").write_text("v1\n")
        (project / "config.yaml").write_text("v1\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"config.yaml": "shipped/config.yaml"},
        )

        tm.init()

        # User modifies the file
        (project / "config.yaml").write_text("user modified v1\n")

        # Ship new version
        (shipped / "config.yaml").write_text("v2\n")

        actions = tm.upgrade()
        assert actions["config.yaml"] == "backup_and_updated"

        # File should now be the new shipped version
        assert (project / "config.yaml").read_text() == "v2\n"

        # Backup should exist
        backups = list(project.glob("config.yaml.*.bak"))
        assert len(backups) == 1
        assert backups[0].read_text() == "user modified v1\n"

    def test_upgrade_skips_removed_file(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        shipped = project / "shipped"
        shipped.mkdir()
        (shipped / "file.yaml").write_text("data\n")
        (project / "file.yaml").write_text("data\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"file.yaml": "shipped/file.yaml"},
        )

        tm.init()
        # Remove the destination file (user intentionally deleted)
        (project / "file.yaml").unlink()

        actions = tm.upgrade()
        assert actions["file.yaml"] == "skipped"

    def test_upgrade_missing_source(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"gone.yaml": "gone.yaml"},
        )

        actions = tm.upgrade()
        assert actions["gone.yaml"] == "missing_source"

    def test_upgrade_updates_manifest(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        project = tmp_path / "project"
        project.mkdir()

        shipped = project / "shipped"
        shipped.mkdir()
        (shipped / "file.yaml").write_text("v1\n")
        (project / "file.yaml").write_text("v1\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        tm = TemplateManager(
            project_dir=project,
            data_dir=data_dir,
            template_sources={"file.yaml": "shipped/file.yaml"},
        )

        tm.init()
        manifest_before = json.loads((data_dir / "templates.json").read_text())
        old_hash = manifest_before["file.yaml"]["shipped_hash"]

        # Change source content (simulate new release)
        (shipped / "file.yaml").write_text("v2\n")
        tm.upgrade()

        manifest_after = json.loads((data_dir / "templates.json").read_text())
        new_hash = manifest_after["file.yaml"]["shipped_hash"]
        assert new_hash != old_hash


# =====================================================================
# E3: TemplateManager — manifest persistence
# =====================================================================


class TestManifestPersistence:
    """Test manifest load/save edge cases."""

    def test_load_nonexistent_manifest(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        tm = TemplateManager(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            template_sources={},
        )

        manifest = tm._load_manifest()
        assert manifest == {}

    def test_load_corrupted_manifest(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "templates.json").write_text("not json{{{")

        tm = TemplateManager(
            project_dir=tmp_path,
            data_dir=data_dir,
            template_sources={},
        )

        manifest = tm._load_manifest()
        assert manifest == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        from superpowers.template_manager import TemplateManager

        data_dir = tmp_path / "nested" / "dir"

        tm = TemplateManager(
            project_dir=tmp_path,
            data_dir=data_dir,
            template_sources={},
        )

        tm._save_manifest({"test": {"key": "value"}})
        assert (data_dir / "templates.json").exists()


# =====================================================================
# E4: CLI integration
# =====================================================================


class TestCLISetup:
    """Smoke tests for the setup CLI commands."""

    def test_setup_group_exists(self):
        from superpowers.cli import main

        # "setup" should be a registered command/group
        assert "setup" in [cmd for cmd in main.commands]

    def test_template_group_exists(self):
        from superpowers.cli import main

        assert "template" in [cmd for cmd in main.commands]

    def test_setup_subcommands(self):
        from superpowers.cli_setup import setup_group

        subcommands = list(setup_group.commands.keys())
        assert "run" in subcommands
        assert "check" in subcommands
        assert "env" in subcommands
        assert "vault" in subcommands
        assert "telegram" in subcommands

    def test_template_subcommands(self):
        from superpowers.cli_template import template_group

        subcommands = list(template_group.commands.keys())
        assert "init" in subcommands
        assert "list" in subcommands
        assert "diff" in subcommands
        assert "reset" in subcommands
        assert "upgrade" in subcommands


class TestCLISetupInvocation:
    """Test CLI command invocation via click test runner."""

    def test_setup_check_runs(self):
        from click.testing import CliRunner

        from superpowers.cli_setup import setup_group

        runner = CliRunner()
        result = runner.invoke(setup_group, ["check"])
        assert result.exit_code == 0
        assert "python" in result.output.lower()

    def test_setup_env_missing_example(self, tmp_path):
        from click.testing import CliRunner

        from superpowers.cli_setup import setup_group

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(setup_group, ["env", "--non-interactive"])
            assert result.exit_code == 1

    def test_setup_env_creates_file(self, tmp_path):
        from click.testing import CliRunner

        from superpowers.cli_setup import setup_group

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            Path(td, ".env.example").write_text("KEY=default\n")
            result = runner.invoke(setup_group, ["env", "--non-interactive"])
            assert result.exit_code == 0
            assert Path(td, ".env").exists()

    def test_template_list_runs(self):
        from click.testing import CliRunner

        from superpowers.cli_template import template_group

        runner = CliRunner()
        result = runner.invoke(template_group, ["list"])
        # Should run without error even with no tracked templates
        assert result.exit_code == 0


# =====================================================================
# Edge cases and regression tests
# =====================================================================


class TestEdgeCases:
    """Additional edge case and regression tests."""

    def test_env_with_quoted_values(self, tmp_path):
        """Values with quotes in .env.example should be handled."""
        from superpowers.setup_wizard import SetupWizard

        example = tmp_path / ".env.example"
        example.write_text("PASS=\"my secret\"\nKEY='quoted'\n")

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        env_path = wizard.create_env()
        content = env_path.read_text()
        assert "PASS=my secret" in content
        assert "KEY=quoted" in content

    def test_env_with_empty_lines_and_comments(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        example = tmp_path / ".env.example"
        example.write_text("# Header\n\n# Section\nKEY=val\n\n# Footer\n")

        wizard = SetupWizard(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            non_interactive=True,
        )

        env_path = wizard.create_env()
        content = env_path.read_text()
        assert "# Header" in content
        assert "# Section" in content
        assert "KEY=val" in content

    def test_template_sha256_consistency(self, tmp_path):
        """Same content should always produce the same hash."""
        from superpowers.template_manager import _sha256

        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("identical content\n")
        f2.write_text("identical content\n")

        assert _sha256(f1) == _sha256(f2)

    def test_template_sha256_different(self, tmp_path):
        from superpowers.template_manager import _sha256

        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content a\n")
        f2.write_text("content b\n")

        assert _sha256(f1) != _sha256(f2)

    def test_wizard_ensure_dirs(self, tmp_path):
        from superpowers.setup_wizard import SetupWizard

        data_dir = tmp_path / "fresh"
        wizard = SetupWizard(project_dir=tmp_path, data_dir=data_dir)
        wizard.ensure_dirs()

        assert data_dir.exists()
        assert (data_dir / "skills").is_dir()
        assert (data_dir / "cron").is_dir()
        assert (data_dir / "vault").is_dir()
        assert (data_dir / "logs").is_dir()
        assert (data_dir / "browser" / "profiles").is_dir()

    def test_wizard_defaults(self):
        """SetupWizard with no args should not raise."""
        from superpowers.setup_wizard import SetupWizard

        wizard = SetupWizard()
        assert wizard.project_dir is not None
        assert wizard.data_dir is not None
        assert wizard.non_interactive is False
        assert wizard.values == {}
