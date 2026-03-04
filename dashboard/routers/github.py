"""GitHub security monitoring — repo listing, branch protection, audit."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from dashboard.deps import get_github_admin
from dashboard.models import (
    GitHubAuditFinding,
    GitHubProtectionOut,
    GitHubRepoOut,
    GitHubSecurityStatus,
)

router = APIRouter()


@router.get("/status", response_model=GitHubSecurityStatus)
def github_status():
    ga = get_github_admin()
    authed, detail = ga.is_authenticated()
    if not authed:
        return GitHubSecurityStatus(
            authenticated=False,
            auth_detail=detail,
            timestamp=datetime.now(UTC).isoformat(),
        )

    try:
        audit = ga.audit_protection()
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyError) as exc:
        return GitHubSecurityStatus(
            authenticated=True,
            auth_detail=detail,
            repo_count=0,
            timestamp=datetime.now(UTC).isoformat(),
        )

    protected = [r for r in audit if r["protected"]]
    unprotected = [r["repo"] for r in audit if not r["protected"]]

    return GitHubSecurityStatus(
        authenticated=True,
        auth_detail=detail,
        repo_count=len(audit),
        protected_count=len(protected),
        unprotected_repos=unprotected,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/repos", response_model=list[GitHubRepoOut])
def list_repos():
    ga = get_github_admin()
    try:
        api_repos = ga.list_repos()
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    audit = {}
    try:
        for entry in ga.audit_protection():
            audit[entry["repo"]] = entry["protected"]
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyError):
        pass

    result = []
    for r in api_repos:
        branch_ref = r.get("defaultBranchRef")
        branch = branch_ref.get("name", "main") if isinstance(branch_ref, dict) else "main"
        result.append(
            GitHubRepoOut(
                name=r["name"],
                default_branch=branch,
                is_private=r.get("isPrivate", False),
                is_fork=r.get("isFork", False),
                protected=audit.get(r["name"], False),
            )
        )
    return result


@router.get("/repos/{repo}/protection", response_model=GitHubProtectionOut | None)
def get_protection(repo: str):
    ga = get_github_admin()
    repos = ga.get_repo_branches()
    branch = "main"
    for r in repos:
        if r["repo"] == repo:
            branch = r["branch"]
            break

    protection = ga.get_branch_protection(repo, branch)
    if protection is None:
        return None

    reviews = protection.get("required_pull_request_reviews", {}) or {}
    return GitHubProtectionOut(
        repo=repo,
        branch=branch,
        enforce_admins=bool(protection.get("enforce_admins", {}).get("enabled", False)),
        require_reviews=reviews is not None and bool(reviews),
        required_approvals=reviews.get("required_approving_review_count", 0) if reviews else 0,
        dismiss_stale=reviews.get("dismiss_stale_reviews", False) if reviews else False,
        allow_force_push=bool(protection.get("allow_force_pushes", {}).get("enabled", True)),
        allow_deletions=bool(protection.get("allow_deletions", {}).get("enabled", True)),
    )


@router.get("/audit", response_model=list[GitHubAuditFinding])
def audit_repos():
    ga = get_github_admin()
    findings = []

    try:
        authed, detail = ga.is_authenticated()
        if not authed:
            findings.append(
                GitHubAuditFinding(
                    severity="critical",
                    repo="(all)",
                    finding="GitHub CLI not authenticated",
                    detail=detail,
                )
            )
            return findings
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        findings.append(
            GitHubAuditFinding(
                severity="critical",
                repo="(all)",
                finding="GitHub CLI unavailable",
                detail=str(e),
            )
        )
        return findings

    try:
        audit = ga.audit_protection()
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyError) as e:
        findings.append(
            GitHubAuditFinding(
                severity="critical",
                repo="(all)",
                finding="Failed to audit repos",
                detail=str(e),
            )
        )
        return findings

    for entry in audit:
        repo = entry["repo"]
        if not entry["protected"]:
            findings.append(
                GitHubAuditFinding(
                    severity="critical",
                    repo=repo,
                    finding="No branch protection",
                    detail=f"Branch '{entry['branch']}' has no protection rules",
                )
            )
        else:
            details = entry.get("details", {}) or {}
            reviews = details.get("required_pull_request_reviews")
            enforce = details.get("enforce_admins", {})
            force_push = details.get("allow_force_pushes", {})

            if not enforce.get("enabled", False):
                findings.append(
                    GitHubAuditFinding(
                        severity="warning",
                        repo=repo,
                        finding="Admins can bypass protection",
                        detail="enforce_admins is disabled",
                    )
                )

            if not reviews:
                findings.append(
                    GitHubAuditFinding(
                        severity="warning",
                        repo=repo,
                        finding="No review requirement",
                        detail="Pull request reviews are not required",
                    )
                )

            if force_push.get("enabled", True):
                findings.append(
                    GitHubAuditFinding(
                        severity="warning",
                        repo=repo,
                        finding="Force push allowed",
                        detail="Force pushes are not blocked on the default branch",
                    )
                )

    if not findings:
        findings.append(
            GitHubAuditFinding(
                severity="info",
                repo="(all)",
                finding="All repos pass security checks",
                detail=f"{len(audit)} repos audited",
            )
        )

    return findings


@router.post("/repos/{repo}/protect")
def protect_repo(repo: str):
    ga = get_github_admin()
    repos = ga.get_repo_branches()
    branch = "main"
    for r in repos:
        if r["repo"] == repo:
            branch = r["branch"]
            break

    ok, detail = ga.enable_branch_protection(repo, branch)
    if not ok:
        raise HTTPException(status_code=502, detail=detail)
    return {"ok": True, "repo": repo, "branch": branch, "detail": detail}
