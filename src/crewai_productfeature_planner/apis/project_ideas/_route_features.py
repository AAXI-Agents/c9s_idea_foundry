"""Feature management route for project ideas.

PATCH /projects/{project_id}/ideas/{idea_id}/features — Update features
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from crewai_productfeature_planner.apis.admin_deps import resolve_tenant_context
from crewai_productfeature_planner.apis.project_ideas.models import (
    ProjectIdeaItem,
    UpdateFeaturesRequest,
    idea_response_fields,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.ideas.repository import (
    get_idea,
    update_features,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.patch(
    "/{idea_id}/features",
    response_model=ProjectIdeaItem,
    summary="Update idea features",
)
async def update_idea_features(
    project_id: str,
    idea_id: str,
    body: UpdateFeaturesRequest,
    user: dict = Depends(require_sso_user),
) -> ProjectIdeaItem:
    tenant = resolve_tenant_context(user)

    existing = get_idea(idea_id=idea_id, tenant=tenant)
    if not existing or existing.get("project_id") != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {idea_id}",
        )

    logger.info(
        "[ProjectIdeas] PATCH features project=%s idea=%s count=%d",
        project_id,
        idea_id,
        len(body.features),
    )

    features_dicts = [f.model_dump() for f in body.features]
    success = update_features(
        idea_id=idea_id,
        features=features_dicts,
        tenant=tenant,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update features",
        )

    doc = get_idea(idea_id=idea_id, tenant=tenant)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated idea",
        )
    return ProjectIdeaItem(**idea_response_fields(doc))
