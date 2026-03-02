#!/usr/bin/env python3
"""Cloudflared Fixer skill entry point — check, diagnose, fix, report."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from superpowers.cloudflared_monitor import CloudflaredMonitor
from superpowers.audit import AuditLog
from superpowers.config import get_data_dir
from superpowers import telegram_notify


def main() -> int:
    """Run cloudflared health check and apply fixes."""
    monitor = CloudflaredMonitor()

    try:
        state, diagnosis = monitor.run_check()
    except Exception as exc:
        print(f"ERROR: Monitor failed: {exc}", file=sys.stderr)
        telegram_notify.notify_error("Cloudflared Monitor", str(exc))
        return 2

    # Audit log
    try:
        audit = AuditLog(get_data_dir() / "audit.log")
        audit.log(
            f"cloudflared.{diagnosis.status}",
            f"status={diagnosis.status}, issues={len(diagnosis.issues)}, fixes={len(diagnosis.actions_taken)}",
            source="skill",
            metadata=diagnosis.to_dict(),
        )
    except Exception:
        pass

    # Print status
    print(f"Cloudflared Monitor — Status: {diagnosis.status.upper()}")
    print(f"  Container running: {state.running}")
    print(f"  Restart count: {state.restart_count}")
    print(f"  Exit code: {state.exit_code}")

    if diagnosis.issues:
        print("\nIssues:")
        for issue in diagnosis.issues:
            print(f"  - {issue}")

    if diagnosis.actions_taken:
        print("\nActions taken:")
        for action in diagnosis.actions_taken:
            print(f"  - {action}")

    if diagnosis.needs_user_action:
        print(f"\nUSER ACTION REQUIRED: {diagnosis.user_action_message}")

    # Telegram notify
    try:
        if diagnosis.status == "healthy":
            # Don't spam on healthy checks — only notify if there were previous issues
            pass
        elif diagnosis.status in ("crash_loop", "down"):
            telegram_notify.notify_error(
                "Cloudflared Monitor",
                diagnosis.to_telegram_summary(),
            )
        elif diagnosis.status == "degraded":
            telegram_notify.notify(diagnosis.to_telegram_summary())
    except Exception:
        pass

    # Exit code
    if diagnosis.status == "healthy":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
