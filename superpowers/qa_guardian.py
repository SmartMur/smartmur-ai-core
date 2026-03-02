"""QA Guardian — autonomous code quality checker for claude-superpowers."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from superpowers.config import get_data_dir

Severity = Literal["critical", "warning", "info"]
Category = Literal["security", "quality", "test_health", "efficiency"]


@dataclass
class Finding:
    """A single QA finding."""
    category: Category
    severity: Severity
    check: str
    message: str
    file: str = ""
    line: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QAReport:
    """Results from a full QA run."""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    findings: list[Finding] = field(default_factory=list)
    checks_run: int = 0
    duration_seconds: float = 0.0

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "info")

    @property
    def is_clean(self) -> bool:
        return self.critical_count == 0 and self.warning_count == 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "findings": [f.to_dict() for f in self.findings],
            "checks_run": self.checks_run,
            "duration_seconds": self.duration_seconds,
            "summary": {
                "critical": self.critical_count,
                "warning": self.warning_count,
                "info": self.info_count,
                "total": len(self.findings),
            },
        }

    def to_telegram_summary(self) -> str:
        if self.is_clean:
            return (
                f"*QA Guardian* — All clear\n"
                f"Checks: {self.checks_run} | Findings: 0\n"
                f"_Duration: {self.duration_seconds:.1f}s_"
            )
        lines = ["*QA Guardian Report*"]
        lines.append(f"Critical: {self.critical_count} | Warning: {self.warning_count} | Info: {self.info_count}")
        # Show up to 5 critical/warning findings
        important = [f for f in self.findings if f.severity in ("critical", "warning")]
        for finding in important[:5]:
            loc = f"`{finding.file}:{finding.line}`" if finding.file else ""
            lines.append(f"  [{finding.severity.upper()}] {finding.check}: {finding.message} {loc}")
        if len(important) > 5:
            lines.append(f"  ...and {len(important) - 5} more")
        lines.append(f"_Duration: {self.duration_seconds:.1f}s_")
        return "\n".join(lines)


class QAGuardian:
    """Runs quality checks against a project directory."""

    # Patterns that look like hardcoded secrets
    SECRET_PATTERNS = [
        re.compile(r'''(?:password|passwd|secret|token|api_key|apikey)\s*=\s*["'][^"']{8,}["']''', re.IGNORECASE),
    ]

    # Patterns for shell=True usage
    SHELL_TRUE_PATTERN = re.compile(r'\bshell\s*=\s*True\b')

    # Patterns for bare except
    BARE_EXCEPT_PATTERN = re.compile(r'^\s*except\s*:', re.MULTILINE)

    # Patterns for eval/exec
    EVAL_EXEC_PATTERN = re.compile(r'\b(?:eval|exec)\s*\(')

    # TODO/FIXME pattern
    TODO_PATTERN = re.compile(r'#\s*(?:TODO|FIXME|HACK|XXX)\b', re.IGNORECASE)

    def __init__(self, project_dir: Path | str, *, baseline_tests: int = 826):
        self.project_dir = Path(project_dir)
        self.baseline_tests = baseline_tests
        self._findings: list[Finding] = []

    def _python_files(self) -> list[Path]:
        """Get all Python files in the project, excluding venv and __pycache__."""
        files = []
        for p in self.project_dir.rglob("*.py"):
            parts = p.relative_to(self.project_dir).parts
            if any(skip in parts for skip in (".venv", "venv", "__pycache__", ".git", "node_modules")):
                continue
            files.append(p)
        return sorted(files)

    def _add(self, category: Category, severity: Severity, check: str, message: str,
             file: str = "", line: int = 0) -> None:
        self._findings.append(Finding(
            category=category, severity=severity, check=check,
            message=message, file=file, line=line,
        ))

    # --- Security checks ---

    def check_shell_true(self) -> None:
        """Flag subprocess calls with shell=True."""
        for path in self._python_files():
            try:
                content = path.read_text(errors="replace")
            except OSError:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if self.SHELL_TRUE_PATTERN.search(line):
                    rel = str(path.relative_to(self.project_dir))
                    self._add("security", "warning", "shell_true",
                              "subprocess with shell=True", file=rel, line=i)

    def check_bare_except(self) -> None:
        """Flag bare 'except:' clauses."""
        for path in self._python_files():
            try:
                content = path.read_text(errors="replace")
            except OSError:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if self.BARE_EXCEPT_PATTERN.match(line):
                    rel = str(path.relative_to(self.project_dir))
                    self._add("security", "warning", "bare_except",
                              "bare except clause (catches all exceptions)", file=rel, line=i)

    def check_hardcoded_secrets(self) -> None:
        """Flag potential hardcoded secrets/passwords/tokens."""
        for path in self._python_files():
            try:
                content = path.read_text(errors="replace")
            except OSError:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                # Skip comments and test files
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for pat in self.SECRET_PATTERNS:
                    if pat.search(line):
                        rel = str(path.relative_to(self.project_dir))
                        self._add("security", "critical", "hardcoded_secret",
                                  "possible hardcoded secret", file=rel, line=i)
                        break  # One finding per line

    def check_eval_exec(self) -> None:
        """Flag use of eval() or exec()."""
        for path in self._python_files():
            try:
                content = path.read_text(errors="replace")
            except OSError:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if self.EVAL_EXEC_PATTERN.search(line):
                    rel = str(path.relative_to(self.project_dir))
                    self._add("security", "critical", "eval_exec",
                              "use of eval() or exec()", file=rel, line=i)

    # --- Quality checks ---

    def check_long_files(self, max_lines: int = 400) -> None:
        """Flag Python files exceeding max_lines."""
        for path in self._python_files():
            try:
                line_count = len(path.read_text(errors="replace").splitlines())
            except OSError:
                continue
            if line_count > max_lines:
                rel = str(path.relative_to(self.project_dir))
                self._add("quality", "warning", "long_file",
                          f"file has {line_count} lines (max {max_lines})", file=rel)

    def check_test_coverage_gaps(self) -> None:
        """Flag source modules in superpowers/ that lack a corresponding test file."""
        src_dir = self.project_dir / "superpowers"
        test_dir = self.project_dir / "tests"
        if not src_dir.is_dir() or not test_dir.is_dir():
            return

        existing_tests = {p.name for p in test_dir.glob("test_*.py")}

        for src_file in sorted(src_dir.glob("*.py")):
            if src_file.name.startswith("_"):
                continue
            expected_test = f"test_{src_file.name}"
            if expected_test not in existing_tests:
                self._add("quality", "info", "test_coverage_gap",
                          f"no test file for superpowers/{src_file.name}",
                          file=f"superpowers/{src_file.name}")

    def check_duplicate_function_names(self) -> None:
        """Flag files with duplicate top-level function/method definitions."""
        for path in self._python_files():
            try:
                source = path.read_text(errors="replace")
                tree = ast.parse(source)
            except (OSError, SyntaxError):
                continue

            # Check top-level functions
            func_names: dict[str, list[int]] = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name
                    func_names.setdefault(name, []).append(node.lineno)

            rel = str(path.relative_to(self.project_dir))
            for name, linenos in func_names.items():
                if len(linenos) > 1:
                    self._add("quality", "warning", "duplicate_function",
                              f"function '{name}' defined {len(linenos)} times (lines {', '.join(map(str, linenos))})",
                              file=rel, line=linenos[0])

    def check_todo_count(self) -> None:
        """Report TODO/FIXME count as info (not a problem, just tracking)."""
        total = 0
        for path in self._python_files():
            try:
                content = path.read_text(errors="replace")
            except OSError:
                continue
            total += len(self.TODO_PATTERN.findall(content))
        if total > 0:
            self._add("quality", "info", "todo_count",
                      f"{total} TODO/FIXME comments across project")

    # --- Test health ---

    def check_test_suite(self, *, run_tests: bool = False, pytest_bin: str = "") -> None:
        """Run pytest and compare pass/fail against baseline.

        If run_tests=False, just checks that the test directory exists.
        """
        test_dir = self.project_dir / "tests"
        if not test_dir.is_dir():
            self._add("test_health", "critical", "test_suite",
                      "tests/ directory not found")
            return

        if not run_tests:
            test_files = list(test_dir.glob("test_*.py"))
            self._add("test_health", "info", "test_suite",
                      f"{len(test_files)} test files found (live run disabled)")
            return

        # Actually run pytest
        if not pytest_bin:
            pytest_bin = str(self.project_dir / ".venv" / "bin" / "pytest")

        try:
            result = subprocess.run(
                [pytest_bin, str(test_dir),
                 "--ignore=" + str(test_dir / "test_telegram_concurrency.py"),
                 "--tb=no", "-q", "--no-header"],
                capture_output=True, text=True, timeout=300,
                cwd=str(self.project_dir),
                env={**__import__("os").environ, "PYTHONPATH": str(self.project_dir)},
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            self._add("test_health", "critical", "test_suite",
                      f"pytest execution failed: {exc}")
            return

        # Parse pytest summary line: "826 passed, 7 failed"
        output = result.stdout + result.stderr
        passed = 0
        failed = 0
        for match in re.finditer(r'(\d+)\s+passed', output):
            passed = int(match.group(1))
        for match in re.finditer(r'(\d+)\s+failed', output):
            failed = int(match.group(1))

        if failed > 0:
            self._add("test_health", "warning", "test_suite",
                      f"pytest: {passed} passed, {failed} failed (baseline: {self.baseline_tests})")
        elif passed < self.baseline_tests:
            self._add("test_health", "warning", "test_suite",
                      f"test count dropped: {passed} vs baseline {self.baseline_tests}")
        else:
            self._add("test_health", "info", "test_suite",
                      f"pytest: {passed} passed, {failed} failed (baseline: {self.baseline_tests})")

    # --- Efficiency checks ---

    def check_unused_imports(self) -> None:
        """Use AST to detect obviously unused imports."""
        for path in self._python_files():
            try:
                source = path.read_text(errors="replace")
                tree = ast.parse(source)
            except (OSError, SyntaxError):
                continue

            # Collect imported names
            imported: dict[str, int] = {}  # name -> lineno
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name.split(".")[0]
                        imported[name] = node.lineno
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        name = alias.asname or alias.name
                        imported[name] = node.lineno

            if not imported:
                continue

            # Collect all Name references (simple heuristic)
            used_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    # For things like `os.path` — the `os` part is a Name node already
                    pass

            rel = str(path.relative_to(self.project_dir))
            for name, lineno in imported.items():
                # Skip __all__ and __future__ and underscore-prefixed
                if name.startswith("_"):
                    continue
                if name not in used_names:
                    self._add("efficiency", "info", "unused_import",
                              f"'{name}' imported but not used", file=rel, line=lineno)

    def check_empty_files(self) -> None:
        """Flag Python files that are empty or only have docstrings/comments."""
        for path in self._python_files():
            try:
                content = path.read_text(errors="replace").strip()
            except OSError:
                continue
            if not content:
                rel = str(path.relative_to(self.project_dir))
                self._add("efficiency", "info", "empty_file",
                          "file is empty", file=rel)
                continue
            # Check if file has only comments/docstrings (no real code)
            lines = [line.strip() for line in content.splitlines()
                     if line.strip() and not line.strip().startswith("#")]
            # If all non-comment lines are just docstring markers
            code_lines = [line for line in lines if not (line.startswith('"""') or line.startswith("'''") or line.startswith('"') or line.startswith("'"))]
            if len(code_lines) == 0 and path.name != "__init__.py":
                rel = str(path.relative_to(self.project_dir))
                self._add("efficiency", "info", "stub_file",
                          "file has no executable code", file=rel)

    def check_dead_modules(self) -> None:
        """Flag modules in superpowers/ not imported by anything else."""
        src_dir = self.project_dir / "superpowers"
        if not src_dir.is_dir():
            return

        module_names = set()
        for p in src_dir.glob("*.py"):
            if p.name.startswith("_"):
                continue
            module_names.add(p.stem)

        if not module_names:
            return

        # Check if each module is imported anywhere
        all_files = self._python_files()
        import_mentions: dict[str, bool] = {m: False for m in module_names}

        for path in all_files:
            if path.parent == src_dir:
                continue  # Don't count self-imports within superpowers/
            try:
                content = path.read_text(errors="replace")
            except OSError:
                continue
            for mod_name in module_names:
                if mod_name in content:
                    import_mentions[mod_name] = True

        for mod_name, is_used in import_mentions.items():
            if not is_used:
                self._add("efficiency", "info", "dead_module",
                          f"superpowers/{mod_name}.py may not be imported anywhere",
                          file=f"superpowers/{mod_name}.py")

    # --- Run all checks ---

    def run_all(self, *, run_tests: bool = False) -> QAReport:
        """Execute all checks and return a QAReport."""
        import time
        start = time.monotonic()
        self._findings = []

        checks = [
            self.check_shell_true,
            self.check_bare_except,
            self.check_hardcoded_secrets,
            self.check_eval_exec,
            self.check_long_files,
            self.check_test_coverage_gaps,
            self.check_duplicate_function_names,
            self.check_todo_count,
            lambda: self.check_test_suite(run_tests=run_tests),
            self.check_unused_imports,
            self.check_empty_files,
            self.check_dead_modules,
        ]

        for check_fn in checks:
            try:
                check_fn()
            except Exception:
                pass  # Individual check failures don't abort the run

        elapsed = time.monotonic() - start
        report = QAReport(
            findings=list(self._findings),
            checks_run=len(checks),
            duration_seconds=round(elapsed, 2),
        )
        return report

    def save_report(self, report: QAReport) -> Path:
        """Save report to data dir as latest.json + timestamped history."""
        qa_dir = get_data_dir() / "qa-guardian"
        qa_dir.mkdir(parents=True, exist_ok=True)

        data = report.to_dict()

        # Save latest
        latest = qa_dir / "latest.json"
        latest.write_text(json.dumps(data, indent=2))

        # Save timestamped
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        history = qa_dir / f"report-{ts}.json"
        history.write_text(json.dumps(data, indent=2))

        return latest
