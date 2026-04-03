"""Ideas API router — assembles all idea route modules.

Route modules:
    get_ideas.py          — GET /ideas (paginated list)
    get_idea.py           — GET /ideas/{run_id}
    patch_idea_status.py  — PATCH /ideas/{run_id}/status

Shared:
    models.py             — IdeaItem, IdeaListResponse, IdeaStatusUpdate, idea_fields()
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from crewai_productfeature_planner.apis.ideas.get_ideas import router as get_ideas_router
from crewai_productfeature_planner.apis.ideas.get_idea import router as get_idea_router
from crewai_productfeature_planner.apis.ideas.patch_idea_status import router as patch_status_router
from crewai_productfeature_planner.apis.sso_auth import require_sso_user

router = APIRouter(
    prefix="/ideas",
    tags=["Ideas"],
    dependencies=[Depends(require_sso_user)],
)
router.include_router(get_ideas_router)
router.include_router(get_idea_router)
router.include_router(patch_status_router)

# Re-export models for backward compatibility
from crewai_productfeature_planner.apis.ideas.models import (  # noqa: E402, F401
    IdeaItem,
    IdeaListResponse,
    IdeaStatusUpdate,
    VALID_STATUSES,
)
