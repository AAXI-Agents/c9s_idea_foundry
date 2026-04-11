"""GET /projects — List projects with pagination.

Request:  Query params: page, page_size.
Response: ProjectListResponse with paginated items.
Database: Queries ``projectConfig`` collection via Motor (async) sorted
          by ``created_at`` desc.  Uses ``estimated_document_count()``
          for unfiltered totals and a short-lived response cache
          (5 s TTL) to eliminate redundant Atlas round-trips.
"""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis._response_cache import response_cache
from crewai_productfeature_planner.apis.projects.models import (
    ProjectItem,
    ProjectListResponse,
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
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page (1-100)"),
    user: dict = Depends(require_sso_user),
) -> ProjectListResponse:
    """Return a paginated list of projects, newest first."""
    logger.debug("[Projects] list_projects called by user_id=%s", user.get("user_id"))
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_size must be between 1 and 100",
        )

    # ── Check response cache ──────────────────────────────────
    cache_params = dict(page=page, page_size=page_size)
    cached = response_cache.get("projects", **cache_params)
    if cached is not None:
        logger.debug("[Projects] cache hit for page=%d size=%d", page, page_size)
        return cached

    # ── Motor async query ─────────────────────────────────────
    from crewai_productfeature_planner.mongodb.async_client import get_async_db
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        PROJECT_CONFIG_COLLECTION,
    )

    db = get_async_db()
    coll = db[PROJECT_CONFIG_COLLECTION]

    skip = (page - 1) * page_size
    total = await coll.estimated_document_count()
    cursor = coll.find({}, {"_id": 0}).sort(
        "created_at", -1
    ).skip(skip).limit(page_size)
    docs = await cursor.to_list(length=page_size)

    total_pages = max(1, ceil(total / page_size))

    result = ProjectListResponse(
        items=[ProjectItem(**project_fields(d)) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    response_cache.put("projects", result, **cache_params)
    return result
