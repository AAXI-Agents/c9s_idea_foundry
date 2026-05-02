"""GET /company/agents/{agent_id} — Get a single agent's detail."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from crewai_productfeature_planner.apis.company.models import AgentDetail
from crewai_productfeature_planner.mongodb.agent_registry import get_agent
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/agents/{agent_id}",
    response_model=AgentDetail,
    summary="Get agent detail",
)
async def get_agent_endpoint(agent_id: str) -> AgentDetail:
    """Return full details for a specific agent."""
    raw = get_agent(agent_id)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )
    return AgentDetail(**raw)
