"""GET /company/budget — Aggregated budget/cost summary."""

from __future__ import annotations

from fastapi import APIRouter

from crewai_productfeature_planner.apis.company.models import BudgetSummaryResponse
from crewai_productfeature_planner.mongodb.agent_registry import get_budget_summary
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/budget",
    response_model=BudgetSummaryResponse,
    summary="Get company budget summary",
)
async def get_budget_endpoint() -> BudgetSummaryResponse:
    """Return aggregated budget and cost data by department."""
    data = get_budget_summary()
    return BudgetSummaryResponse(**data)
