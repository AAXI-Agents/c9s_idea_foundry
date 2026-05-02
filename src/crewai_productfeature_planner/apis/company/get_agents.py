"""GET /company/agents — List all agents with optional filtering."""

from __future__ import annotations

from fastapi import APIRouter, Query

from crewai_productfeature_planner.apis.company.models import AgentDetail, AgentListResponse
from crewai_productfeature_planner.mongodb.agent_registry import list_agents
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/agents",
    response_model=AgentListResponse,
    summary="List all agents",
)
async def list_agents_endpoint(
    department: str | None = Query(default=None, description="Filter by department"),
    status: str | None = Query(default=None, description="Filter by status"),
) -> AgentListResponse:
    """Return all registered agents, optionally filtered."""
    raw = list_agents(department=department, status=status)
    agents = [AgentDetail(**a) for a in raw]
    return AgentListResponse(agents=agents, total=len(agents))
