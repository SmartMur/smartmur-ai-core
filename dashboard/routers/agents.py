"""Agent router: list, recommend, and inspect subagents via the dashboard API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AgentOut(BaseModel):
    """Summary of a registered agent."""

    name: str
    description: str
    tags: list[str] = []
    skills: list[str] = []
    triggers: list[str] = []


class AgentDetail(AgentOut):
    """Full agent detail including the path to agent.md."""

    path: str = ""


class TechStackOut(BaseModel):
    """Detected tech stack for a repository."""

    languages: dict[str, int] = {}
    frameworks: list[str] = []
    tools: list[str] = []
    primary_language: str = ""


class AgentRecommendation(BaseModel):
    """A single agent recommendation with score and reasoning."""

    name: str
    description: str
    score: float
    reasons: list[str] = []
    tags: list[str] = []


class RecommendResponse(BaseModel):
    """Full recommendation response including optional tech stack."""

    recommendations: list[AgentRecommendation] = []
    tech_stack: TechStackOut | None = None
    task: str = ""
    repo: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _get_registry():
    """Lazy-import and return a configured AgentRegistry."""
    from superpowers.agent_registry import AgentRegistry

    return AgentRegistry()


@router.get("", response_model=list[AgentOut])
def list_agents():
    """List all discovered agents."""
    try:
        registry = _get_registry()
        agents = registry.list()
        return [
            AgentOut(
                name=a.name,
                description=a.description,
                tags=a.tags,
                skills=a.skills,
                triggers=a.triggers,
            )
            for a in agents
        ]
    except (ImportError, OSError, RuntimeError) as exc:
        logger.warning("Failed to list agents: %s", exc)
        return []


@router.get("/recommend", response_model=RecommendResponse)
def recommend_agents(
    task: str = Query(..., description="Task description for agent recommendation"),
    repo: str = Query("", description="Optional repo path for tech stack detection"),
    top_n: int = Query(5, ge=1, le=20, description="Max number of recommendations"),
):
    """Return ranked agent recommendations for a task, optionally boosted by repo context."""
    from superpowers.agent_router import select_agents, detect_tech_stack

    registry = _get_registry()
    repo_path = repo if repo else None

    selections = select_agents(
        task_description=task,
        repo_path=repo_path,
        registry=registry,
        top_n=top_n,
    )

    recommendations = [
        AgentRecommendation(
            name=s.agent.name,
            description=s.agent.description,
            score=s.score,
            reasons=s.reasons,
            tags=s.agent.tags,
        )
        for s in selections
    ]

    tech_stack_out = None
    if repo_path:
        try:
            ts = detect_tech_stack(repo_path)
            tech_stack_out = TechStackOut(
                languages=ts.languages,
                frameworks=ts.frameworks,
                tools=ts.tools,
                primary_language=ts.primary_language,
            )
        except (OSError, PermissionError):
            pass

    return RecommendResponse(
        recommendations=recommendations,
        tech_stack=tech_stack_out,
        task=task,
        repo=repo,
    )


@router.get("/{name}", response_model=AgentDetail)
def get_agent(name: str):
    """Get full details for a specific agent."""
    registry = _get_registry()
    try:
        agent = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent not found: {name}")

    return AgentDetail(
        name=agent.name,
        description=agent.description,
        tags=agent.tags,
        skills=agent.skills,
        triggers=agent.triggers,
        path=str(agent.path),
    )
