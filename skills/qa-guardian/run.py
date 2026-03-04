#!/usr/bin/env python3
"""QA Guardian skill entry point — run checks, log to audit, notify Telegram."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from superpowers import telegram_notify  # noqa: E402
from superpowers.audit import AuditLog  # noqa: E402
from superpowers.config import get_data_dir  # noqa: E402
from superpowers.qa_guardian import QAGuardian  # noqa: E402


def main() -> int:
    """Run QA Guardian and report results."""
    guardian = QAGuardian(PROJECT_ROOT)

    # Run with live tests disabled by default (use --run-tests flag to enable)
    run_tests = "--run-tests" in sys.argv
    report = guardian.run_all(run_tests=run_tests)

    # Save report
    try:
        report_path = guardian.save_report(report)
        print(f"Report saved to {report_path}")
    except (OSError, ValueError) as exc:
        print(f"Warning: could not save report: {exc}", file=sys.stderr)

    # Audit log
    try:
        audit = AuditLog(get_data_dir() / "audit.log")
        audit.log(
            "qa_guardian.run",
            f"{report.checks_run} checks, {len(report.findings)} findings",
            source="skill",
            metadata=report.to_dict()["summary"],
        )
    except (OSError, ValueError):
        pass  # Audit failures are non-fatal

    # Print summary
    print(f"\nQA Guardian — {report.checks_run} checks run")
    print(f"  Critical: {report.critical_count}")
    print(f"  Warning:  {report.warning_count}")
    print(f"  Info:     {report.info_count}")
    print(f"  Duration: {report.duration_seconds:.1f}s")

    if report.findings:
        print("\nFindings:")
        for f in report.findings:
            loc = f"{f.file}:{f.line}" if f.file else ""
            print(f"  [{f.severity.upper():8s}] {f.check}: {f.message} {loc}")

    # Telegram notify
    try:
        if report.critical_count > 0:
            telegram_notify.notify_error(
                "QA Guardian",
                report.to_telegram_summary(),
            )
        elif report.is_clean:
            telegram_notify.notify_done("QA Guardian — all clear")
        else:
            telegram_notify.notify(report.to_telegram_summary())
    except (OSError, ImportError, ValueError):
        pass  # Notification failures are non-fatal

    # Exit code: 0=clean, 1=findings, 2=error
    if report.critical_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
