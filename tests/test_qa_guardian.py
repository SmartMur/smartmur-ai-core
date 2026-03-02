"""Tests for the QA Guardian — autonomous code quality checker."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from superpowers.qa_guardian import Finding, QAGuardian, QAReport

# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

class TestFinding:
    def test_create_finding(self):
        f = Finding(category="security", severity="critical", check="test", message="msg")
        assert f.category == "security"
        assert f.severity == "critical"
        assert f.file == ""
        assert f.line == 0

    def test_finding_with_location(self):
        f = Finding(category="quality", severity="warning", check="c", message="m",
                    file="foo.py", line=42)
        assert f.file == "foo.py"
        assert f.line == 42

    def test_finding_to_dict(self):
        f = Finding(category="security", severity="critical", check="eval_exec",
                    message="use of eval()", file="bad.py", line=10)
        d = f.to_dict()
        assert d["category"] == "security"
        assert d["file"] == "bad.py"
        assert d["line"] == 10


# ---------------------------------------------------------------------------
# QAReport
# ---------------------------------------------------------------------------

class TestQAReport:
    def test_empty_report(self):
        r = QAReport()
        assert r.is_clean
        assert r.critical_count == 0
        assert r.warning_count == 0
        assert r.info_count == 0

    def test_report_counts(self):
        r = QAReport(findings=[
            Finding("security", "critical", "a", "x"),
            Finding("security", "critical", "b", "y"),
            Finding("quality", "warning", "c", "z"),
            Finding("efficiency", "info", "d", "w"),
        ])
        assert r.critical_count == 2
        assert r.warning_count == 1
        assert r.info_count == 1
        assert not r.is_clean

    def test_report_to_dict(self):
        r = QAReport(checks_run=12, findings=[
            Finding("security", "critical", "eval_exec", "found eval"),
        ])
        d = r.to_dict()
        assert d["checks_run"] == 12
        assert d["summary"]["critical"] == 1
        assert len(d["findings"]) == 1

    def test_telegram_summary_clean(self):
        r = QAReport(checks_run=12, duration_seconds=1.5)
        msg = r.to_telegram_summary()
        assert "All clear" in msg

    def test_telegram_summary_with_findings(self):
        r = QAReport(checks_run=12, findings=[
            Finding("security", "critical", "eval_exec", "eval() used", "bad.py", 5),
        ])
        msg = r.to_telegram_summary()
        assert "CRITICAL" in msg
        assert "eval_exec" in msg


# ---------------------------------------------------------------------------
# QAGuardian — security checks
# ---------------------------------------------------------------------------

class TestSecurityChecks:
    def test_detect_shell_true(self, tmp_path):
        (tmp_path / "bad.py").write_text("subprocess.run(cmd, shell=True)\n")
        g = QAGuardian(tmp_path)
        g.check_shell_true()
        assert any(f.check == "shell_true" for f in g._findings)

    def test_no_shell_true(self, tmp_path):
        (tmp_path / "good.py").write_text("subprocess.run(cmd)\n")
        g = QAGuardian(tmp_path)
        g.check_shell_true()
        assert not g._findings

    def test_detect_bare_except(self, tmp_path):
        code = "try:\n    pass\nexcept:\n    pass\n"
        (tmp_path / "bad.py").write_text(code)
        g = QAGuardian(tmp_path)
        g.check_bare_except()
        assert any(f.check == "bare_except" for f in g._findings)

    def test_no_bare_except(self, tmp_path):
        code = "try:\n    pass\nexcept Exception:\n    pass\n"
        (tmp_path / "good.py").write_text(code)
        g = QAGuardian(tmp_path)
        g.check_bare_except()
        assert not g._findings

    def test_detect_hardcoded_secret(self, tmp_path):
        (tmp_path / "bad.py").write_text('password = "supersecret123"\n')
        g = QAGuardian(tmp_path)
        g.check_hardcoded_secrets()
        assert any(f.check == "hardcoded_secret" for f in g._findings)

    def test_skip_comments_for_secrets(self, tmp_path):
        (tmp_path / "ok.py").write_text('# password = "supersecret123"\n')
        g = QAGuardian(tmp_path)
        g.check_hardcoded_secrets()
        assert not g._findings

    def test_detect_eval(self, tmp_path):
        (tmp_path / "bad.py").write_text('result = eval(user_input)\n')
        g = QAGuardian(tmp_path)
        g.check_eval_exec()
        assert any(f.check == "eval_exec" for f in g._findings)

    def test_detect_exec(self, tmp_path):
        (tmp_path / "bad.py").write_text('exec(code_string)\n')
        g = QAGuardian(tmp_path)
        g.check_eval_exec()
        assert any(f.check == "eval_exec" for f in g._findings)

    def test_no_eval_in_comment(self, tmp_path):
        (tmp_path / "ok.py").write_text('# eval(this) is dangerous\n')
        g = QAGuardian(tmp_path)
        g.check_eval_exec()
        assert not g._findings


# ---------------------------------------------------------------------------
# QAGuardian — quality checks
# ---------------------------------------------------------------------------

class TestQualityChecks:
    def test_detect_long_file(self, tmp_path):
        (tmp_path / "big.py").write_text("x = 1\n" * 500)
        g = QAGuardian(tmp_path)
        g.check_long_files(max_lines=400)
        assert any(f.check == "long_file" for f in g._findings)

    def test_no_long_file(self, tmp_path):
        (tmp_path / "small.py").write_text("x = 1\n" * 50)
        g = QAGuardian(tmp_path)
        g.check_long_files(max_lines=400)
        assert not g._findings

    def test_test_coverage_gap(self, tmp_path):
        (tmp_path / "superpowers").mkdir()
        (tmp_path / "superpowers" / "mymod.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        g = QAGuardian(tmp_path)
        g.check_test_coverage_gaps()
        assert any(f.check == "test_coverage_gap" for f in g._findings)

    def test_no_coverage_gap(self, tmp_path):
        (tmp_path / "superpowers").mkdir()
        (tmp_path / "superpowers" / "mymod.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_mymod.py").write_text("pass\n")
        g = QAGuardian(tmp_path)
        g.check_test_coverage_gaps()
        assert not any(f.check == "test_coverage_gap" for f in g._findings)

    def test_detect_duplicate_functions(self, tmp_path):
        code = "def foo():\n    pass\n\ndef foo():\n    pass\n"
        (tmp_path / "dup.py").write_text(code)
        g = QAGuardian(tmp_path)
        g.check_duplicate_function_names()
        assert any(f.check == "duplicate_function" for f in g._findings)

    def test_todo_count(self, tmp_path):
        (tmp_path / "a.py").write_text("# TODO fix this\n# FIXME broken\nx = 1\n")
        g = QAGuardian(tmp_path)
        g.check_todo_count()
        assert any(f.check == "todo_count" and "2" in f.message for f in g._findings)


# ---------------------------------------------------------------------------
# QAGuardian — test health checks
# ---------------------------------------------------------------------------

class TestTestHealth:
    def test_no_test_dir(self, tmp_path):
        g = QAGuardian(tmp_path)
        g.check_test_suite()
        assert any(f.check == "test_suite" and f.severity == "critical" for f in g._findings)

    def test_test_dir_exists_no_run(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("pass\n")
        g = QAGuardian(tmp_path)
        g.check_test_suite(run_tests=False)
        assert any("1 test files found" in f.message for f in g._findings)

    @patch("subprocess.run")
    def test_pytest_pass(self, mock_run, tmp_path):
        (tmp_path / "tests").mkdir()
        mock_run.return_value = MagicMock(
            stdout="826 passed\n", stderr="", returncode=0
        )
        g = QAGuardian(tmp_path, baseline_tests=826)
        g.check_test_suite(run_tests=True, pytest_bin="pytest")
        assert any("826 passed" in f.message for f in g._findings)

    @patch("subprocess.run")
    def test_pytest_regression(self, mock_run, tmp_path):
        (tmp_path / "tests").mkdir()
        mock_run.return_value = MagicMock(
            stdout="800 passed, 5 failed\n", stderr="", returncode=1
        )
        g = QAGuardian(tmp_path, baseline_tests=826)
        g.check_test_suite(run_tests=True, pytest_bin="pytest")
        assert any(f.severity == "warning" and "failed" in f.message for f in g._findings)


# ---------------------------------------------------------------------------
# QAGuardian — efficiency checks
# ---------------------------------------------------------------------------

class TestEfficiencyChecks:
    def test_detect_unused_import(self, tmp_path):
        (tmp_path / "unused.py").write_text("import os\nx = 1\n")
        g = QAGuardian(tmp_path)
        g.check_unused_imports()
        assert any(f.check == "unused_import" and "os" in f.message for f in g._findings)

    def test_no_unused_import(self, tmp_path):
        (tmp_path / "used.py").write_text("import os\nprint(os.getcwd())\n")
        g = QAGuardian(tmp_path)
        g.check_unused_imports()
        assert not any(f.check == "unused_import" and "os" in f.message for f in g._findings)

    def test_detect_empty_file(self, tmp_path):
        (tmp_path / "empty.py").write_text("")
        g = QAGuardian(tmp_path)
        g.check_empty_files()
        assert any(f.check == "empty_file" for f in g._findings)

    def test_init_not_flagged_as_stub(self, tmp_path):
        (tmp_path / "__init__.py").write_text('"""Package."""\n')
        g = QAGuardian(tmp_path)
        g.check_empty_files()
        assert not any(f.check == "stub_file" for f in g._findings)

    def test_detect_dead_module(self, tmp_path):
        (tmp_path / "superpowers").mkdir()
        (tmp_path / "superpowers" / "orphan.py").write_text("x = 1\n")
        (tmp_path / "main.py").write_text("print('hello')\n")
        g = QAGuardian(tmp_path)
        g.check_dead_modules()
        assert any(f.check == "dead_module" for f in g._findings)


# ---------------------------------------------------------------------------
# QAGuardian — run_all integration
# ---------------------------------------------------------------------------

class TestRunAll:
    def test_run_all_returns_report(self, tmp_path):
        (tmp_path / "ok.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        g = QAGuardian(tmp_path)
        report = g.run_all()
        assert isinstance(report, QAReport)
        assert report.checks_run == 12
        assert report.duration_seconds >= 0

    def test_run_all_clean_project(self, tmp_path):
        (tmp_path / "good.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_good.py").write_text("pass\n")
        g = QAGuardian(tmp_path)
        report = g.run_all()
        assert isinstance(report, QAReport)

    @patch("superpowers.qa_guardian.get_data_dir")
    def test_save_report(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path / "data"
        g = QAGuardian(tmp_path)
        report = QAReport(checks_run=12)
        path = g.save_report(report)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["checks_run"] == 12

    @patch("superpowers.qa_guardian.get_data_dir")
    def test_save_report_creates_history(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path / "data"
        g = QAGuardian(tmp_path)
        report = QAReport(checks_run=12)
        g.save_report(report)
        history_files = list((tmp_path / "data" / "qa-guardian").glob("report-*.json"))
        assert len(history_files) == 1


# ---------------------------------------------------------------------------
# QAGuardian — file filtering
# ---------------------------------------------------------------------------

class TestFileFiltering:
    def test_excludes_venv(self, tmp_path):
        (tmp_path / ".venv" / "lib").mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "bad.py").write_text("eval(x)\n")
        (tmp_path / "good.py").write_text("x = 1\n")
        g = QAGuardian(tmp_path)
        files = g._python_files()
        assert all(".venv" not in str(f) for f in files)

    def test_excludes_pycache(self, tmp_path):
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.cpython-311.pyc").write_text("")
        (tmp_path / "good.py").write_text("x = 1\n")
        g = QAGuardian(tmp_path)
        files = g._python_files()
        assert all("__pycache__" not in str(f) for f in files)
