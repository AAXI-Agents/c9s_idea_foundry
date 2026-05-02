"""PATCH /company/agents/{agent_id}/budget — Update agent budget config."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from crewai_productfeature_planner.apis.company.models import AgentDetail, BudgetUpdateRequest
from crewai_productfeature_planner.mongodb.agent_registry import get_agent, update_budget
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.patch(
    "/agents/{agent_id}/budget",
    response_model=AgentDetail,
    summary="Update agent budget",
)
async def update_agent_budget(agent_id: str, body: BudgetUpdateRequest) -> AgentDetail:
    """Update budget configuration for a specific agent."""
    existing = get_agent(agent_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    update_budget(
        agent_id,
        monthly_token_limit=body.monthly_token_limit,
        monthly_cost_limit_usd=body.monthly_cost_limit_usd,
        warning_threshold_pct=body.warning_threshold_pct,
        hard_stop=body.hard_stop,
    )

    updated = get_agent(agent_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated agent",
        )
    return AgentDetail(**updated)
