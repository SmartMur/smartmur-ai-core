#!/usr/bin/env python3
"""Network scan skill entry point — discover hosts, check ports, report status."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from superpowers import telegram_notify  # noqa: E402
from superpowers.audit import AuditLog  # noqa: E402
from superpowers.config import get_data_dir  # noqa: E402
from superpowers.network_scanner import (  # noqa: E402
    format_port_detail,
    format_table,
    load_config,
    run_scan,
)


def main() -> int:
    """Run network scan and print results."""
    config = load_config()

    try:
        report = run_scan(
            hosts=config["hosts"],
            subnets=config["subnets"],
            ports=config["ports"],
            critical=config["critical"],
            timeout=config["timeout"],
            workers=config["workers"],
        )
    except Exception as exc:
        print(f"ERROR: Scan failed: {exc}", file=sys.stderr)
        telegram_notify.notify_error("Network Scan", str(exc))
        return 2

    # Print results
    print(format_table(report))
    print(format_port_detail(report))

    # Audit log
    try:
        audit = AuditLog(get_data_dir() / "audit.log")
        audit.log(
            "network_scan.complete",
            f"hosts={report.total_hosts}, up={report.hosts_up}, down={report.hosts_down}",
            source="skill",
            metadata={
                "total": report.total_hosts,
                "up": report.hosts_up,
                "down": report.hosts_down,
                "critical_down": report.critical_down,
                "scan_time": report.scan_time_seconds,
            },
        )
    except (ImportError, OSError, ValueError):
        pass

    # Telegram notify (only on failures)
    try:
        if report.critical_down:
            msg = (
                f"[ALERT] Network Scan: {len(report.critical_down)} critical host(s) DOWN\n"
                f"Down: {', '.join(report.critical_down)}\n"
                f"Up: {report.hosts_up}/{report.total_hosts}"
            )
            telegram_notify.notify_error("Network Scan", msg)
        # Don't spam on success
    except (ImportError, OSError, ValueError):
        pass

    # Exit code: 0 if all critical hosts up, 1 otherwise
    if report.all_critical_up:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
