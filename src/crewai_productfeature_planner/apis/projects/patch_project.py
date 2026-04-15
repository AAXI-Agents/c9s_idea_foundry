"""PATCH /projects/{project_id} — Update a project.

Request:  Path param ``project_id``, body ``ProjectUpdate``.
Response: Updated ProjectItem.
Database: Updates ``projectConfig`` collection via ``update_project()``.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from crewai_productfeature_planner.apis.projects.models import (
    ProjectItem,
    ProjectUpdate,
    project_fields,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.patch(
    "/{project_id}",
    response_model=ProjectItem,
    summary="Update a project",
)
async def update_project(project_id: str, body: ProjectUpdate, user: dict = Depends(require_sso_user)) -> ProjectItem:
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        get_project as _get_project,
        update_project as _update_project,
    )

    logger.info("[Projects] UPDATE project_id=%s user_id=%s", project_id, user.get("user_id"))
    tenant = TenantContext.from_user(user)
    existing = _get_project(project_id, tenant=tenant)
    if not existing:
        logger.warning("[Projects] Not found for update project_id=%s", project_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    updates = body.model_dump(exclude_none=True)
    if updates:
        _update_project(project_id, tenant=tenant, **updates)
        logger.info("[Projects] Updated project_id=%s fields=%s", project_id, list(updates.keys()))

    doc = _get_project(project_id, tenant=tenant)
    return ProjectItem(**project_fields(doc or existing))
