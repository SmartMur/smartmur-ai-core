"""SSH: hosts, groups, run commands, health check."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dashboard.deps import get_health_checker, get_host_registry, get_ssh_executor
from dashboard.models import SSHCommandResult, SSHHealthOut, SSHHostOut, SSHRunRequest

router = APIRouter()


@router.get("/hosts", response_model=list[SSHHostOut])
def list_hosts():
    hosts = get_host_registry()
    return [
        SSHHostOut(
            alias=h.alias,
            hostname=h.hostname,
            port=h.port,
            username=h.username,
            groups=h.groups,
        )
        for h in hosts.list_hosts()
    ]


@router.get("/groups")
def list_groups():
    hosts = get_host_registry()
    return hosts.groups()


@router.post("/run", response_model=list[SSHCommandResult])
def run_command(req: SSHRunRequest):
    executor = get_ssh_executor()
    try:
        results = executor.run(req.target, req.command, timeout=req.timeout)
    except (OSError, RuntimeError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return [
        SSHCommandResult(
            host=r.host,
            command=r.command,
            stdout=r.stdout,
            stderr=r.stderr,
            exit_code=r.exit_code,
            ok=r.ok,
            error=r.error,
        )
        for r in results
    ]


@router.get("/health", response_model=list[SSHHealthOut])
def health_check():
    checker = get_health_checker()
    report = checker.check_all()
    return [
        SSHHealthOut(
            alias=h.alias,
            hostname=h.hostname,
            ping_ok=h.ping_ok,
            ssh_ok=h.ssh_ok,
            uptime=h.uptime,
            load_avg=h.load_avg,
            latency_ms=h.latency_ms,
            error=h.error,
        )
        for h in report.hosts
    ]
