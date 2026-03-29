"""Ideas CRUD router — list (paginated), get, archive, update status.

Pagination
----------
``GET /ideas`` accepts ``page`` (1-based), ``page_size`` (10, 25, 50),
optional ``project_id`` and ``status`` query parameters.
"""

from __future__ import annotations

from enum import IntEnum
from math import ceil
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/ideas",
    tags=["Ideas"],
    dependencies=[Depends(require_sso_user)],
)

# ── Pagination helpers ────────────────────────────────────────

_VALID_PAGE_SIZES = {10, 25, 50}

VALID_STATUSES = {"inprogress", "completed", "paused", "failed", "archived"}


# ── Pydantic schemas ─────────────────────────────────────────


class IdeaItem(BaseModel):
    run_id: str
    idea: str = ""
    finalized_idea: str = ""
    status: str = ""
    project_id: str = ""
    created_at: str = ""
    completed_at: str = ""
    sections_done: int = 0
    total_sections: int = 0
    iteration: int = 0
    confluence_url: str = ""
    jira_phase: str = ""
    figma_design_url: str = ""
    figma_design_status: str = ""


class IdeaListResponse(BaseModel):
    items: list[IdeaItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class IdeaStatusUpdate(BaseModel):
    status: Literal["archived", "paused"] = Field(
        description="New status. Only 'archived' and 'paused' transitions are supported."
    )


# ── Routes ────────────────────────────────────────────────────


@router.get(
    "",
    response_model=IdeaListResponse,
    summary="List ideas (paginated)",
)
async def list_ideas(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=10, description="Items per page: 10, 25, or 50"),
    project_id: str | None = Query(default=None, description="Filter by project ID"),
    idea_status: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (inprogress, completed, paused, failed, archived)",
    ),
    user: dict = Depends(require_sso_user),
) -> IdeaListResponse:
    """Return a paginated list of ideas, newest first."""
    logger.debug("[Ideas] list_ideas called by user_id=%s", user.get("user_id"))
    if page_size not in _VALID_PAGE_SIZES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size must be one of {sorted(_VALID_PAGE_SIZES)}",
        )

    if idea_status and idea_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {sorted(VALID_STATUSES)}",
        )

    from crewai_productfeature_planner.mongodb.working_ideas._common import (
        WORKING_COLLECTION,
        get_db,
    )

    db = get_db()
    coll = db[WORKING_COLLECTION]

    query: dict[str, Any] = {}
    if project_id:
        query["project_id"] = project_id
    if idea_status:
        query["status"] = idea_status

    total = coll.count_documents(query)
    total_pages = max(1, ceil(total / page_size))
    skip = (page - 1) * page_size

    docs = list(
        coll.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    return IdeaListResponse(
        items=[IdeaItem(**_idea_fields(d)) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{run_id}",
    response_model=IdeaItem,
    summary="Get a single idea by run_id",
)
async def get_idea(run_id: str, user: dict = Depends(require_sso_user)) -> IdeaItem:
    from crewai_productfeature_planner.mongodb.working_ideas._queries import (
        find_run_any_status,
    )

    logger.info("[Ideas] GET run_id=%s user_id=%s", run_id, user.get("user_id"))
    doc = find_run_any_status(run_id)
    if not doc:
        logger.warning("[Ideas] Not found run_id=%s", run_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {run_id}",
        )
    return IdeaItem(**_idea_fields(doc))


@router.patch(
    "/{run_id}/status",
    response_model=IdeaItem,
    summary="Update idea status (archive / pause)",
)
async def update_idea_status(run_id: str, body: IdeaStatusUpdate, user: dict = Depends(require_sso_user)) -> IdeaItem:
    from crewai_productfeature_planner.mongodb.working_ideas._queries import (
        find_run_any_status,
    )
    from crewai_productfeature_planner.mongodb.working_ideas._status import (
        mark_archived,
        mark_paused,
    )

    doc = find_run_any_status(run_id)
    if not doc:
        logger.warning("[Ideas] Not found for status update run_id=%s", run_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {run_id}",
        )

    logger.info("[Ideas] STATUS UPDATE run_id=%s new_status=%s user_id=%s", run_id, body.status, user.get("user_id"))
    if body.status == "archived":
        # Signal cancellation to stop any running flow for this run
        from crewai_productfeature_planner.apis.shared import request_cancel
        request_cancel(run_id)
        # Unblock any pending approval gates so the flow thread wakes up
        try:
            from crewai_productfeature_planner.apis.slack._flow_handlers import (
                _unblock_gates_for_cancel,
            )
            _unblock_gates_for_cancel(run_id)
        except Exception:  # noqa: BLE001
            logger.debug("Could not unblock gates for %s", run_id, exc_info=True)
        mark_archived(run_id)
        # Also archive the crew job
        try:
            from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
                update_job_status,
            )
            update_job_status(run_id, "archived")
        except Exception:  # noqa: BLE001
            logger.debug("Could not archive crewJob for %s", run_id, exc_info=True)
    elif body.status == "paused":
        mark_paused(run_id)

    updated = find_run_any_status(run_id)
    return IdeaItem(**_idea_fields(updated or doc))


# ── Helpers ───────────────────────────────────────────────────

_TOTAL_SECTIONS = 12


def _idea_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract IdeaItem-compatible fields from a MongoDB document."""
    status_val = doc.get("status", "unknown")

    section_obj = doc.get("section") or {}
    sections = [k for k, v in section_obj.items() if isinstance(v, list) and v]
    raw_exec = doc.get("executive_summary", [])
    has_exec = isinstance(raw_exec, list) and len(raw_exec) > 0
    exec_counted = "executive_summary" in sections
    sections_done = len(sections) + (1 if has_exec and not exec_counted else 0)
    if status_val == "completed":
        sections_done = _TOTAL_SECTIONS

    max_iter = 0
    for entries in section_obj.values():
        if isinstance(entries, list):
            for entry in entries:
                it = entry.get("iteration", 0) if isinstance(entry, dict) else 0
                if it > max_iter:
                    max_iter = it
    exec_iter_count = len(raw_exec) if isinstance(raw_exec, list) else 0
    effective_iter = max(max_iter, exec_iter_count)

    return {
        "run_id": doc.get("run_id", ""),
        "idea": doc.get("idea", ""),
        "finalized_idea": doc.get("finalized_idea", ""),
        "status": status_val,
        "project_id": doc.get("project_id", ""),
        "created_at": doc.get("created_at", ""),
        "completed_at": doc.get("completed_at") or "",
        "sections_done": sections_done,
        "total_sections": _TOTAL_SECTIONS,
        "iteration": effective_iter,
        "confluence_url": doc.get("confluence_url", ""),
        "jira_phase": doc.get("jira_phase", ""),
        "figma_design_url": doc.get("figma_design_url", ""),
        "figma_design_status": doc.get("figma_design_status", ""),
    }
