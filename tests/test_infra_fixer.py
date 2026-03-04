"""Tests for the Infra Fixer — general Docker infrastructure monitor."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from superpowers.infra_fixer import (
    CRASH_LOOP_THRESHOLD,
    KNOWN_PROJECTS,
    PLACEHOLDER_PATTERNS,
    ContainerInfo,
    InfraFixer,
    InfraIssue,
    InfraReport,
)

# ---------------------------------------------------------------------------
# TestContainerInfo
# ---------------------------------------------------------------------------


class TestContainerInfo:
    """Tests for ContainerInfo dataclass."""

    def test_defaults(self):
        c = ContainerInfo()
        assert c.name == ""
        assert c.project == ""
        assert c.image == ""
        assert c.status == ""
        assert c.running is False
        assert c.exit_code == 0
        assert c.restart_count == 0
        assert c.health == ""
        assert c.started_at == ""

    def test_to_dict(self):
        c = ContainerInfo(name="redis", project="myapp", running=True, health="healthy")
        d = c.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "redis"
        assert d["project"] == "myapp"
        assert d["running"] is True
        assert d["health"] == "healthy"
        assert d["exit_code"] == 0


# ---------------------------------------------------------------------------
# TestInfraIssue
# ---------------------------------------------------------------------------


class TestInfraIssue:
    """Tests for InfraIssue dataclass."""

    def test_create(self):
        issue = InfraIssue(
            severity="critical",
            container="cloudflared",
            project="cloudflared",
            issue="Crash loop: 10 restarts",
            suggestion="Check logs",
        )
        assert issue.severity == "critical"
        assert issue.container == "cloudflared"
        assert issue.project == "cloudflared"
        assert issue.issue == "Crash loop: 10 restarts"
        assert issue.suggestion == "Check logs"

    def test_to_dict(self):
        issue = InfraIssue(
            severity="warning",
            container="redis",
            project="myapp",
            issue="Container unhealthy",
        )
        d = issue.to_dict()
        assert isinstance(d, dict)
        assert d["severity"] == "warning"
        assert d["container"] == "redis"
        assert d["suggestion"] == ""


# ---------------------------------------------------------------------------
# TestInfraReport
# ---------------------------------------------------------------------------


class TestInfraReport:
    """Tests for InfraReport dataclass."""

    def test_empty_report_is_healthy(self):
        report = InfraReport()
        assert report.status == "healthy"
        assert report.critical_count == 0
        assert report.warning_count == 0

    def test_counts_work(self):
        report = InfraReport(
            containers_total=10,
            containers_running=8,
            containers_stopped=2,
            containers_unhealthy=1,
            projects_total=3,
        )
        assert report.containers_total == 10
        assert report.containers_running == 8
        assert report.containers_stopped == 2
        assert report.containers_unhealthy == 1
        assert report.projects_total == 3

    def test_status_healthy(self):
        report = InfraReport(
            issues=[
                InfraIssue(severity="info", container="x", project="y", issue="disk usage"),
            ]
        )
        assert report.status == "healthy"

    def test_status_degraded(self):
        report = InfraReport(
            issues=[
                InfraIssue(severity="warning", container="x", project="y", issue="stopped"),
            ]
        )
        assert report.status == "degraded"
        assert report.warning_count == 1
        assert report.critical_count == 0

    def test_status_down(self):
        report = InfraReport(
            issues=[
                InfraIssue(severity="critical", container="x", project="y", issue="crash loop"),
                InfraIssue(severity="warning", container="z", project="y", issue="stopped"),
            ]
        )
        assert report.status == "down"
        assert report.critical_count == 1
        assert report.warning_count == 1

    def test_to_dict(self):
        report = InfraReport(
            containers_total=5,
            containers_running=4,
            containers_stopped=1,
            issues=[
                InfraIssue(severity="warning", container="a", project="b", issue="stopped"),
            ],
            containers=[
                ContainerInfo(name="a", project="b", running=False),
            ],
        )
        d = report.to_dict()
        assert d["status"] == "degraded"
        assert d["containers_total"] == 5
        assert len(d["issues"]) == 1
        assert len(d["containers"]) == 1
        assert d["summary"]["warning"] == 1
        assert d["summary"]["critical"] == 0
        assert d["summary"]["info"] == 0

    def test_telegram_summary_clean(self):
        report = InfraReport(
            containers_total=10,
            containers_running=10,
            duration_seconds=1.5,
        )
        summary = report.to_telegram_summary()
        assert "OK" in summary
        assert "HEALTHY" in summary
        assert "10/10" in summary
        assert "1.5s" in summary

    def test_telegram_summary_with_issues(self):
        report = InfraReport(
            containers_total=10,
            containers_running=8,
            containers_unhealthy=1,
            duration_seconds=2.3,
            issues=[
                InfraIssue(
                    severity="critical", container="cf", project="cloudflared", issue="crash loop"
                ),
                InfraIssue(severity="warning", container="redis", project="app", issue="stopped"),
            ],
            actions_taken=["Stopped crash-looping container: cf"],
        )
        summary = report.to_telegram_summary()
        assert "DOWN" in summary
        assert "1 critical" in summary
        assert "1 warning" in summary
        assert "crash loop" in summary
        assert "Actions:" in summary


# ---------------------------------------------------------------------------
# TestPlaceholderPatterns
# ---------------------------------------------------------------------------


class TestPlaceholderPatterns:
    """Tests for PLACEHOLDER_PATTERNS regexes."""

    def test_your_xxx_here(self):
        pat = PLACEHOLDER_PATTERNS[0]
        assert pat.search("your_token_here")
        assert pat.search("YOUR_PASSWORD_HERE")
        assert not pat.search("real_value_123")

    def test_changeme(self):
        pat = PLACEHOLDER_PATTERNS[1]
        assert pat.search("changeme")
        assert pat.search("CHANGEME")
        assert not pat.search("mypassword")

    def test_angle_bracket_placeholder(self):
        pat = PLACEHOLDER_PATTERNS[2]
        assert pat.search("<your-token>")
        assert pat.search("<your_api_key>")
        assert not pat.search("real-token-value")

    def test_no_false_positive_on_normal_values(self):
        for pat in PLACEHOLDER_PATTERNS:
            assert not pat.search("sk-abc123def456")
            assert not pat.search("192.168.1.1")
            assert not pat.search("redis://localhost:6379")


# ---------------------------------------------------------------------------
# TestCheckContainerHealth
# ---------------------------------------------------------------------------


class TestCheckContainerHealth:
    """Tests for InfraFixer.check_container_health."""

    def setup_method(self):
        self.fixer = InfraFixer(projects={})

    def test_detect_crash_loop(self):
        containers = [
            ContainerInfo(
                name="cloudflared",
                project="cloudflared",
                restart_count=CRASH_LOOP_THRESHOLD + 1,
                exit_code=255,
            ),
        ]
        issues = self.fixer.check_container_health(containers)
        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert "crash loop" in issues[0].issue.lower()
        assert "255" in issues[0].issue

    def test_detect_unhealthy(self):
        containers = [
            ContainerInfo(
                name="webapp",
                project="myapp",
                running=True,
                health="unhealthy",
            ),
        ]
        issues = self.fixer.check_container_health(containers)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "healthcheck" in issues[0].issue.lower()

    def test_detect_restarting(self):
        containers = [
            ContainerInfo(
                name="worker",
                project="myapp",
                status="Restarting (1) 5 seconds ago",
                exit_code=1,
                restart_count=2,
            ),
        ]
        issues = self.fixer.check_container_health(containers)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "restarting" in issues[0].issue.lower()

    def test_no_issue_for_healthy(self):
        containers = [
            ContainerInfo(
                name="redis",
                project="myapp",
                running=True,
                status="Up 2 hours",
                health="healthy",
            ),
        ]
        issues = self.fixer.check_container_health(containers)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# TestCheckExpectedRunning
# ---------------------------------------------------------------------------


class TestCheckExpectedRunning:
    """Tests for InfraFixer.check_expected_running."""

    def test_all_expected_running(self):
        projects = {
            "myapp": {
                "compose_dir": "/tmp/myapp",
                "expected_running": ["redis", "web"],
            },
        }
        fixer = InfraFixer(projects=projects)
        containers = [
            ContainerInfo(name="redis", project="myapp", running=True),
            ContainerInfo(name="web", project="myapp", running=True),
        ]
        issues = fixer.check_expected_running(containers)
        assert len(issues) == 0

    def test_missing_expected_warning(self):
        projects = {
            "myapp": {
                "compose_dir": "/tmp/myapp",
                "expected_running": ["redis", "web"],
            },
        }
        fixer = InfraFixer(projects=projects)
        containers = [
            ContainerInfo(name="redis", project="myapp", running=True),
            # "web" is not present at all
        ]
        issues = fixer.check_expected_running(containers)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].container == "web"
        assert "not found" in issues[0].issue.lower()

    def test_stopped_expected_warning_with_compose_dir(self):
        projects = {
            "myapp": {
                "compose_dir": "/tmp/myapp",
                "expected_running": ["redis"],
            },
        }
        fixer = InfraFixer(projects=projects)
        containers = [
            ContainerInfo(name="redis", project="myapp", running=False, exit_code=137),
        ]
        issues = fixer.check_expected_running(containers)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "stopped" in issues[0].issue.lower()
        assert "137" in issues[0].issue
        assert "/tmp/myapp" in issues[0].suggestion


# ---------------------------------------------------------------------------
# TestCheckEnvFiles
# ---------------------------------------------------------------------------


class TestCheckEnvFiles:
    """Tests for InfraFixer.check_env_files."""

    def test_no_placeholder_clean(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=sk-real-key-123\nDB_HOST=localhost\n")
        projects = {"test": {"compose_dir": str(tmp_path), "expected_running": []}}
        fixer = InfraFixer(projects=projects)
        issues = fixer.check_env_files()
        assert len(issues) == 0

    def test_placeholder_detected_critical(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=your_token_here\n")
        projects = {"test": {"compose_dir": str(tmp_path), "expected_running": []}}
        fixer = InfraFixer(projects=projects)
        issues = fixer.check_env_files()
        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert "API_KEY" in issues[0].issue

    def test_missing_env_skip(self, tmp_path):
        # No .env file in tmp_path
        projects = {"test": {"compose_dir": str(tmp_path), "expected_running": []}}
        fixer = InfraFixer(projects=projects)
        issues = fixer.check_env_files()
        assert len(issues) == 0

    def test_comments_ignored(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# API_KEY=your_token_here\nREAL_KEY=abc123\n\n# This is a comment\n")
        projects = {"test": {"compose_dir": str(tmp_path), "expected_running": []}}
        fixer = InfraFixer(projects=projects)
        issues = fixer.check_env_files()
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# TestApplyFixes
# ---------------------------------------------------------------------------


class TestApplyFixes:
    """Tests for InfraFixer.apply_fixes."""

    def setup_method(self):
        self.fixer = InfraFixer(
            projects={
                "myapp": {"compose_dir": "/tmp/myapp", "expected_running": ["redis"]},
            }
        )

    @patch.object(InfraFixer, "_run_cmd")
    def test_stops_crash_looping_container(self, mock_cmd):
        mock_cmd.return_value = MagicMock(returncode=0)
        containers = [
            ContainerInfo(name="cf", project="cloudflared", restart_count=10),
        ]
        issues = [
            InfraIssue(
                severity="critical",
                container="cf",
                project="cloudflared",
                issue="Crash loop: 10 restarts, exit code 255",
            ),
        ]
        actions = self.fixer.apply_fixes(containers, issues)
        assert any("Stopped crash-looping" in a for a in actions)
        mock_cmd.assert_any_call(["docker", "stop", "cf"])

    @patch.object(InfraFixer, "_run_cmd")
    def test_does_not_restart_crash_loop(self, mock_cmd):
        """If a container is both crash-looping and expected-stopped, don't restart it."""
        mock_cmd.return_value = MagicMock(returncode=0)
        containers = [
            ContainerInfo(name="redis", project="myapp", restart_count=10),
        ]
        issues = [
            InfraIssue(
                severity="critical",
                container="redis",
                project="myapp",
                issue="Crash loop: 10 restarts, exit code 1",
            ),
            InfraIssue(
                severity="warning",
                container="redis",
                project="myapp",
                issue="Expected container is stopped (exit code 1)",
            ),
        ]
        actions = self.fixer.apply_fixes(containers, issues)
        # Should stop it but NOT restart it
        assert any("Stopped crash-looping" in a for a in actions)
        assert not any("Restarted" in a for a in actions)

    @patch.object(InfraFixer, "_run_cmd")
    def test_restarts_stopped_expected(self, mock_cmd):
        mock_cmd.return_value = MagicMock(returncode=0)
        containers = [
            ContainerInfo(name="redis", project="myapp", running=False, exit_code=0),
        ]
        issues = [
            InfraIssue(
                severity="warning",
                container="redis",
                project="myapp",
                issue="Expected container is stopped (exit code 0)",
            ),
        ]
        actions = self.fixer.apply_fixes(containers, issues)
        assert any("Restarted" in a for a in actions)

    def test_no_action_when_healthy(self):
        containers = [
            ContainerInfo(name="redis", project="myapp", running=True),
        ]
        issues = []
        actions = self.fixer.apply_fixes(containers, issues)
        assert len(actions) == 0


# ---------------------------------------------------------------------------
# TestSaveReport
# ---------------------------------------------------------------------------


class TestSaveReport:
    """Tests for InfraFixer.save_report."""

    @patch("superpowers.infra_fixer.get_data_dir")
    def test_saves_latest_json(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path
        fixer = InfraFixer(projects={})
        report = InfraReport(containers_total=5, containers_running=5)
        result = fixer.save_report(report)
        assert result.name == "latest.json"
        assert result.exists()
        data = json.loads(result.read_text())
        assert data["containers_total"] == 5
        assert data["status"] == "healthy"

    @patch("superpowers.infra_fixer.get_data_dir")
    def test_creates_incident_log_on_issues(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path
        fixer = InfraFixer(projects={})
        report = InfraReport(
            issues=[
                InfraIssue(severity="warning", container="x", project="y", issue="stopped"),
            ],
        )
        fixer.save_report(report)
        incident_log = tmp_path / "infra-fixer" / "incident-log.jsonl"
        assert incident_log.exists()
        lines = incident_log.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["status"] == "degraded"
        assert len(entry["issues"]) == 1

    @patch("superpowers.infra_fixer.get_data_dir")
    def test_no_incident_log_when_clean(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path
        fixer = InfraFixer(projects={})
        report = InfraReport(containers_total=5, containers_running=5)
        fixer.save_report(report)
        incident_log = tmp_path / "infra-fixer" / "incident-log.jsonl"
        assert not incident_log.exists()


# ---------------------------------------------------------------------------
# TestRunCheck
# ---------------------------------------------------------------------------


class TestRunCheck:
    """Tests for InfraFixer.run_check (integration-style with mocks)."""

    @patch.object(InfraFixer, "check_disk_usage", return_value=[])
    @patch.object(InfraFixer, "check_env_files", return_value=[])
    @patch.object(InfraFixer, "check_expected_running", return_value=[])
    @patch.object(InfraFixer, "check_container_health", return_value=[])
    @patch.object(InfraFixer, "apply_fixes", return_value=[])
    @patch.object(InfraFixer, "get_all_containers")
    def test_full_run_returns_report(
        self, mock_containers, mock_fixes, mock_health, mock_expected, mock_env, mock_disk
    ):
        mock_containers.return_value = [
            ContainerInfo(name="redis", project="myapp", running=True),
            ContainerInfo(name="web", project="myapp", running=True),
        ]
        fixer = InfraFixer(projects={})
        report = fixer.run_check()
        assert isinstance(report, InfraReport)
        assert report.containers_total == 2
        assert report.containers_running == 2
        assert report.status == "healthy"
        assert report.duration_seconds >= 0
        mock_fixes.assert_called_once()

    @patch.object(InfraFixer, "check_disk_usage", return_value=[])
    @patch.object(InfraFixer, "check_env_files", return_value=[])
    @patch.object(InfraFixer, "check_expected_running", return_value=[])
    @patch.object(InfraFixer, "check_container_health", return_value=[])
    @patch.object(InfraFixer, "apply_fixes", return_value=[])
    @patch.object(InfraFixer, "get_all_containers")
    def test_auto_fix_false_skips_fixes(
        self, mock_containers, mock_fixes, mock_health, mock_expected, mock_env, mock_disk
    ):
        mock_containers.return_value = []
        fixer = InfraFixer(projects={})
        report = fixer.run_check(auto_fix=False)
        assert isinstance(report, InfraReport)
        mock_fixes.assert_not_called()

    @patch.object(InfraFixer, "get_all_containers")
    def test_handles_docker_not_available(self, mock_containers):
        """When docker returns no containers, report should still be valid."""
        mock_containers.return_value = []
        fixer = InfraFixer(projects={})
        report = fixer.run_check(auto_fix=False)
        assert isinstance(report, InfraReport)
        assert report.containers_total == 0
        assert report.containers_running == 0


# ---------------------------------------------------------------------------
# TestCheckDiskUsage
# ---------------------------------------------------------------------------


class TestCheckDiskUsage:
    """Tests for InfraFixer.check_disk_usage."""

    @patch.object(InfraFixer, "_run_cmd")
    def test_flags_large_reclaimable(self, mock_cmd):
        mock_cmd.return_value = MagicMock(
            returncode=0,
            stdout="Images\t5.2GB\t2.1GB\nContainers\t100MB\t50MB\nVolumes\t3GB\t1.5GB\n",
        )
        fixer = InfraFixer(projects={})
        issues = fixer.check_disk_usage()
        # Should flag Images (2.1GB) and Volumes (1.5GB) but not Containers (50MB)
        assert len(issues) == 2
        assert all(i.severity == "info" for i in issues)
        assert any("Images" in i.issue for i in issues)
        assert any("Volumes" in i.issue for i in issues)

    @patch.object(InfraFixer, "_run_cmd")
    def test_no_issues_when_small(self, mock_cmd):
        mock_cmd.return_value = MagicMock(
            returncode=0,
            stdout="Images\t500MB\t100MB\nContainers\t10MB\t5MB\n",
        )
        fixer = InfraFixer(projects={})
        issues = fixer.check_disk_usage()
        assert len(issues) == 0

    @patch.object(InfraFixer, "_run_cmd")
    def test_handles_command_failure(self, mock_cmd):
        mock_cmd.return_value = MagicMock(returncode=1, stdout="")
        fixer = InfraFixer(projects={})
        issues = fixer.check_disk_usage()
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# TestKnownProjects
# ---------------------------------------------------------------------------


class TestKnownProjects:
    """Tests for KNOWN_PROJECTS configuration."""

    def test_all_projects_have_required_keys(self):
        for name, info in KNOWN_PROJECTS.items():
            assert "compose_dir" in info, f"{name} missing compose_dir"
            assert "expected_running" in info, f"{name} missing expected_running"
            assert isinstance(info["expected_running"], list)

    def test_known_project_count(self):
        assert len(KNOWN_PROJECTS) == 9
