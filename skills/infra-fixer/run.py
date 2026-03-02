#!/usr/bin/env python3
"""Infra Fixer skill entry point — check all Docker infrastructure, fix issues, report."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from superpowers.infra_fixer import InfraFixer
from superpowers.audit import AuditLog
from superpowers.config import get_data_dir
from superpowers import telegram_notify


def main() -> int:
    """Run infrastructure health check."""
    auto_fix = "--no-fix" not in sys.argv
    fixer = InfraFixer()

    try:
        report = fixer.run_check(auto_fix=auto_fix)
    except Exception as exc:
        print(f"ERROR: Infra check failed: {exc}", file=sys.stderr)
        telegram_notify.notify_error("Infra Fixer", str(exc))
        return 2

    # Save report
    try:
        report_path = fixer.save_report(report)
        print(f"Report saved to {report_path}")
    except Exception as exc:
        print(f"Warning: could not save report: {exc}", file=sys.stderr)

    # Audit log
    try:
        audit = AuditLog(get_data_dir() / "audit.log")
        audit.log(
            f"infra_fixer.{report.status}",
            f"{report.containers_running}/{report.containers_total} running, {len(report.issues)} issues",
            source="skill",
            metadata=report.to_dict()["summary"],
        )
    except Exception:
        pass

    # Print summary
    print(f"\nInfra Fixer — Status: {report.status.upper()}")
    print(f"  Containers: {report.containers_running}/{report.containers_total} running")
    print(f"  Unhealthy:  {report.containers_unhealthy}")
    print(f"  Projects:   {report.projects_total}")
    print(f"  Duration:   {report.duration_seconds:.1f}s")

    if report.issues:
        print(f"\nIssues ({len(report.issues)}):")
        for issue in report.issues:
            target = issue.container or issue.project
            print(f"  [{issue.severity.upper():8s}] {target}: {issue.issue}")
            if issue.suggestion:
                print(f"             -> {issue.suggestion}")

    if report.actions_taken:
        print(f"\nActions taken ({len(report.actions_taken)}):")
        for action in report.actions_taken:
            print(f"  - {action}")

    # Telegram notify
    try:
        if report.status == "healthy":
            pass  # Don't spam on healthy checks
        elif report.critical_count > 0:
            telegram_notify.notify_error("Infra Fixer", report.to_telegram_summary())
        else:
            telegram_notify.notify(report.to_telegram_summary())
    except Exception:
        pass

    return 0 if report.status == "healthy" else 1


if __name__ == "__main__":
    sys.exit(main())
