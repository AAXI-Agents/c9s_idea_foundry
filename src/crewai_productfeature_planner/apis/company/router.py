"""Company Dashboard API router — assembles all company route modules.

Route modules:
    get_org_chart.py        — GET /company/org-chart
    get_agents.py           — GET /company/agents
    get_agent.py            — GET /company/agents/{agent_id}
    patch_agent_budget.py   — PATCH /company/agents/{agent_id}/budget
    get_budget.py           — GET /company/budget
    get_activity.py         — GET /company/activity

Shared:
    models.py               — Response/request models
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from crewai_productfeature_planner.apis.company.get_activity import router as get_activity_router
from crewai_productfeature_planner.apis.company.get_agent import router as get_agent_router
from crewai_productfeature_planner.apis.company.get_agents import router as get_agents_router
from crewai_productfeature_planner.apis.company.get_budget import router as get_budget_router
from crewai_productfeature_planner.apis.company.get_org_chart import router as get_org_chart_router
from crewai_productfeature_planner.apis.company.patch_agent_budget import router as patch_budget_router
from crewai_productfeature_planner.apis.sso_auth import require_sso_user

router = APIRouter(
    prefix="/company",
    tags=["Company"],
    dependencies=[Depends(require_sso_user)],
)
router.include_router(get_org_chart_router)
router.include_router(get_agents_router)
router.include_router(get_agent_router)
router.include_router(patch_budget_router)
router.include_router(get_budget_router)
router.include_router(get_activity_router)
