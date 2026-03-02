"""GET /api/status — aggregate health of all subsystems."""

from __future__ import annotations

from fastapi import APIRouter

from dashboard.models import AggregateStatus, SubsystemStatus

router = APIRouter()


@router.get("/status", response_model=AggregateStatus)
def aggregate_status():
    subs: list[SubsystemStatus] = []

    # Cron
    try:
        from dashboard.deps import get_cron_engine
        engine = get_cron_engine()
        jobs = engine.list_jobs()
        enabled = sum(1 for j in jobs if j.enabled)
        subs.append(SubsystemStatus(
            name="cron", ok=True,
            detail=f"{len(jobs)} jobs ({enabled} enabled)",
            count=len(jobs),
        ))
    except Exception:
        subs.append(SubsystemStatus(name="cron", ok=False, detail="unavailable"))

    # Channels
    try:
        from dashboard.deps import get_channel_registry
        reg = get_channel_registry()
        available = reg.available()
        subs.append(SubsystemStatus(
            name="channels", ok=True,
            detail=", ".join(available) if available else "none configured",
            count=len(available),
        ))
    except Exception:
        subs.append(SubsystemStatus(name="channels", ok=False, detail="unavailable"))

    # SSH
    try:
        from dashboard.deps import get_host_registry
        hosts = get_host_registry()
        host_list = hosts.list_hosts()
        groups = hosts.groups()
        subs.append(SubsystemStatus(
            name="ssh", ok=True,
            detail=f"{len(host_list)} hosts, {len(groups)} groups",
            count=len(host_list),
        ))
    except Exception:
        subs.append(SubsystemStatus(name="ssh", ok=False, detail="unavailable"))

    # Workflows
    try:
        from dashboard.deps import get_workflow_loader
        loader = get_workflow_loader()
        names = loader.list_workflows()
        subs.append(SubsystemStatus(
            name="workflows", ok=True,
            detail=f"{len(names)} workflows",
            count=len(names),
        ))
    except Exception:
        subs.append(SubsystemStatus(name="workflows", ok=False, detail="unavailable"))

    # Memory
    try:
        from dashboard.deps import get_memory_store
        store = get_memory_store()
        stats = store.stats()
        subs.append(SubsystemStatus(
            name="memory", ok=True,
            detail=f"{stats['total']} entries",
            count=stats["total"],
        ))
    except Exception:
        subs.append(SubsystemStatus(name="memory", ok=False, detail="unavailable"))

    # Skills
    try:
        from dashboard.deps import get_skill_registry
        sr = get_skill_registry()
        skills = sr.list_skills()
        subs.append(SubsystemStatus(
            name="skills", ok=True,
            detail=", ".join(s.name for s in skills) if skills else "none",
            count=len(skills),
        ))
    except Exception:
        subs.append(SubsystemStatus(name="skills", ok=False, detail="unavailable"))

    # Vault
    try:
        from superpowers.config import get_data_dir
        vault_file = get_data_dir() / "vault.enc"
        initialized = vault_file.exists()
        subs.append(SubsystemStatus(
            name="vault", ok=initialized,
            detail="initialized" if initialized else "not initialized",
        ))
    except Exception:
        subs.append(SubsystemStatus(name="vault", ok=False, detail="unavailable"))

    # Watchers
    try:
        from dashboard.deps import get_watcher_engine
        we = get_watcher_engine()
        rules = we.list_rules()
        enabled = sum(1 for r in rules if r.enabled)
        subs.append(SubsystemStatus(
            name="watchers", ok=True,
            detail=f"{len(rules)} rules ({enabled} enabled)",
            count=len(rules),
        ))
    except Exception:
        subs.append(SubsystemStatus(name="watchers", ok=False, detail="unavailable"))

    # Audit
    try:
        from dashboard.deps import get_audit_log
        audit = get_audit_log()
        recent = audit.tail(5)
        subs.append(SubsystemStatus(
            name="audit", ok=True,
            detail=f"{len(recent)} recent entries",
            count=len(recent),
        ))
    except Exception:
        subs.append(SubsystemStatus(name="audit", ok=False, detail="unavailable"))

    # Browser
    try:
        from dashboard.deps import get_browser_profiles
        pm = get_browser_profiles()
        profiles = pm.list_profiles()
        subs.append(SubsystemStatus(
            name="browser", ok=True,
            detail=f"{len(profiles)} profiles",
            count=len(profiles),
        ))
    except Exception:
        subs.append(SubsystemStatus(name="browser", ok=False, detail="unavailable"))

    return AggregateStatus(subsystems=subs)
