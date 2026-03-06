# Contributing to Claude Superpowers

Thank you for your interest in contributing to the Nexus ecosystem.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How to Contribute](#how-to-contribute)
3. [Development Setup](#development-setup)
4. [Coding Standards](#coding-standards)
5. [Commit Convention](#commit-convention)
6. [Pull Request Process](#pull-request-process)
7. [Issue Guidelines](#issue-guidelines)
8. [Security](#security)

---

## Code of Conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
Be respectful, constructive, and professional.

---

## How to Contribute

### Good First Issues

Look for issues labeled `good first issue` or `help wanted`. We also maintain a curated list of approachable tasks in **[docs/good-first-issues.md](docs/good-first-issues.md)** -- 17 self-contained issues ranging from adding docstrings to writing new test files.

### Types of Contributions

- **Bug fixes**: Found a bug? Open an issue first, then submit a PR.
- **New features**: Discuss in an issue before writing code. We value design alignment.
- **Documentation**: Typos, clarifications, new guides -- always welcome.
- **Skills**: New skills that follow the skill manifest format (see `superpowers/skill_creator.py` and `skills/_template/`).
- **Tests**: More coverage is always appreciated. We maintain 982+ tests.
- **Security**: See [Security](#security) below for responsible disclosure.

---

## Development Setup

### Prerequisites

- Python 3.12 or 3.13
- `git`
- `docker` and `docker-compose` (for running the full stack)
- `age` (for encryption tests; install via `apt install age` or `brew install age`)
- Shell: bash 4.0+ or zsh

### Local Setup

```bash
# Clone the repository
git clone https://github.com/SmartMur/claude-superpowers.git
cd claude-superpowers

# Create virtual environment (Python 3.13 lacks ensurepip, so use --without-pip)
python3 -m venv --without-pip .venv

# Bootstrap pip using get-pip.py
.venv/bin/python -m pip install --upgrade pip setuptools wheel

# Install the package in editable mode + development dependencies
.venv/bin/pip install -e ".[dev]"

# Verify installation
.venv/bin/claw --version
```

### Running Tests

```bash
# Run the full test suite (excluding the hanging Telegram concurrency test)
PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_telegram_concurrency.py -q

# Run tests with coverage
PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_telegram_concurrency.py --cov=superpowers --cov-report=html

# Run a specific test file
PYTHONPATH=. .venv/bin/pytest tests/test_cron_engine.py -v

# Run tests matching a pattern
PYTHONPATH=. .venv/bin/pytest tests/ -k "vault" -v
```

**Note**: Vault tests (14 errors, 5 failures) require `age-keygen` binary to be installed. If `age` is not available, those tests will fail but do not block contributions.

---

## Coding Standards

### Python (Main codebase)

- **Formatter/Linter**: ruff (configured in `pyproject.toml`)
- **Type hints**: Required for all public functions
- **Docstrings**: Required for all public classes and functions (Google-style)
- **Imports**: Sorted and deduplicated by ruff. No unused imports.
- **Max line length**: 120 characters
- **Test every public function**: Unit tests in `tests/test_*.py`

Run linting:
```bash
.venv/bin/ruff check .
.venv/bin/ruff format . --diff  # Preview changes
.venv/bin/ruff format .         # Apply fixes
```

### Shell Scripts

- **Linting**: `shellcheck` (all scripts must pass)
- **Shebang**: `#!/usr/bin/env bash`
- **Error handling**: `set -euo pipefail` at the top
- **Quoting**: All variable expansions must be quoted
- **Location**: Scripts in `scripts/` or skill `run.sh` files

Run linting:
```bash
shellcheck scripts/*.sh skills/*/run.sh
```

### YAML (Workflows, skill manifests)

- **Indentation**: 2 spaces
- **No trailing whitespace**
- **Comments**: Explain non-obvious values
- **Validation**: Workflows and skill.yaml files must match schema (validated in tests)

### General

- No hardcoded secrets, IPs, paths, or machine-specific values
- All sensitive values in `.env` or vault (encrypted)
- `.env.example` files provided for every `.env`
- Skills follow the structure: `skills/{skill-name}/skill.yaml`, `run.py` or `run.sh`, `command.md`

---

## Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`, `perf`

**Scope**: The subsystem affected (e.g., `vault`, `cron`, `ssh`, `messaging`, `browser`, `skills`, `workflows`, `memory`, `dashboard`, `intake`)

**Examples**:

```
feat(ssh): add connection timeout configuration
fix(cron): prevent duplicate job scheduling on daemon restart
docs(workflows): add approval gate example to reference
test(vault): add rotation policy expiry edge cases
feat(skills): create network-scan skill with NMAP integration
refactor(memory): optimize fact lookup query performance
perf(intake): cache parsed YAML workflow definitions
```

---

## Pull Request Process

1. **Branch from `main`**. Name your branch: `{type}/{short-description}` (e.g., `feat/ssh-timeout`, `fix/cron-duplicate`).

2. **Write tests** for any new functionality. PRs that decrease test coverage will be discussed.

3. **Run the full test suite locally** before pushing:
   ```bash
   PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_telegram_concurrency.py -q
   ```

4. **Run linting** to ensure code quality:
   ```bash
   .venv/bin/ruff check .
   .venv/bin/ruff format .
   shellcheck scripts/*.sh 2>/dev/null || true
   ```

5. **Update documentation** if your change affects user-facing behavior:
   - Update relevant files in `docs/`
   - Update `README.md` if adding a new subsystem
   - Add a comment in your code if the change is subtle

6. **Fill out the PR template**. Describe what changed, why, and how to test it.

7. **One approval required** for merge. Maintainers may request changes.

8. **Squash merge** is the default merge strategy.

### PR Template

```markdown
## What

<!-- Brief description of the change -->

## Why

<!-- What problem does this solve? Link to issue if applicable -->

## How to Test

<!-- Steps to verify the change works -->

## Checklist

- [ ] Tests pass locally (`PYTHONPATH=. pytest tests/ --ignore=tests/test_telegram_concurrency.py -q`)
- [ ] Linter passes (`ruff check .`)
- [ ] Documentation updated (if applicable)
- [ ] No secrets committed (check with `git diff HEAD~1 | grep -E "(password|token|secret|key)"`)
- [ ] Commit messages follow convention
- [ ] New public functions have type hints and docstrings
```

---

## Issue Guidelines

### Bug Reports

Include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version, Docker version if relevant)
- Relevant logs or error messages (wrap long logs in `<details>`)
- Command used to trigger the bug

### Feature Requests

Include:
- The problem you are trying to solve (not just the solution you want)
- How you currently work around it (if applicable)
- Use case or example workflow
- Whether this belongs in core vs. a skill/plugin

### Skills, Workflows, or Integrations

- Link to any related issues or discussions
- Include example YAML or command invocation
- Describe error messages or unexpected behavior clearly

---

## Security

**Do not open public issues for security vulnerabilities.**

Report security issues via email to the maintainers. We will acknowledge receipt within 48 hours and provide an estimated fix timeline within 7 days.

See [docs/reference/SECURITY.md](docs/reference/SECURITY.md) for the full security policy.

---

## Tips for Success

- **Read the architecture first**: `docs/reference/architecture.md` explains how the eight subsystems interact.
- **Check `to-do.md`** for known issues and planned work.
- **Look at existing tests**: They often show intended usage better than docstrings.
- **Join discussions**: Open a [GitHub Discussion](https://github.com/SmartMur/claude-superpowers/discussions) for questions.
- **Skills are entry points**: New to the codebase? Start with a skill. They're smaller, testable in isolation, and impact the CLI immediately.

---

## Questions?

Open a [Discussion](https://github.com/SmartMur/claude-superpowers/discussions) for questions that are not bugs or feature requests.

---

**Thank you for contributing to the Nexus ecosystem.**
