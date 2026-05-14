"""CRUD routes for project ideas.

POST   /projects/{project_id}/ideas          — Create idea
GET    /projects/{project_id}/ideas          — List ideas
GET    /projects/{project_id}/ideas/{idea_id} — Get idea detail
PATCH  /projects/{project_id}/ideas/{idea_id} — Update idea metadata
PATCH  /projects/{project_id}/ideas/{idea_id}/status — Update idea status
DELETE /projects/{project_id}/ideas/{idea_id} — Delete idea (draft only)
"""

from __future__ import annotations

from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis.admin_deps import resolve_tenant_context
from crewai_productfeature_planner.apis.project_ideas.models import (
    CreateIdeaRequest,
    ProjectIdeaItem,
    ProjectIdeaListResponse,
    UpdateIdeaRequest,
    UpdateIdeaStatusRequest,
    idea_response_fields,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.ideas.repository import (
    count_ideas,
    create_idea,
    delete_idea,
    get_idea,
    list_ideas,
    update_idea,
    update_idea_status,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _enrich_completed_fields(items: list[dict[str, Any]], tenant) -> None:
    """Enrich completed ideas with PRD data from workingIdeas.

    Uses a single batch query with projection to avoid N+1 round-trips.
    Mutates the idea dicts in place, adding ``completed_at``,
    ``confluence_url``, ``jira_epic_key``, and ``prd_summary`` fields
    sourced from the linked working idea run.
    """
    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_runs_batch,
    )

    # Collect run_ids for all completed ideas
    run_id_map: dict[str, str] = {}  # run_id → (used for reverse lookup)
    doc_by_run: dict[str, list[dict[str, Any]]] = {}  # run_id → list of docs needing enrichment

    for doc in items:
        if doc.get("status") != "completed":
            continue
        run_id = doc.get("active_run_id")
        if not run_id:
            run_ids = doc.get("run_ids") or []
            run_id = run_ids[-1] if run_ids else None
        if not run_id:
            continue
        run_id_map[run_id] = run_id
        doc_by_run.setdefault(run_id, []).append(doc)

    if not run_id_map:
        return

    # Single batch query with minimal projection
    wi_docs = find_runs_batch(
        list(run_id_map.keys()),
        tenant=tenant,
        projection={
            "completed_at": 1,
            "confluence_url": 1,
            "jira_output": 1,
            "finalized_idea": 1,
        },
    )

    # Enrich each completed idea from the batch results
    for run_id, idea_docs in doc_by_run.items():
        wi = wi_docs.get(run_id)
        if not wi:
            continue

        for doc in idea_docs:
            doc["completed_at"] = wi.get("completed_at", "")
            doc["confluence_url"] = wi.get("confluence_url") or None

            # Extract primary Jira epic key from jira_output
            jira_output = wi.get("jira_output") or {}
            epics = jira_output.get("epics") or []
            if epics and isinstance(epics, list) and isinstance(epics[0], dict):
                doc["jira_epic_key"] = epics[0].get("key") or None
            elif isinstance(jira_output, dict) and jira_output.get("epic_key"):
                doc["jira_epic_key"] = jira_output["epic_key"]

            # Extract PRD summary from finalized_idea (first 200 chars)
            finalized = wi.get("finalized_idea") or ""
            if finalized:
                lines = finalized.strip().splitlines()
                summary_lines = [
                    ln for ln in lines if ln.strip() and not ln.strip().startswith("#")
                ]
                summary = " ".join(summary_lines)[:200].strip()
                if len(summary) < len(" ".join(summary_lines)):
                    summary += "…"
                doc["prd_summary"] = summary


@router.post(
    "/",
    response_model=ProjectIdeaItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new idea in this project",
)
async def create_project_idea(
    project_id: str,
    body: CreateIdeaRequest,
    user: dict = Depends(require_sso_user),
) -> ProjectIdeaItem:
    tenant = resolve_tenant_context(user)
    user_id = user.get("user_id", "")

    logger.info(
        "[ProjectIdeas] POST create project=%s user=%s title=%r",
        project_id,
        user_id,
        body.title,
    )

    doc = create_idea(
        project_id=project_id,
        title=body.title,
        description=body.description,
        created_by=user_id,
        ideation_session_id=body.ideation_session_id,
        tenant=tenant,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create idea",
        )
    return ProjectIdeaItem(**idea_response_fields(doc))


@router.get(
    "/",
    response_model=ProjectIdeaListResponse,
    summary="List ideas for this project (paginated)",
)
async def list_project_ideas(
    project_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    idea_status: str | None = Query(default=None, alias="status"),
    user: dict = Depends(require_sso_user),
) -> ProjectIdeaListResponse:
    tenant = resolve_tenant_context(user)

    logger.debug(
        "[ProjectIdeas] GET list project=%s page=%d size=%d status=%s",
        project_id,
        page,
        page_size,
        idea_status,
    )

    total = count_ideas(project_id=project_id, status=idea_status, tenant=tenant)
    items = list_ideas(
        project_id=project_id,
        status=idea_status,
        page=page,
        page_size=page_size,
        tenant=tenant,
    )
    total_pages = max(1, ceil(total / page_size))

    # Enrich completed ideas with PRD deliverable fields
    _enrich_completed_fields(items, tenant=tenant)

    return ProjectIdeaListResponse(
        items=[ProjectIdeaItem(**idea_response_fields(d)) for d in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{idea_id}",
    response_model=ProjectIdeaItem,
    summary="Get a single idea by ID",
)
async def get_project_idea(
    project_id: str,
    idea_id: str,
    user: dict = Depends(require_sso_user),
) -> ProjectIdeaItem:
    tenant = resolve_tenant_context(user)

    logger.info("[ProjectIdeas] GET detail project=%s idea=%s", project_id, idea_id)

    doc = get_idea(idea_id=idea_id, tenant=tenant)
    if not doc or doc.get("project_id") != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {idea_id}",
        )
    _enrich_completed_fields([doc], tenant=tenant)
    return ProjectIdeaItem(**idea_response_fields(doc))


@router.patch(
    "/{idea_id}",
    response_model=ProjectIdeaItem,
    summary="Update idea metadata (title, description)",
)
async def update_project_idea(
    project_id: str,
    idea_id: str,
    body: UpdateIdeaRequest,
    user: dict = Depends(require_sso_user),
) -> ProjectIdeaItem:
    tenant = resolve_tenant_context(user)

    # Verify idea belongs to this project
    existing = get_idea(idea_id=idea_id, tenant=tenant)
    if not existing or existing.get("project_id") != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {idea_id}",
        )

    logger.info(
        "[ProjectIdeas] PATCH metadata project=%s idea=%s",
        project_id,
        idea_id,
    )

    doc = update_idea(
        idea_id=idea_id,
        title=body.title,
        description=body.description,
        tenant=tenant,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update idea",
        )
    return ProjectIdeaItem(**idea_response_fields(doc))


@router.patch(
    "/{idea_id}/status",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update idea status",
)
async def update_project_idea_status(
    project_id: str,
    idea_id: str,
    body: UpdateIdeaStatusRequest,
    user: dict = Depends(require_sso_user),
) -> None:
    tenant = resolve_tenant_context(user)

    existing = get_idea(idea_id=idea_id, tenant=tenant)
    if not existing or existing.get("project_id") != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {idea_id}",
        )

    logger.info(
        "[ProjectIdeas] PATCH status project=%s idea=%s status=%s",
        project_id,
        idea_id,
        body.status,
    )

    success = update_idea_status(
        idea_id=idea_id,
        status=body.status,
        tenant=tenant,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to transition status to {body.status}",
        )


@router.delete(
    "/{idea_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an idea (draft only)",
)
async def delete_project_idea(
    project_id: str,
    idea_id: str,
    user: dict = Depends(require_sso_user),
) -> None:
    tenant = resolve_tenant_context(user)

    existing = get_idea(idea_id=idea_id, tenant=tenant)
    if not existing or existing.get("project_id") != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {idea_id}",
        )

    if existing.get("status") != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ideas in 'draft' status can be deleted",
        )

    logger.info(
        "[ProjectIdeas] DELETE project=%s idea=%s",
        project_id,
        idea_id,
    )

    success = delete_idea(idea_id=idea_id, tenant=tenant)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete idea",
        )
