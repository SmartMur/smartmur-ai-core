# Job Orchestration

## Overview

The job runner executes work on isolated git branches, keeping the main branch clean while automation tasks make changes to the repository. Each job gets a dedicated `job/{id}` branch created from the current HEAD. After execution, all changes are staged and committed automatically. The runner then returns to the original branch.

Optional features include pull request creation via the `gh` CLI and path-restricted auto-merge that prevents accidental merges of sensitive files.

## How It Works

1. A new branch `job/{id}` is created from the current HEAD.
2. The runner checks out the job branch.
3. The command (shell string) or callable (Python function) executes.
4. All changed, new, and untracked files are staged and committed.
5. The runner checks out the original branch.
6. Optionally, a pull request is created and/or an auto-merge is attempted.

Jobs are tracked in memory for the lifetime of the `JobRunner` instance. The `list_job_branches()` method also discovers `job/*` branches directly from git, so branches from previous sessions are visible.

## Configuration

### Auto-Merge Path Restrictions

Auto-merge only proceeds when every changed file matches at least one allowed glob pattern. The defaults are:

| Pattern | Description |
|---------|-------------|
| `docs/*` | Documentation files |
| `*.md` | Markdown files anywhere in the repo |
| `tests/*` | Test files |
| `skills/*/skill.yaml` | Skill manifests |

Override the defaults by passing `allowed_auto_merge_paths` to the `JobRunner` constructor:

```python
runner = JobRunner(
    repo_dir="/path/to/repo",
    allowed_auto_merge_paths=["docs/*", "*.md", "config/*.yaml"],
)
```

### Timeouts

| Operation | Timeout | Notes |
|-----------|---------|-------|
| Job execution (shell) | 300 seconds | Applies to the subprocess |
| Git operations | 60 seconds | Per git command |
| PR creation via `gh` | 30 seconds | Falls back gracefully if `gh` is unavailable |

## CLI Reference

All commands are under `claw jobs`.

### `claw jobs list`

List all `job/*` branches in the repository with their status and commit SHA.

```bash
claw jobs list
claw jobs list --repo /path/to/repo
```

```
                Job Branches
+----------+-----------+-----------+----------+
| ID       | Branch    | Status    | SHA      |
+----------+-----------+-----------+----------+
| a1b2c3d4 | job/a1b2c3d4 | completed | 9f8e7d6c |
| fix-docs | job/fix-docs | merged    | 1a2b3c4d |
+----------+-----------+-----------+----------+
```

### `claw jobs run`

Execute a shell command on a dedicated job branch.

```bash
claw jobs run <name> -c "<command>" [options]
```

| Flag | Description |
|------|-------------|
| `-c`, `--command` | Shell command to execute (required) |
| `--repo` | Repository path (default: current working directory) |
| `--pr` | Create a pull request after successful execution |
| `--auto-merge` | Auto-merge the branch if all changed files are in allowed paths |

## Python API

### JobRunner

```python
from superpowers.job_runner import JobRunner

runner = JobRunner(repo_dir="/path/to/repo")
```

### Running a Job

With a shell command:

```python
result = runner.run(
    name="update-docs",
    command="python scripts/gen_docs.py",
    commit_message="docs: regenerate API reference",
)
```

With a Python callable:

```python
def my_task():
    Path("output.txt").write_text("done")
    return "Task finished"

result = runner.run(name="write-output", callable=my_task)
```

### Inspecting Results

```python
print(result.status)         # JobStatus.completed
print(result.job_id)         # "a1b2c3d4"
print(result.branch)         # "job/a1b2c3d4"
print(result.changed_files)  # ["docs/api.md"]
print(result.commit_sha)     # "9f8e7d6c..."
print(result.duration)       # 2.34 (seconds)
```

The `JobResult` dataclass contains:

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `str` | Unique job identifier |
| `name` | `str` | Human-readable job name |
| `branch` | `str` | Git branch name (`job/{id}`) |
| `status` | `JobStatus` | `pending`, `running`, `completed`, `failed`, or `merged` |
| `output` | `str` | stdout from the command |
| `error` | `str` | stderr or error message |
| `return_code` | `int` | Process exit code |
| `commit_sha` | `str` | SHA of the commit on the job branch |
| `pr_url` | `str` | Pull request URL or branch reference |
| `changed_files` | `list[str]` | Files modified by the job |
| `started_at` | `float` | Timestamp when execution began |
| `completed_at` | `float` | Timestamp when execution finished |
| `duration` | `float` | Execution time in seconds |

### Creating a Pull Request

```python
result = runner.create_pr(
    result,
    base_branch="main",
    title="Job: update-docs",
    body="Regenerated API reference from source.",
)
print(result.pr_url)
```

If `gh` is not installed, `pr_url` is set to `branch:<branch-name>` so you can create the PR manually.

### Auto-Merge

```python
if runner.can_auto_merge(result):
    result = runner.auto_merge(result, target_branch="main")
    print(result.status)  # JobStatus.merged
```

Auto-merge is blocked when:

- The job has no changed files.
- The job failed.
- Any changed file does not match the allowed glob patterns.

When blocked, the result is returned unchanged. When a merge conflict occurs, the merge is aborted and an error is recorded on the result.

## Examples

### Run a Documentation Update and Auto-Merge

```bash
claw jobs run regen-docs \
  -c "python scripts/gen_docs.py" \
  --auto-merge
```

Because the generated files land under `docs/*`, auto-merge proceeds automatically.

### Run a Code Change and Open a PR

```bash
claw jobs run refactor-utils \
  -c "python scripts/refactor.py" \
  --pr
```

The `--pr` flag creates a GitHub pull request via `gh pr create`. Since code files are outside the default auto-merge paths, `--auto-merge` would be blocked.

### End-to-End in Python

```python
from superpowers.job_runner import JobRunner

runner = JobRunner(allowed_auto_merge_paths=["docs/*", "*.md"])
result = runner.run(name="update-changelog", command="./scripts/changelog.sh")

if result.status.value == "completed":
    if runner.can_auto_merge(result):
        runner.auto_merge(result)
    else:
        runner.create_pr(result, title="Update changelog")
```

## Troubleshooting

**"Branch job/xxx already exists"** -- A previous job with the same ID was not cleaned up. Delete the branch with `git branch -D job/xxx` and retry.

**"gh CLI not available"** -- Install the GitHub CLI (`gh`) to enable PR creation. Without it, the runner logs the branch name so you can create the PR manually.

**"Auto-merge blocked: files outside allowed paths"** -- The job changed files not covered by `allowed_auto_merge_paths`. Either add the paths to the allowlist or merge manually via a PR.

**Job times out** -- Shell commands have a 300-second timeout. For long-running tasks, consider breaking them into smaller jobs or increasing the timeout in custom code.

## Modules

| Module | Path | Purpose |
|--------|------|---------|
| `job_runner` | `superpowers/job_runner.py` | Core engine: branch management, execution, PR creation, auto-merge |
| `cli_jobs` | `superpowers/cli_jobs.py` | Click commands for `claw jobs` |
