"""GET /projects — List projects with pagination.

Request:  Query params: page, page_size.
Response: ProjectListResponse with paginated items.
Database: Queries ``projectConfig`` collection sorted by ``created_at`` desc.
"""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis.projects.models import (
    ProjectItem,
    ProjectListResponse,
    VALID_PAGE_SIZES,
    project_fields,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/",
    response_model=ProjectListResponse,
    summary="List projects (paginated)",
)
async def list_projects(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=10, description="Items per page: 10, 25, or 50"),
    user: dict = Depends(require_sso_user),
) -> ProjectListResponse:
    """Return a paginated list of projects, newest first."""
    logger.debug("[Projects] list_projects called by user_id=%s", user.get("user_id"))
    if page_size not in VALID_PAGE_SIZES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size must be one of {sorted(VALID_PAGE_SIZES)}",
        )

    from crewai_productfeature_planner.mongodb.project_config.repository import (
        PROJECT_CONFIG_COLLECTION,
    )
    from crewai_productfeature_planner.mongodb.client import get_db

    db = get_db()
    coll = db[PROJECT_CONFIG_COLLECTION]

    total = coll.count_documents({})
    total_pages = max(1, ceil(total / page_size))
    skip = (page - 1) * page_size

    docs = list(
        coll.find({}, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    return ProjectListResponse(
        items=[ProjectItem(**project_fields(d)) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
