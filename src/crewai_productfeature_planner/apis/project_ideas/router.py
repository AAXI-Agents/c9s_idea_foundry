"""Project Ideas API router — assembles all route modules.

All routes are nested under ``/projects/{project_id}/ideas``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from crewai_productfeature_planner.apis.project_ideas._route_crud import (
    router as crud_router,
)
from crewai_productfeature_planner.apis.project_ideas._route_features import (
    router as features_router,
)
from crewai_productfeature_planner.apis.project_ideas._route_flow import (
    router as flow_router,
)
from crewai_productfeature_planner.apis.project_ideas._route_deliverables import (
    router as deliverables_router,
)
from crewai_productfeature_planner.apis.project_ideas._route_websocket import (
    ws_router as idea_ws_router,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user

router = APIRouter(
    prefix="/projects/{project_id}/ideas",
    tags=["Project Ideas"],
    dependencies=[Depends(require_sso_user)],
)
router.include_router(crud_router)
router.include_router(features_router)
router.include_router(flow_router)
router.include_router(deliverables_router)

# WebSocket router exported separately (no SSO dependency — uses token query param)
ws_only_router = idea_ws_router
