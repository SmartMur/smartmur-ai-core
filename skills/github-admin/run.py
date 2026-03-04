#!/usr/bin/env python3
"""GitHub Admin skill entry point — auth, protect, audit, list repos."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from superpowers import telegram_notify  # noqa: E402
from superpowers.audit import AuditLog  # noqa: E402
from superpowers.config import get_data_dir  # noqa: E402
from superpowers.github_admin import GH_BIN, GitHubAdmin  # noqa: E402

USAGE = """\
GitHub administration tool.

Usage:
  github-admin auth      Check authentication status
  github-admin login     Authenticate with GitHub (device flow)
  github-admin protect   Enable branch protection on all repos
  github-admin audit     Audit branch protection status
  github-admin repos     List all repos
"""


def cmd_auth(admin: GitHubAdmin) -> int:
    """Check gh authentication status."""
    ok, output = admin.is_authenticated()
    if ok:
        print("Authenticated with GitHub")
        print(output)
        return 0
    else:
        print("NOT authenticated with GitHub")
        print(output)
        print()
        print("Run: /github-admin login")
        return 1


def cmd_login() -> int:
    """Start gh auth login device flow."""
    print("Starting GitHub device-flow authentication ...")
    print("A browser window will open (or a code + URL will be printed).\n")
    result = subprocess.run(
        [GH_BIN, "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web"],
        timeout=120,
    )
    return result.returncode


def cmd_repos(admin: GitHubAdmin) -> int:
    """List all repos."""
    try:
        repos = admin.list_repos()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not repos:
        print("No repos found.")
        return 0

    print(f"{'Repository':<40} {'Default Branch':<15} {'Private':<8} {'Fork'}")
    print("-" * 75)
    for r in repos:
        name = r.get("name", "?")
        branch_ref = r.get("defaultBranchRef")
        branch = branch_ref.get("name", "?") if isinstance(branch_ref, dict) else "?"
        private = "yes" if r.get("isPrivate") else "no"
        fork = "yes" if r.get("isFork") else "no"
        print(f"{name:<40} {branch:<15} {private:<8} {fork}")

    print(f"\nTotal: {len(repos)} repos")
    return 0


def cmd_protect(admin: GitHubAdmin) -> int:
    """Enable branch protection on all repos."""
    print("Enabling branch protection on all repos ...\n")

    results = admin.protect_all_repos()

    ok_count = sum(1 for r in results if r["ok"])
    fail_count = len(results) - ok_count

    print(f"{'Repository':<40} {'Branch':<15} {'Status'}")
    print("-" * 65)
    for r in results:
        status = "PROTECTED" if r["ok"] else f"FAILED: {r['detail']}"
        print(f"{r['repo']:<40} {r['branch']:<15} {status}")

    print(f"\nProtected: {ok_count}, Failed: {fail_count}")

    # Audit log
    try:
        audit = AuditLog(get_data_dir() / "audit.log")
        audit.log(
            "github_admin.protect",
            f"Protected {ok_count}/{len(results)} repos",
            source="skill",
            metadata={"ok": ok_count, "failed": fail_count},
        )
    except (OSError, ValueError):
        pass

    # Telegram notify
    try:
        summary = f"GitHub branch protection: {ok_count}/{len(results)} repos protected"
        if fail_count > 0:
            failed_names = [r["repo"] for r in results if not r["ok"]]
            summary += f"\nFailed: {', '.join(failed_names)}"
            telegram_notify.notify(f"[WARN] {summary}")
        else:
            telegram_notify.notify_done(summary)
    except (OSError, ImportError, ValueError):
        pass

    return 0 if fail_count == 0 else 1


def cmd_audit(admin: GitHubAdmin) -> int:
    """Audit branch protection status."""
    print("Auditing branch protection ...\n")

    results = admin.audit_protection()

    protected_count = sum(1 for r in results if r["protected"])
    unprotected_count = len(results) - protected_count

    print(f"{'Repository':<40} {'Branch':<15} {'Protected'}")
    print("-" * 65)
    for r in results:
        status = "YES" if r["protected"] else "NO"
        print(f"{r['repo']:<40} {r['branch']:<15} {status}")

    print(f"\nProtected: {protected_count}, Unprotected: {unprotected_count}")

    # Audit log
    try:
        audit = AuditLog(get_data_dir() / "audit.log")
        audit.log(
            "github_admin.audit",
            f"{protected_count}/{len(results)} repos protected",
            source="skill",
            metadata={
                "protected": protected_count,
                "unprotected": unprotected_count,
            },
        )
    except (OSError, ValueError):
        pass

    # Telegram notify if unprotected repos found
    try:
        if unprotected_count > 0:
            names = [r["repo"] for r in results if not r["protected"]]
            telegram_notify.notify(
                f"[AUDIT] {unprotected_count} unprotected repos: {', '.join(names)}"
            )
    except (OSError, ImportError, ValueError):
        pass

    return 0 if unprotected_count == 0 else 1


def main() -> int:
    """Dispatch subcommand."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    subcommand = sys.argv[1].lower()
    admin = GitHubAdmin()

    if subcommand == "auth":
        return cmd_auth(admin)
    elif subcommand == "login":
        return cmd_login()
    elif subcommand == "repos":
        return cmd_repos(admin)
    elif subcommand == "protect":
        return cmd_protect(admin)
    elif subcommand == "audit":
        return cmd_audit(admin)
    else:
        print(f"Unknown subcommand: {subcommand}\n")
        print(USAGE)
        return 2


if __name__ == "__main__":
    sys.exit(main())
