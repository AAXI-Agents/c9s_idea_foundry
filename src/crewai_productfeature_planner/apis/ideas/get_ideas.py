"""GET /ideas — List ideas with pagination, project and status filters.

Request:  Query params: page, page_size, project_id, status.
Response: IdeaListResponse with paginated items.
Database: Queries ``workingIdeas`` collection via Motor (async) with
          optional filters, sorted by ``created_at`` descending.  Uses a
          lean projection to avoid transferring heavy PRD content and a
          short-lived response cache (5 s TTL) to eliminate redundant
          Atlas round-trips from dashboard polling.
"""

from __future__ import annotations

from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis._response_cache import response_cache
from crewai_productfeature_planner.apis.admin_deps import resolve_tenant_context
from crewai_productfeature_planner.apis.ideas.models import (
    IDEA_LIST_PROJECTION,
    IdeaItem,
    IdeaListResponse,
    VALID_STATUSES,
    idea_fields,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import tenant_filter
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/",
    response_model=IdeaListResponse,
    summary="List ideas (paginated)",
)
async def list_ideas(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page (1-100)"),
    project_id: str | None = Query(default=None, description="Filter by project ID"),
    idea_status: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (inprogress, completed, paused, failed, archived)",
    ),
    include_archived: bool = Query(
        default=False,
        description=(
            "Include archived ideas in the result. Defaults to False so that "
            "user-archived ('deleted') ideas do not reappear in the dashboard."
        ),
    ),
    organization_id: str | None = Query(
        default=None,
        description="Filter by organization (enterprise admins only)",
    ),
    user: dict = Depends(require_sso_user),
) -> IdeaListResponse:
    """Return a paginated list of ideas, newest first."""
    logger.debug("[Ideas] list_ideas called by user_id=%s", user.get("user_id"))
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_size must be between 1 and 100",
        )

    if idea_status and idea_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {sorted(VALID_STATUSES)}",
        )

    # ── Check response cache ──────────────────────────────────
    cache_params = dict(page=page, page_size=page_size,
                        project_id=project_id, status=idea_status,
                        include_archived=include_archived,
                        organization_id=organization_id)
    cached = response_cache.get("ideas", **cache_params)
    if cached is not None:
        logger.debug("[Ideas] cache hit for page=%d size=%d", page, page_size)
        return cached

    # ── Motor async query ─────────────────────────────────────
    from crewai_productfeature_planner.mongodb.async_client import get_async_db
    from crewai_productfeature_planner.mongodb.working_ideas._common import (
        WORKING_COLLECTION,
    )

    db = get_async_db()
    coll = db[WORKING_COLLECTION]

    tenant = resolve_tenant_context(user, organization_id)
    t_filter = tenant_filter(tenant)

    query: dict[str, Any] = {**t_filter}
    if project_id:
        query["project_id"] = project_id
    if idea_status:
        # Explicit status filter wins — caller can opt in to deleted/archived/failed/completed.
        query["status"] = idea_status
    elif not include_archived:
        # Default behaviour: hide terminal-state ideas from the dashboard.
        # 'deleted' is the user-facing soft-delete (DELETE /ideas/{id}) and
        # must NEVER appear in the default dashboard listing. 'archived' is
        # the internal restart-PRD state. 'failed' is terminated state the
        # user already saw. 'completed' means a PRD has been generated —
        # these ideas no longer need attention in the active list.
        query["status"] = {"$nin": ["deleted", "archived", "failed", "completed"]}

    skip = (page - 1) * page_size
    total = await coll.count_documents(query)
    cursor = coll.find(query, IDEA_LIST_PROJECTION).sort(
        "created_at", -1
    ).skip(skip).limit(page_size)
    docs = await cursor.to_list(length=page_size)

    total_pages = max(1, ceil(total / page_size))

    result = IdeaListResponse(
        items=[IdeaItem(**idea_fields(d)) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    response_cache.put("ideas", result, **cache_params)
    return result
