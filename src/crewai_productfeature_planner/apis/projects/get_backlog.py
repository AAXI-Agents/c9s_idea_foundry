"""GET /projects/{project_id}/backlog — read-only backlog aggregator.

Composes a kanban-style backlog from multiple MongoDB collections:

- ``workingIdeas``  → ``kind=idea``  (overall run items)
- PRD sections from ``workingIdeas.sections`` → ``kind=prd_section``
- Publishing state  → ``kind=publish_confluence``, ``kind=publish_jira``

Each item carries a ``blocked_by`` list computed server-side so the
frontend can render dependency arrows without extra queries.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext, tenant_filter
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Response models ─────────────────────────────────────────────

from pydantic import BaseModel, Field


class BacklogItem(BaseModel):
    """A single backlog card."""

    id: str = Field(..., description="Synthetic ID (e.g. 'idea:{run_id}').")
    kind: str = Field(
        ...,
        description="Item type: idea, prd_section, publish_confluence, publish_jira.",
    )
    run_id: str = Field(..., description="Associated flow run ID.")
    title: str = Field(..., description="Human-readable title.")
    status: str = Field(default="", description="Item-level status.")
    section_key: str | None = Field(
        default=None, description="Section key for prd_section items."
    )
    blocked_by: list[str] = Field(
        default_factory=list,
        description="IDs of items that block this item.",
    )
    created_at: str = Field(default="", description="ISO-8601 timestamp.")
    updated_at: str = Field(default="", description="ISO-8601 timestamp.")


class BacklogResponse(BaseModel):
    """Response for GET /projects/{project_id}/backlog."""

    project_id: str = Field(..., description="Project ID.")
    count: int = Field(default=0, description="Total backlog items.")
    items: list[BacklogItem] = Field(
        default_factory=list, description="Backlog items."
    )


# ── Helpers ─────────────────────────────────────────────────────

def _iso(val: Any) -> str:
    if val is None:
        return ""
    return val.isoformat() if hasattr(val, "isoformat") else str(val)


def _build_backlog(
    project_id: str,
    *,
    tenant: TenantContext | None = None,
    limit: int = 200,
) -> list[BacklogItem]:
    """Build backlog items from MongoDB collections."""
    db = get_db()
    items: list[BacklogItem] = []

    query: dict[str, Any] = {
        **tenant_filter(tenant),
        "project_id": project_id,
    }

    ideas = list(
        db["workingIdeas"]
        .find(query, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )

    for idea in ideas:
        run_id = idea.get("run_id", "")
        idea_id = f"idea:{run_id}"
        idea_status = idea.get("status", "")
        idea_title = (idea.get("idea", "") or "")[:120] or f"Run {run_id[:8]}"

        # Top-level idea item
        items.append(BacklogItem(
            id=idea_id,
            kind="idea",
            run_id=run_id,
            title=idea_title,
            status=idea_status,
            created_at=_iso(idea.get("created_at")),
            updated_at=_iso(idea.get("updated_at")),
        ))

        # Section items
        sections = idea.get("sections", {})
        section_ids: list[str] = []
        if isinstance(sections, dict):
            prev_section_id: str | None = None
            for key, sec in sections.items():
                if not isinstance(sec, dict):
                    continue
                sec_id = f"section:{run_id}:{key}"
                section_ids.append(sec_id)

                # blocked_by: the idea + previous section (linear dependency)
                blocked_by = [idea_id]
                if prev_section_id:
                    blocked_by.append(prev_section_id)

                sec_status = "approved" if sec.get("is_approved") else (
                    "draft" if sec.get("content") else "pending"
                )
                items.append(BacklogItem(
                    id=sec_id,
                    kind="prd_section",
                    run_id=run_id,
                    title=sec.get("title", key),
                    status=sec_status,
                    section_key=key,
                    blocked_by=blocked_by,
                    created_at=_iso(sec.get("created_date") or idea.get("created_at")),
                    updated_at=_iso(sec.get("updated_date")),
                ))
                prev_section_id = sec_id

        # Publishing items — blocked by all sections being approved
        if idea_status == "completed":
            pub_blocked_by = section_ids.copy() if section_ids else [idea_id]

            if not idea.get("confluence_url"):
                items.append(BacklogItem(
                    id=f"pub:confluence:{run_id}",
                    kind="publish_confluence",
                    run_id=run_id,
                    title="Publish to Confluence",
                    status="pending",
                    blocked_by=pub_blocked_by,
                    created_at=_iso(idea.get("completed_at") or idea.get("created_at")),
                ))

            if not idea.get("jira_output") and not idea.get("jira_skeleton"):
                items.append(BacklogItem(
                    id=f"pub:jira:{run_id}",
                    kind="publish_jira",
                    run_id=run_id,
                    title="Create Jira tickets",
                    status="pending",
                    blocked_by=pub_blocked_by,
                    created_at=_iso(idea.get("completed_at") or idea.get("created_at")),
                ))

    return items[:limit]


# ── Route ───────────────────────────────────────────────────────

@router.get(
    "/{project_id}/backlog",
    response_model=BacklogResponse,
    summary="Get project backlog",
    description=(
        "Returns a kanban-style backlog for a project, composed from "
        "working ideas, PRD sections, and publishing state. Each item "
        "includes a ``blocked_by`` list for dependency rendering."
    ),
    responses={
        200: {"description": "Backlog returned successfully."},
        404: {"description": "Project not found."},
    },
)
async def get_project_backlog(
    project_id: str,
    limit: int = Query(default=200, ge=1, le=1000, description="Max items."),
    user: dict = Depends(require_sso_user),
) -> BacklogResponse:
    """Return backlog items for a single project."""
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        get_project as _get_project,
    )

    tenant = TenantContext.from_user(user)
    logger.info(
        "[Projects] GET backlog project_id=%s user_id=%s",
        project_id, user.get("user_id"),
    )

    if not _get_project(project_id, tenant=tenant):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    try:
        items = _build_backlog(project_id, tenant=tenant, limit=limit)
    except Exception as exc:
        logger.error(
            "[Projects] Failed to build backlog project_id=%s: %s",
            project_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to build backlog",
        ) from exc

    return BacklogResponse(
        project_id=project_id,
        count=len(items),
        items=items,
    )
