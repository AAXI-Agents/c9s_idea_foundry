"""DELETE /projects/{project_id} — Delete a project.

Request:  Path param ``project_id``.
Response: 204 No Content.
Database: Deletes from ``projectConfig`` collection via ``delete_project()``.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
async def delete_project(project_id: str, user: dict = Depends(require_sso_user)) -> None:
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        delete_project as _delete_project,
        get_project as _get_project,
    )

    logger.info("[Projects] DELETE project_id=%s user_id=%s", project_id, user.get("user_id"))
    tenant = TenantContext.from_user(user)
    existing = _get_project(project_id, tenant=tenant)
    if not existing:
        logger.warning("[Projects] Not found for delete project_id=%s", project_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    _delete_project(project_id, tenant=tenant)
    logger.info("[Projects] Deleted project_id=%s", project_id)
