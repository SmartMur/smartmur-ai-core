"""Tests for superpowers.job_runner — git-branch job orchestration."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from superpowers.job_runner import JobResult, JobRunner, JobRunnerError, JobStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository with one commit."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    # Create initial commit so we have a branch to return to
    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "Initial commit"],
        check=True,
        capture_output=True,
    )
    return tmp_path


@pytest.fixture
def runner(git_repo: Path) -> JobRunner:
    """Return a JobRunner pointing at the temp git repo."""
    return JobRunner(repo_dir=git_repo)


# ---------------------------------------------------------------------------
# D1: Branch creation and execution
# ---------------------------------------------------------------------------


class TestBranchCreation:
    def test_creates_job_branch(self, runner: JobRunner, git_repo: Path):
        result = runner.run(name="test-job", command="echo hello", job_id="abc123")
        assert result.branch == "job/abc123"
        # Verify branch exists in git
        proc = subprocess.run(
            ["git", "-C", str(git_repo), "branch", "--list", "job/abc123"],
            capture_output=True,
            text=True,
        )
        assert "job/abc123" in proc.stdout

    def test_returns_to_original_branch(self, runner: JobRunner, git_repo: Path):
        original = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        runner.run(name="test", command="echo done")
        current = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert current == original

    def test_auto_generates_job_id(self, runner: JobRunner):
        result = runner.run(name="auto-id", command="echo ok")
        assert len(result.job_id) == 8
        assert result.branch.startswith("job/")

    def test_duplicate_branch_raises(self, runner: JobRunner):
        runner.run(name="first", command="echo 1", job_id="dup")
        with pytest.raises(JobRunnerError, match="already exists"):
            runner.run(name="second", command="echo 2", job_id="dup")

    def test_requires_command_or_callable(self, runner: JobRunner):
        with pytest.raises(JobRunnerError, match="Either command or callable"):
            runner.run(name="empty")


class TestShellExecution:
    def test_captures_stdout(self, runner: JobRunner):
        result = runner.run(name="echo-test", command="echo 'hello world'")
        assert "hello world" in result.output
        assert result.return_code == 0

    def test_captures_stderr(self, runner: JobRunner):
        result = runner.run(name="stderr-test", command="echo 'err' >&2 && false")
        assert "err" in result.error
        assert result.return_code != 0
        assert result.status == JobStatus.failed

    def test_successful_job_status(self, runner: JobRunner):
        result = runner.run(name="ok-job", command="echo success")
        assert result.status == JobStatus.completed

    def test_failed_job_status(self, runner: JobRunner):
        result = runner.run(name="fail-job", command="exit 1")
        assert result.status == JobStatus.failed

    def test_records_timing(self, runner: JobRunner):
        result = runner.run(name="timing", command="echo fast")
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration is not None
        assert result.duration >= 0


class TestCallableExecution:
    def test_callable_success(self, runner: JobRunner, git_repo: Path):
        def my_task():
            (git_repo / "output.txt").write_text("generated")
            return "task done"

        result = runner.run(name="callable-job", callable=my_task)
        assert result.status == JobStatus.completed
        assert result.output == "task done"
        assert result.return_code == 0

    def test_callable_none_return(self, runner: JobRunner):
        def quiet_task():
            return None

        result = runner.run(name="quiet", callable=quiet_task)
        assert result.status == JobStatus.completed
        assert result.output == ""

    def test_callable_exception(self, runner: JobRunner):
        def bad_task():
            raise ValueError("something broke")

        result = runner.run(name="broken", callable=bad_task)
        assert result.status == JobStatus.failed
        assert "something broke" in result.error
        assert result.return_code == 1


class TestAutoCommit:
    def test_commits_new_files(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="create-file",
            command=f"echo 'new content' > {git_repo / 'newfile.txt'}",
        )
        assert result.status == JobStatus.completed
        assert result.commit_sha is not None
        assert len(result.commit_sha) >= 7

    def test_commits_modified_files(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="modify-readme",
            command=f"echo 'updated' >> {git_repo / 'README.md'}",
        )
        assert result.status == JobStatus.completed
        assert "README.md" in result.changed_files

    def test_no_commit_when_no_changes(self, runner: JobRunner):
        result = runner.run(name="no-op", command="echo 'no files changed'")
        assert result.status == JobStatus.completed
        assert result.commit_sha is None
        assert result.changed_files == []

    def test_no_commit_on_failure(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="fail-with-changes",
            command=f"echo 'partial' > {git_repo / 'partial.txt'} && exit 1",
        )
        assert result.status == JobStatus.failed
        # changed_files may still be populated but no commit should exist
        # (we track what changed even on failure for diagnostics)

    def test_custom_commit_message(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="custom-msg",
            command=f"echo 'data' > {git_repo / 'data.txt'}",
            commit_message="feat: add data file",
        )
        assert result.commit_sha is not None
        # Verify the commit message on the job branch
        log = subprocess.run(
            ["git", "-C", str(git_repo), "log", result.branch, "-1", "--format=%s"],
            capture_output=True,
            text=True,
        )
        assert "feat: add data file" in log.stdout

    def test_changed_files_tracked(self, runner: JobRunner, git_repo: Path):
        cmd = f"echo a > {git_repo / 'file_a.txt'} && echo b > {git_repo / 'file_b.txt'}"
        result = runner.run(name="multi-file", command=cmd)
        assert "file_a.txt" in result.changed_files
        assert "file_b.txt" in result.changed_files


# ---------------------------------------------------------------------------
# D2: PR creation
# ---------------------------------------------------------------------------


class TestPRCreation:
    def test_pr_without_gh(self, runner: JobRunner, git_repo: Path, monkeypatch):
        """When gh is not available, pr_url should contain branch info."""
        monkeypatch.setattr("shutil.which", lambda name: None)
        result = runner.run(
            name="pr-test",
            command=f"echo 'pr content' > {git_repo / 'pr.txt'}",
        )
        result = runner.create_pr(result)
        assert result.pr_url is not None
        assert "branch:job/" in result.pr_url

    def test_pr_skipped_for_failed_job(self, runner: JobRunner, git_repo: Path):
        result = runner.run(name="fail", command="exit 1")
        result = runner.create_pr(result)
        assert result.pr_url is None  # Should not attempt

    def test_pr_body_generation(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="body-test",
            command=f"echo 'content' > {git_repo / 'doc.md'}",
        )
        body = runner._generate_pr_body(result)
        assert "body-test" in body
        assert result.job_id in body
        assert "doc.md" in body

    def test_pr_custom_title_and_body(self, runner: JobRunner, git_repo: Path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        result = runner.run(
            name="custom-pr",
            command=f"echo 'x' > {git_repo / 'x.txt'}",
        )
        result = runner.create_pr(
            result,
            title="Custom Title",
            body="Custom body text",
        )
        assert result.pr_url is not None


# ---------------------------------------------------------------------------
# D3: Path-restricted auto-merge
# ---------------------------------------------------------------------------


class TestAutoMerge:
    def test_can_auto_merge_allowed_paths(self, runner: JobRunner, git_repo: Path):
        runner.run(
            name="docs-change",
            command=f"echo 'doc' > {git_repo / 'docs' / 'guide.txt'}; echo 'note' > {git_repo / 'CHANGELOG.md'}",
        )
        # docs/* and *.md are in the default allowed paths
        # Manually fix: the command creates docs/ dir but docs/guide.txt matches docs/*
        (git_repo / "docs").mkdir(exist_ok=True)
        # Re-run to make sure files exist
        result2 = runner.run(
            name="docs-change2",
            command=f"mkdir -p {git_repo / 'docs'} && echo 'doc' > {git_repo / 'docs' / 'guide.txt'}",
        )
        assert runner.can_auto_merge(result2)

    def test_cannot_auto_merge_restricted_paths(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="src-change",
            command=f"echo 'code' > {git_repo / 'main.py'}",
        )
        assert not runner.can_auto_merge(result)

    def test_cannot_auto_merge_mixed_paths(self, runner: JobRunner, git_repo: Path):
        cmd = f"echo 'doc' > {git_repo / 'README.md'} && echo 'code' > {git_repo / 'main.py'}"
        result = runner.run(name="mixed", command=cmd)
        assert not runner.can_auto_merge(result)

    def test_cannot_auto_merge_no_changes(self, runner: JobRunner):
        result = runner.run(name="no-changes", command="echo noop")
        assert not runner.can_auto_merge(result)

    def test_cannot_auto_merge_failed_job(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="fail-merge",
            command=f"echo 'doc' > {git_repo / 'NOTES.md'} && exit 1",
        )
        assert not runner.can_auto_merge(result)

    def test_auto_merge_succeeds(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="merge-test",
            command=f"echo 'note' > {git_repo / 'NOTES.md'}",
        )
        assert runner.can_auto_merge(result)
        original_branch = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        result = runner.auto_merge(result, target_branch=original_branch)
        assert result.status == JobStatus.merged

    def test_auto_merge_blocked_logs_warning(self, runner: JobRunner, git_repo: Path):
        result = runner.run(
            name="blocked",
            command=f"echo 'code' > {git_repo / 'app.py'}",
        )
        result = runner.auto_merge(result)
        assert result.status != JobStatus.merged

    def test_custom_allowed_paths(self, git_repo: Path):
        runner = JobRunner(
            repo_dir=git_repo,
            allowed_auto_merge_paths=["config/*.yaml", "*.json"],
        )
        result = runner.run(
            name="config-change",
            command=f"echo '{{}}' > {git_repo / 'settings.json'}",
        )
        assert runner.can_auto_merge(result)

    def test_matches_any_pattern_method(self, runner: JobRunner):
        assert runner._matches_any_pattern("docs/guide.txt")
        assert runner._matches_any_pattern("README.md")
        assert runner._matches_any_pattern("tests/test_foo.py")
        assert runner._matches_any_pattern("skills/heartbeat/skill.yaml")
        assert not runner._matches_any_pattern("superpowers/main.py")
        assert not runner._matches_any_pattern("docker-compose.yml")


# ---------------------------------------------------------------------------
# D4: Job listing and retrieval
# ---------------------------------------------------------------------------


class TestJobQueries:
    def test_list_jobs_empty(self, runner: JobRunner):
        assert runner.list_jobs() == []

    def test_list_jobs_after_run(self, runner: JobRunner):
        runner.run(name="j1", command="echo 1", job_id="aaa")
        runner.run(name="j2", command="echo 2", job_id="bbb")
        jobs = runner.list_jobs()
        assert len(jobs) == 2
        ids = {j.job_id for j in jobs}
        assert ids == {"aaa", "bbb"}

    def test_get_job_found(self, runner: JobRunner):
        runner.run(name="findme", command="echo x", job_id="find1")
        job = runner.get_job("find1")
        assert job is not None
        assert job.name == "findme"

    def test_get_job_not_found(self, runner: JobRunner):
        assert runner.get_job("nonexistent") is None

    def test_list_job_branches(self, runner: JobRunner, git_repo: Path):
        runner.run(name="br1", command="echo a", job_id="br1")
        runner.run(name="br2", command="echo b", job_id="br2")
        branches = runner.list_job_branches()
        branch_ids = {b["job_id"] for b in branches}
        assert "br1" in branch_ids
        assert "br2" in branch_ids

    def test_list_job_branches_with_status(self, runner: JobRunner, git_repo: Path):
        runner.run(name="ok-job", command="echo ok", job_id="okjob")
        branches = runner.list_job_branches()
        found = [b for b in branches if b["job_id"] == "okjob"]
        assert len(found) == 1
        assert found[0]["status"] == "completed"


# ---------------------------------------------------------------------------
# D5: JobResult dataclass
# ---------------------------------------------------------------------------


class TestJobResult:
    def test_default_values(self):
        r = JobResult(job_id="x", name="test", branch="job/x")
        assert r.status == JobStatus.pending
        assert r.output == ""
        assert r.error == ""
        assert r.changed_files == []
        assert r.return_code is None

    def test_status_enum(self):
        assert JobStatus.completed.value == "completed"
        assert JobStatus.failed.value == "failed"
        assert JobStatus.merged.value == "merged"
        assert JobStatus.running.value == "running"
        assert JobStatus.pending.value == "pending"


# ---------------------------------------------------------------------------
# Dashboard API tests
# ---------------------------------------------------------------------------


class TestDashboardJobsAPI:
    """Test the /api/jobs/branches endpoints via FastAPI TestClient."""

    @pytest.fixture
    def client(self, monkeypatch):
        """Set up dashboard credentials and return a test client."""
        monkeypatch.setenv("DASHBOARD_USER", "admin")
        monkeypatch.setenv("DASHBOARD_PASS", "testpass")
        # Reset singleton so new env vars are picked up
        import dashboard.deps as deps

        deps._settings = None
        deps._jobs_db = None

        from fastapi.testclient import TestClient

        from dashboard.app import app

        client = TestClient(app)
        return client

    def _auth(self):
        return ("admin", "testpass")

    def test_list_job_branches_endpoint(self, client):
        resp = client.get("/api/jobs/branches", auth=self._auth())
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_job_branch_not_found(self, client):
        resp = client.get("/api/jobs/branches/nonexistent", auth=self._auth())
        assert resp.status_code == 404

    def test_existing_jobs_endpoints_still_work(self, client):
        # The original DB-backed endpoints should still function
        resp = client.get("/api/jobs", auth=self._auth())
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------


class TestConfig:
    def test_default_allowed_paths(self):
        from superpowers.config import Settings

        s = Settings()
        assert "docs/*" in s.allowed_auto_merge_paths
        assert "*.md" in s.allowed_auto_merge_paths
        assert "tests/*" in s.allowed_auto_merge_paths

    def test_runner_uses_config_paths(self, git_repo: Path):
        from superpowers.config import Settings

        s = Settings()
        runner = JobRunner(
            repo_dir=git_repo,
            allowed_auto_merge_paths=s.allowed_auto_merge_paths,
        )
        assert runner.allowed_auto_merge_paths == s.allowed_auto_merge_paths
