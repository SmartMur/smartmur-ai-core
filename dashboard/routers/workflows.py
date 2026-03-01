"""Workflows: list, show, validate, run."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from dashboard.deps import get_workflow_engine, get_workflow_loader
from dashboard.models import (
    StepResultOut,
    WorkflowDetail,
    WorkflowOut,
    WorkflowRunRequest,
)

router = APIRouter()


@router.get("", response_model=list[WorkflowOut])
def list_workflows():
    loader = get_workflow_loader()
    names = loader.list_workflows()
    out = []
    for name in names:
        try:
            config = loader.load(name)
            out.append(WorkflowOut(
                name=config.name,
                description=config.description,
                step_count=len(config.steps),
            ))
        except Exception:
            out.append(WorkflowOut(name=name, description="(failed to load)"))
    return out


@router.get("/{name}", response_model=WorkflowDetail)
def get_workflow(name: str):
    loader = get_workflow_loader()
    try:
        config = loader.load(name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return WorkflowDetail(
        name=config.name,
        description=config.description,
        steps=[asdict(s) for s in config.steps],
        rollback_steps=[asdict(s) for s in config.rollback_steps],
        notify_profile=config.notify_profile,
    )


@router.post("/{name}/validate")
def validate_workflow(name: str):
    loader = get_workflow_loader()
    try:
        config = loader.load(name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    errors = loader.validate(config)
    return {"valid": len(errors) == 0, "errors": errors}


@router.post("/{name}/run", response_model=list[StepResultOut])
def run_workflow(name: str, req: WorkflowRunRequest):
    loader = get_workflow_loader()
    engine = get_workflow_engine()
    try:
        config = loader.load(name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    results = engine.run(config, dry_run=req.dry_run)
    return [
        StepResultOut(
            step_name=r.step_name,
            status=r.status.value,
            output=r.output,
            error=r.error,
        )
        for r in results
    ]
