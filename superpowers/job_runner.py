"""Job orchestration: branch-per-job execution with optional PR creation and auto-merge.

Each job runs on a dedicated ``job/{id}`` git branch.  After execution the
results are committed and the runner returns to the original branch.  If
``gh`` CLI is available, a pull request can be created automatically.
Path-restricted auto-merge prevents accidental merges of sensitive changes.
"""

from __future__ import annotations

import fnmatch
import logging
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    merged = "merged"


@dataclass
class JobResult:
    """Outcome of a single job execution."""

    job_id: str
    name: str
    branch: str
    status: JobStatus = JobStatus.pending
    output: str = ""
    error: str = ""
    return_code: int | None = None
    commit_sha: str | None = None
    pr_url: str | None = None
    changed_files: list[str] = field(default_factory=list)
    started_at: float | None = None
    completed_at: float | None = None
    duration: float | None = None


class JobRunnerError(Exception):
    """Raised when a job orchestration step fails."""


class JobRunner:
    """Execute work on isolated git branches with automatic commits.

    Parameters
    ----------
    repo_dir:
        Path to the git repository.  Defaults to the current working directory.
    allowed_auto_merge_paths:
        Glob patterns for files safe to auto-merge.  If *all* changed files
        match at least one pattern, ``auto_merge()`` will proceed.
    """

    def __init__(
        self,
        repo_dir: str | Path | None = None,
        allowed_auto_merge_paths: list[str] | None = None,
    ) -> None:
        self.repo_dir = Path(repo_dir) if repo_dir else Path.cwd()
        self.allowed_auto_merge_paths: list[str] = allowed_auto_merge_paths or [
            "docs/*",
            "*.md",
            "tests/*",
            "skills/*/skill.yaml",
        ]
        self._results: dict[str, JobResult] = {}

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        """Run a git command inside the repo directory."""
        cmd = ["git", "-C", str(self.repo_dir), *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
            timeout=60,
        )

    def _current_branch(self) -> str:
        """Return the current branch name (or HEAD sha if detached)."""
        result = self._git("rev-parse", "--abbrev-ref", "HEAD")
        branch = result.stdout.strip()
        if branch == "HEAD":
            # Detached HEAD — return the sha
            result = self._git("rev-parse", "HEAD")
            return result.stdout.strip()
        return branch

    def _branch_exists(self, branch: str) -> bool:
        """Check whether a local branch exists."""
        result = self._git("rev-parse", "--verify", branch, check=False)
        return result.returncode == 0

    def _changed_files(self) -> list[str]:
        """Return list of changed/new files relative to repo root."""
        # Staged changes
        staged = self._git("diff", "--cached", "--name-only", check=False)
        # Unstaged changes
        unstaged = self._git("diff", "--name-only", check=False)
        # Untracked
        untracked = self._git("ls-files", "--others", "--exclude-standard", check=False)
        files: set[str] = set()
        for r in (staged, unstaged, untracked):
            for line in r.stdout.strip().splitlines():
                if line.strip():
                    files.add(line.strip())
        return sorted(files)

    def _diff_summary(self) -> str:
        """Return a short diff stat summary."""
        result = self._git("diff", "--stat", "HEAD", check=False)
        return result.stdout.strip() or "(no changes)"

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def run(
        self,
        name: str,
        command: str | None = None,
        callable: Callable[[], str | None] | None = None,
        commit_message: str | None = None,
        job_id: str | None = None,
    ) -> JobResult:
        """Execute a job on a dedicated branch.

        Either *command* (string, split via ``shlex.split``) or *callable*
        (Python function) must be provided.  The callable should return an
        optional output string.

        Steps:
            1. Create ``job/{id}`` branch from current HEAD
            2. Run the command or callable
            3. Stage and commit all changes
            4. Return to the original branch
        """
        if not command and not callable:
            raise JobRunnerError("Either command or callable must be provided")

        jid = job_id or str(uuid.uuid4())[:8]
        branch = f"job/{jid}"
        original_branch = self._current_branch()

        result = JobResult(
            job_id=jid,
            name=name,
            branch=branch,
        )

        try:
            # 1. Create and checkout the job branch
            if self._branch_exists(branch):
                raise JobRunnerError(f"Branch {branch} already exists")
            self._git("checkout", "-b", branch)
            result.status = JobStatus.running
            result.started_at = time.time()

            # 2. Execute
            if command:
                # SECURITY: shell=True is required here because job commands
                # may contain shell operators (pipes, redirects, &&, etc.).
                # The command originates from the local CLI (--command flag)
                # or Python callers — never from untrusted network input.
                # We use an explicit /bin/sh invocation to make the shell
                # usage auditable rather than relying on shell=True internals.
                proc = subprocess.run(
                    ["/bin/sh", "-c", command],
                    capture_output=True,
                    text=True,
                    cwd=str(self.repo_dir),
                    timeout=300,
                )
                result.output = proc.stdout
                result.error = proc.stderr
                result.return_code = proc.returncode
                if proc.returncode != 0:
                    result.status = JobStatus.failed
            else:
                # callable path
                assert callable is not None
                try:
                    output = callable()
                    result.output = output or ""
                    result.return_code = 0
                except (RuntimeError, OSError, ValueError, KeyError) as exc:
                    result.error = str(exc)
                    result.return_code = 1
                    result.status = JobStatus.failed

            # 3. Stage and commit changes
            changed = self._changed_files()
            result.changed_files = changed
            if changed and result.status != JobStatus.failed:
                self._git("add", "-A")
                msg = commit_message or f"job/{jid}: {name}"
                self._git("commit", "-m", msg, check=False)
                sha_result = self._git("rev-parse", "HEAD")
                result.commit_sha = sha_result.stdout.strip()

            if result.status == JobStatus.running:
                result.status = JobStatus.completed

        except subprocess.TimeoutExpired:
            result.status = JobStatus.failed
            result.error = "Job execution timed out"
        except subprocess.CalledProcessError as exc:
            result.status = JobStatus.failed
            result.error = f"Git error: {exc.stderr or exc.stdout or str(exc)}"
        finally:
            result.completed_at = time.time()
            if result.started_at:
                result.duration = result.completed_at - result.started_at

            # 4. Return to original branch
            try:
                self._git("checkout", original_branch, check=False)
            except (subprocess.SubprocessError, OSError):
                logger.warning("Could not return to branch %s", original_branch)

        self._results[jid] = result
        return result

    # ------------------------------------------------------------------
    # PR creation
    # ------------------------------------------------------------------

    def create_pr(
        self,
        result: JobResult,
        base_branch: str | None = None,
        title: str | None = None,
        body: str | None = None,
    ) -> JobResult:
        """Create a pull request for a completed job.

        Uses ``gh`` CLI if available; otherwise logs the branch info.
        Returns the updated result with ``pr_url`` set if successful.
        """
        if result.status not in (JobStatus.completed, JobStatus.merged):
            logger.warning("Job %s not completed, skipping PR creation", result.job_id)
            return result

        base = base_branch or self._current_branch()
        pr_title = title or f"Job: {result.name}"
        pr_body = body or self._generate_pr_body(result)

        gh_path = shutil.which("gh")
        if gh_path:
            try:
                proc = subprocess.run(
                    [
                        gh_path,
                        "pr",
                        "create",
                        "--base",
                        base,
                        "--head",
                        result.branch,
                        "--title",
                        pr_title,
                        "--body",
                        pr_body,
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(self.repo_dir),
                    timeout=30,
                )
                if proc.returncode == 0:
                    result.pr_url = proc.stdout.strip()
                    logger.info("PR created: %s", result.pr_url)
                else:
                    logger.warning("gh pr create failed: %s", proc.stderr)
                    result.pr_url = f"branch:{result.branch} (gh failed: {proc.stderr.strip()})"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("gh CLI timed out or not found")
                result.pr_url = f"branch:{result.branch}"
        else:
            logger.info(
                "gh CLI not available. Branch ready for PR: %s -> %s",
                result.branch,
                base,
            )
            result.pr_url = f"branch:{result.branch}"

        self._results[result.job_id] = result
        return result

    def _generate_pr_body(self, result: JobResult) -> str:
        """Generate a PR body from job result."""
        lines = [
            f"## Job: {result.name}",
            f"**Job ID:** {result.job_id}",
            f"**Branch:** `{result.branch}`",
            f"**Status:** {result.status.value}",
            "",
        ]
        if result.changed_files:
            lines.append("### Changed files")
            for f in result.changed_files:
                lines.append(f"- `{f}`")
            lines.append("")
        if result.output:
            lines.append("### Output")
            lines.append("```")
            lines.append(result.output[:2000])
            lines.append("```")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Auto-merge
    # ------------------------------------------------------------------

    def can_auto_merge(self, result: JobResult) -> bool:
        """Check if all changed files match allowed auto-merge patterns.

        Returns True only if there are changed files and every one matches
        at least one pattern in ``allowed_auto_merge_paths``.
        """
        if not result.changed_files:
            return False
        if result.status == JobStatus.failed:
            return False

        for filepath in result.changed_files:
            if not self._matches_any_pattern(filepath):
                return False
        return True

    def _matches_any_pattern(self, filepath: str) -> bool:
        """Check if a file path matches any of the allowed glob patterns."""
        for pattern in self.allowed_auto_merge_paths:
            if fnmatch.fnmatch(filepath, pattern):
                return True
        return False

    def auto_merge(self, result: JobResult, target_branch: str | None = None) -> JobResult:
        """Merge a job branch if all changed files are in allowed paths.

        Performs a fast-forward or regular merge into the target branch.
        Returns the updated result.
        """
        if not self.can_auto_merge(result):
            logger.warning(
                "Auto-merge blocked for job %s: files outside allowed paths", result.job_id
            )
            return result

        target = target_branch or self._current_branch()

        try:
            self._git("checkout", target)
            self._git(
                "merge", result.branch, "--no-ff", "-m", f"Merge {result.branch}: {result.name}"
            )
            result.status = JobStatus.merged
            logger.info("Auto-merged %s into %s", result.branch, target)
        except subprocess.CalledProcessError as exc:
            logger.error("Auto-merge failed: %s", exc.stderr)
            result.error = f"Auto-merge failed: {exc.stderr}"
            # Abort the merge if it failed mid-way
            self._git("merge", "--abort", check=False)
        finally:
            self._results[result.job_id] = result

        return result

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_jobs(self) -> list[JobResult]:
        """Return all tracked job results."""
        return list(self._results.values())

    def get_job(self, job_id: str) -> JobResult | None:
        """Return a single job result by ID."""
        return self._results.get(job_id)

    def list_job_branches(self) -> list[dict]:
        """List all job/* branches from the git repo with metadata."""
        result = self._git(
            "branch",
            "--list",
            "job/*",
            "--format=%(refname:short) %(objectname:short) %(committerdate:iso)",
            check=False,
        )
        branches = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.strip().split(None, 2)
            branch_name = parts[0] if parts else line.strip()
            sha = parts[1] if len(parts) > 1 else ""
            date = parts[2] if len(parts) > 2 else ""
            job_id = branch_name.removeprefix("job/")
            # Check if we have a tracked result for this
            tracked = self._results.get(job_id)
            branches.append(
                {
                    "job_id": job_id,
                    "branch": branch_name,
                    "sha": sha,
                    "date": date,
                    "status": tracked.status.value if tracked else "unknown",
                    "name": tracked.name if tracked else "",
                }
            )
        return branches
