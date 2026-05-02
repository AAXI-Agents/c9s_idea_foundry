"""GET /company/org-chart — Agent organizational hierarchy."""

from __future__ import annotations

from fastapi import APIRouter

from crewai_productfeature_planner.apis.company.models import OrgChartNode, OrgChartResponse
from crewai_productfeature_planner.mongodb.agent_registry import get_org_chart
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/org-chart",
    response_model=OrgChartResponse,
    summary="Get agent org chart",
)
async def get_org_chart_endpoint() -> OrgChartResponse:
    """Return all agents structured as an org chart with departments."""
    raw = get_org_chart()
    agents = [OrgChartNode(**a) for a in raw]
    departments = sorted({a.department for a in agents})
    return OrgChartResponse(agents=agents, departments=departments)
