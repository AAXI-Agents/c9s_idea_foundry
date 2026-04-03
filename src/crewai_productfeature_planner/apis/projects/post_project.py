"""POST /projects — Create a new project.

Request:  Body ``ProjectCreate`` (name, description, integration keys).
Response: 201 Created with ProjectItem.
Database: Inserts into ``projectConfig`` collection via ``create_project()``.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from crewai_productfeature_planner.apis.projects.models import (
    ProjectCreate,
    ProjectItem,
    project_fields,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=ProjectItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(body: ProjectCreate, user: dict = Depends(require_sso_user)) -> ProjectItem:
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        create_project as _create_project,
        get_project as _get_project,
    )

    logger.info("[Projects] CREATE name=%s user_id=%s", body.name, user.get("user_id"))
    project_id = _create_project(
        name=body.name,
        description=body.description,
        confluence_space_key=body.confluence_space_key,
        jira_project_key=body.jira_project_key,
        confluence_parent_id=body.confluence_parent_id,
        reference_urls=body.reference_urls,
    )
    if not project_id:
        logger.error("[Projects] CREATE failed for name=%s", body.name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        )

    logger.info("[Projects] Created project_id=%s", project_id)
    doc = _get_project(project_id)
    return ProjectItem(**project_fields(doc or {"project_id": project_id, "name": body.name}))
