"""GET /projects/{project_id} — Get a single project.

Request:  Path param ``project_id``.
Response: ProjectItem.
Database: Queries ``projectConfig`` collection via ``get_project()``.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from crewai_productfeature_planner.apis.projects.models import ProjectItem, project_fields
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/{project_id}",
    response_model=ProjectItem,
    summary="Get a project by ID",
)
async def get_project(project_id: str, user: dict = Depends(require_sso_user)) -> ProjectItem:
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        get_project as _get_project,
    )

    logger.info("[Projects] GET project_id=%s user_id=%s", project_id, user.get("user_id"))
    doc = _get_project(project_id)
    if not doc:
        logger.warning("[Projects] Not found project_id=%s", project_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )
    return ProjectItem(**project_fields(doc))
