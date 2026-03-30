"""Projects CRUD router — list (paginated), get, create, update, delete.

Pagination
----------
``GET /projects`` accepts ``page`` (1-based) and ``page_size`` (10, 25,
or 50) query parameters.  Responses include ``total``, ``page``,
``page_size``, ``total_pages``, and the ``items`` list.
"""

from __future__ import annotations

from enum import IntEnum
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
    dependencies=[Depends(require_sso_user)],
)


# ── Pagination helpers ────────────────────────────────────────


class PageSize(IntEnum):
    TEN = 10
    TWENTY_FIVE = 25
    FIFTY = 50


_VALID_PAGE_SIZES = {int(v) for v in PageSize}


# ── Pydantic schemas ─────────────────────────────────────────


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    confluence_space_key: str = Field(default="", max_length=50)
    jira_project_key: str = Field(default="", max_length=50)
    confluence_parent_id: str = Field(default="", max_length=50)
    reference_urls: list[str] = Field(default_factory=list, max_length=20)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    confluence_space_key: str | None = None
    jira_project_key: str | None = None
    confluence_parent_id: str | None = None


class ProjectItem(BaseModel):
    project_id: str
    name: str
    confluence_space_key: str = ""
    jira_project_key: str = ""
    confluence_parent_id: str = ""
    reference_urls: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class ProjectListResponse(BaseModel):
    items: list[ProjectItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Routes ────────────────────────────────────────────────────


@router.get(
    "",
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
    if page_size not in _VALID_PAGE_SIZES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size must be one of {sorted(_VALID_PAGE_SIZES)}",
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
        items=[ProjectItem(**_project_fields(d)) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


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
    return ProjectItem(**_project_fields(doc))


@router.post(
    "",
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
    return ProjectItem(**_project_fields(doc or {"project_id": project_id, "name": body.name}))


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
    existing = _get_project(project_id)
    if not existing:
        logger.warning("[Projects] Not found for update project_id=%s", project_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    updates = body.model_dump(exclude_none=True)
    if updates:
        _update_project(project_id, **updates)
        logger.info("[Projects] Updated project_id=%s fields=%s", project_id, list(updates.keys()))

    doc = _get_project(project_id)
    return ProjectItem(**_project_fields(doc or existing))


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
    existing = _get_project(project_id)
    if not existing:
        logger.warning("[Projects] Not found for delete project_id=%s", project_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    _delete_project(project_id)
    logger.info("[Projects] Deleted project_id=%s", project_id)


# ── Helpers ───────────────────────────────────────────────────


def _project_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract ProjectItem-compatible fields from a MongoDB document."""
    return {
        "project_id": doc.get("project_id", ""),
        "name": doc.get("name", ""),
        "confluence_space_key": doc.get("confluence_space_key", ""),
        "jira_project_key": doc.get("jira_project_key", ""),
        "confluence_parent_id": doc.get("confluence_parent_id", ""),
        "reference_urls": doc.get("reference_urls", []),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }
