"""GET /approvals/pending — cross-project pending approvals queue.

Aggregates actionable items across the user's projects:
- PRD sections awaiting approval
- Completed PRDs awaiting Confluence publishing
- Completed PRDs awaiting Jira ticket creation
- Paused runs that can be resumed
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from crewai_productfeature_planner.apis.approvals.models import (
    ApprovalAction,
    ApprovalItem,
    ApprovalListResponse,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext, tenant_filter
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/approvals",
    tags=["Approvals"],
    dependencies=[Depends(require_sso_user)],
)

_ERROR_RESPONSES = {
    500: {"description": "Internal server error."},
}


def _iso(val: Any) -> str:
    """Convert a value to ISO string."""
    if val is None:
        return ""
    return val.isoformat() if hasattr(val, "isoformat") else str(val)


def _build_approval_items(
    *,
    project_id: str | None = None,
    tenant: TenantContext | None = None,
    limit: int = 100,
) -> list[ApprovalItem]:
    """Aggregate pending approval items from MongoDB."""
    db = get_db()
    items: list[ApprovalItem] = []

    # Build base query for working ideas
    base_query: dict[str, Any] = {**tenant_filter(tenant)}
    if project_id:
        base_query["project_id"] = project_id

    # 1. PRD section approvals — active runs with unapproved sections
    #    that have content (ready for review)
    try:
        active_query = {
            **base_query,
            "status": {"$in": ["inprogress", "in_progress"]},
        }
        active_runs = list(
            db["workingIdeas"]
            .find(active_query, {"_id": 0})
            .sort("created_at", -1)
            .limit(limit)
        )

        for idea in active_runs:
            run_id = idea.get("run_id", "")
            proj_id = idea.get("project_id", "")
            sections = idea.get("sections", {})

            if isinstance(sections, dict):
                for key, sec in sections.items():
                    if isinstance(sec, dict) and sec.get("content") and not sec.get("is_approved"):
                        items.append(ApprovalItem(
                            id=f"approve:{run_id}:{key}",
                            kind="prd_section_approval",
                            run_id=run_id,
                            project_id=proj_id,
                            title=f"{sec.get('title', key)} — awaiting approval",
                            section_key=key,
                            waiting_since=_iso(sec.get("updated_date") or idea.get("created_at")),
                            owner_agent_id=None,
                            actions=[
                                ApprovalAction(
                                    label="Approve",
                                    endpoint="POST /flow/prd/approve",
                                    payload_hint={"run_id": run_id, "approve": True},
                                ),
                                ApprovalAction(
                                    label="Send back",
                                    endpoint="POST /flow/prd/approve",
                                    payload_hint={"run_id": run_id, "approve": False, "feedback": "..."},
                                ),
                            ],
                        ))
    except Exception:
        logger.error("[Approvals] Failed to query section approvals", exc_info=True)

    # 2. Paused runs — can be resumed
    try:
        paused_query = {**base_query, "status": "paused"}
        paused_runs = list(
            db["workingIdeas"]
            .find(paused_query, {"_id": 0, "run_id": 1, "idea": 1, "project_id": 1, "created_at": 1})
            .sort("created_at", -1)
            .limit(limit)
        )
        for idea in paused_runs:
            run_id = idea.get("run_id", "")
            items.append(ApprovalItem(
                id=f"resume:{run_id}",
                kind="resume_paused",
                run_id=run_id,
                project_id=idea.get("project_id", ""),
                title=f"Paused run — {(idea.get('idea', '') or '')[:80]}",
                waiting_since=_iso(idea.get("created_at")),
                actions=[
                    ApprovalAction(
                        label="Resume",
                        endpoint="POST /flow/prd/resume",
                        payload_hint={"run_id": run_id},
                    ),
                ],
            ))
    except Exception:
        logger.error("[Approvals] Failed to query paused runs", exc_info=True)

    # 3. Completed PRDs awaiting publishing
    try:
        completed_query = {
            **base_query,
            "status": "completed",
        }
        completed_runs = list(
            db["workingIdeas"]
            .find(completed_query, {"_id": 0})
            .sort("created_at", -1)
            .limit(limit)
        )
        for idea in completed_runs:
            run_id = idea.get("run_id", "")
            proj_id = idea.get("project_id", "")

            # Check if all sections approved
            sections = idea.get("sections", {})
            all_approved = True
            if isinstance(sections, dict):
                for sec in sections.values():
                    if isinstance(sec, dict) and not sec.get("is_approved"):
                        all_approved = False
                        break

            if not all_approved:
                continue

            # Confluence publishing
            if not idea.get("confluence_url"):
                items.append(ApprovalItem(
                    id=f"pub:confluence:{run_id}",
                    kind="publish_confluence",
                    run_id=run_id,
                    project_id=proj_id,
                    title="Publish to Confluence",
                    waiting_since=_iso(idea.get("completed_at") or idea.get("created_at")),
                    actions=[
                        ApprovalAction(
                            label="Publish",
                            endpoint=f"POST /publishing/confluence/{run_id}",
                            payload_hint={"run_id": run_id},
                        ),
                    ],
                ))

            # Jira ticketing
            if not idea.get("jira_output") and not idea.get("jira_skeleton"):
                items.append(ApprovalItem(
                    id=f"pub:jira:{run_id}",
                    kind="publish_jira",
                    run_id=run_id,
                    project_id=proj_id,
                    title="Create Jira tickets",
                    waiting_since=_iso(idea.get("completed_at") or idea.get("created_at")),
                    actions=[
                        ApprovalAction(
                            label="Create tickets",
                            endpoint=f"POST /publishing/jira/{run_id}",
                            payload_hint={"run_id": run_id},
                        ),
                    ],
                ))
    except Exception:
        logger.error("[Approvals] Failed to query publishing approvals", exc_info=True)

    return items[:limit]


@router.get(
    "/pending",
    response_model=ApprovalListResponse,
    summary="List pending approvals",
    description=(
        "Returns items the authenticated user can act on across all "
        "their accessible projects. Items include PRD sections awaiting "
        "approval, paused runs, and completed PRDs awaiting publishing."
    ),
    responses={
        200: {"description": "Approvals returned successfully."},
        **_ERROR_RESPONSES,
    },
)
async def list_pending_approvals(
    project_id: str | None = Query(
        default=None, description="Filter by project ID."
    ),
    limit: int = Query(default=100, ge=1, le=500, description="Max items to return."),
    user: dict = Depends(require_sso_user),
) -> ApprovalListResponse:
    """Return all pending approval items for the authenticated user."""
    tenant = TenantContext.from_user(user)
    logger.info(
        "[Approvals] Listing pending approvals user_id=%s project_id=%s",
        user.get("user_id"), project_id,
    )
    try:
        items = _build_approval_items(
            project_id=project_id, tenant=tenant, limit=limit,
        )
    except Exception as exc:
        logger.error(
            "[Approvals] Failed to build approvals: %s", exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to query approvals",
        ) from exc

    return ApprovalListResponse(count=len(items), items=items)
