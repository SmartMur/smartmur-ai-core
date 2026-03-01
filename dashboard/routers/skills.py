"""Skills: list, info, run."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dashboard.deps import get_skill_registry
from dashboard.models import SkillDetail, SkillOut, SkillRunRequest, SkillRunResult

router = APIRouter()


@router.get("", response_model=list[SkillOut])
def list_skills():
    sr = get_skill_registry()
    return [
        SkillOut(
            name=s.name,
            description=s.description,
            version=s.version,
            author=s.author,
        )
        for s in sr.list_skills()
    ]


@router.get("/{name}", response_model=SkillDetail)
def get_skill(name: str):
    sr = get_skill_registry()
    try:
        s = sr.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillDetail(
        name=s.name,
        description=s.description,
        version=s.version,
        author=s.author,
        triggers=s.triggers,
        dependencies=s.dependencies,
        permissions=s.permissions,
    )


@router.post("/{name}/run", response_model=SkillRunResult)
def run_skill(name: str, req: SkillRunRequest):
    sr = get_skill_registry()
    try:
        skill = sr.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")

    from superpowers.skill_loader import SkillLoader
    loader = SkillLoader()
    result = loader.run(skill, req.args or None)
    return SkillRunResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
    )
