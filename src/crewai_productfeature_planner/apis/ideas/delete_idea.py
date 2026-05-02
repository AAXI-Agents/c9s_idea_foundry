"""DELETE /ideas/{run_id} — Soft-delete an idea with full cascade.

Request:  Path param ``run_id``, optional query param ``purge_remote``.
Response: 200 JSON with cascade summary on success, 404 if missing,
          409 if the idea is currently in-flight (user must pause first).
Database: Sets ``status="deleted"`` on the idea and cascades to:
          - ``crewJobs`` (mirrors status)
          - ``ideation_sessions`` (marks deleted)
          - ``productRequirements`` (sets deleted_at, clears pointers)
          - UX design state on the workingIdeas doc
          If ``purge_remote=true``, also attempts to delete linked Jira
          issues and Confluence pages via their REST APIs (best-effort).
          Broadcasts ``idea_deleted`` WebSocket event.

Soft-delete vs archive — these are intentionally different states:

    * ``deleted``  — user clicked the trash icon. The row must NEVER
                     reappear in the default dashboard listing.
    * ``archived`` — internal lifecycle state used when the system
                     restarts a PRD flow with the same idea text.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis._response_cache import response_cache
from crewai_productfeature_planner.apis.ideas.models import (
    CascadeResult,
    DeleteIdeaResponse,
    RemotePurgeResult,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────


def _cascade_ideation_session(run_id: str, tenant: TenantContext) -> str:
    """Mark ideation session linked to this run_id as deleted.

    Returns the session_id if found, empty string otherwise.
    """
    try:
        from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
            _col,
            update_session_status,
        )

        # Ideation sessions link to PRD via prd_run_id field
        col = _col()
        session = col.find_one({"prd_run_id": run_id}, {"session_id": 1})
        if session:
            session_id = session.get("session_id", "")
            update_session_status(session_id=session_id, status="deleted", tenant=tenant)
            return session_id
    except Exception:  # noqa: BLE001
        logger.debug(
            "Could not cascade to ideation session for run_id=%s",
            run_id, exc_info=True,
        )
    return ""


def _cascade_product_requirements(run_id: str) -> dict[str, int]:
    """Set deleted_at on the delivery record and return link counts cleared."""
    from datetime import datetime, timezone

    jira_cleared = 0
    confluence_cleared = 0

    try:
        from crewai_productfeature_planner.mongodb.client import get_db
        from crewai_productfeature_planner.mongodb.product_requirements.repository import (
            PRODUCT_REQUIREMENTS_COLLECTION,
        )

        db = get_db()
        col = db[PRODUCT_REQUIREMENTS_COLLECTION]
        doc = col.find_one({"run_id": run_id})
        if doc:
            if doc.get("confluence_page_id") or doc.get("confluence_url"):
                confluence_cleared = 1
            if doc.get("jira_tickets"):
                jira_cleared = len(doc["jira_tickets"])

            col.update_one(
                {"run_id": run_id},
                {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat(), "status": "deleted"}},
            )
    except Exception:  # noqa: BLE001
        logger.debug(
            "Could not cascade to productRequirements for run_id=%s",
            run_id, exc_info=True,
        )

    return {"jira_cleared": jira_cleared, "confluence_cleared": confluence_cleared}


def _clear_ux_state(run_id: str) -> int:
    """Clear UX design pointers on workingIdeas. Returns 1 if cleared, else 0."""
    try:
        from crewai_productfeature_planner.mongodb.client import get_db
        from crewai_productfeature_planner.mongodb.working_ideas._common import (
            WORKING_COLLECTION,
        )

        db = get_db()
        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id, "ux_design_status": {"$exists": True, "$ne": ""}},
            {"$set": {"ux_design_status": "deleted", "ux_output_file": ""}},
        )
        return 1 if result.modified_count else 0
    except Exception:  # noqa: BLE001
        logger.debug(
            "Could not clear UX state for run_id=%s",
            run_id, exc_info=True,
        )
        return 0


def _count_sections(doc: dict[str, Any]) -> int:
    """Count non-empty section keys in the workingIdeas document."""
    section = doc.get("section")
    if isinstance(section, dict):
        return len([k for k, v in section.items() if v])
    return 0


def _purge_remote_integrations(run_id: str) -> RemotePurgeResult:
    """Best-effort delete of linked Jira issues and Confluence pages."""
    result = RemotePurgeResult(attempted=True)

    try:
        from crewai_productfeature_planner.mongodb.client import get_db
        from crewai_productfeature_planner.mongodb.product_requirements.repository import (
            PRODUCT_REQUIREMENTS_COLLECTION,
        )

        db = get_db()
        doc = db[PRODUCT_REQUIREMENTS_COLLECTION].find_one({"run_id": run_id})
        if not doc:
            return result

        # Delete Confluence page
        confluence_page_id = doc.get("confluence_page_id", "")
        if confluence_page_id:
            try:
                _delete_confluence_page(confluence_page_id)
                result.confluence_deleted.append(confluence_page_id)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"confluence:{confluence_page_id}:{exc}")

        # Delete Jira issues
        jira_tickets = doc.get("jira_tickets") or []
        for ticket in jira_tickets:
            key = ticket.get("key", "")
            if key:
                try:
                    _delete_jira_issue(key)
                    result.jira_deleted.append(key)
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(f"jira:{key}:{exc}")

    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"fetch_delivery_record:{exc}")

    return result


def _delete_confluence_page(page_id: str) -> None:
    """Delete a Confluence page by ID."""
    import os

    from crewai_productfeature_planner.tools.confluence_tool import (
        _build_auth_header,
        _confluence_request,
    )

    base_url = os.environ.get("ATLASSIAN_BASE_URL", "")
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    if not (base_url and username and api_token):
        raise RuntimeError("Confluence credentials not configured")

    auth_header = _build_auth_header(username, api_token)
    url = f"{base_url}/wiki/rest/api/content/{page_id}"
    _confluence_request("DELETE", url, auth_header=auth_header)


def _delete_jira_issue(issue_key: str) -> None:
    """Delete a Jira issue by key."""
    import os

    from crewai_productfeature_planner.tools.jira._http import _jira_request

    base_url = os.environ.get("ATLASSIAN_BASE_URL", "")
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    if not (base_url and username and api_token):
        raise RuntimeError("Jira credentials not configured")

    import base64
    credentials = f"{username}:{api_token}"
    auth_header = f"Basic {base64.b64encode(credentials.encode()).decode()}"
    url = f"{base_url}/rest/api/3/issue/{issue_key}"
    _jira_request("DELETE", url, auth_header=auth_header)


def _broadcast_idea_deleted(run_id: str) -> None:
    """Broadcast idea_deleted event on the PRD WebSocket channel."""
    try:
        from crewai_productfeature_planner.apis.prd._route_websocket import broadcast_sync

        broadcast_sync(run_id, {"type": "idea_deleted", "run_id": run_id})
    except Exception:  # noqa: BLE001
        logger.debug(
            "Could not broadcast idea_deleted for run_id=%s",
            run_id, exc_info=True,
        )


# ── Route ─────────────────────────────────────────────────────────────


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_200_OK,
    response_model=DeleteIdeaResponse,
    summary="Soft-delete an idea with cascade",
)
async def delete_idea(
    run_id: str,
    purge_remote: bool = Query(default=False, description="Also delete linked Jira/Confluence remotely"),
    user: dict = Depends(require_sso_user),
) -> DeleteIdeaResponse:
    """Soft-delete an idea and cascade to all derived records."""
    from crewai_productfeature_planner.mongodb.working_ideas._queries import (
        find_run_any_status,
    )
    from crewai_productfeature_planner.mongodb.working_ideas._status import (
        mark_deleted,
    )

    tenant = TenantContext.from_user(user)
    doc = find_run_any_status(run_id, tenant=tenant)
    if not doc:
        logger.warning(
            "[Ideas] DELETE not found run_id=%s user_id=%s",
            run_id, user.get("user_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {run_id}",
        )

    # Reject deletion of actively running ideas — user must pause first.
    if doc.get("status") == "inprogress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idea is currently in-flight. Pause the PRD flow before deleting.",
        )

    logger.info(
        "[Ideas] DELETE run_id=%s user_id=%s purge_remote=%s",
        run_id, user.get("user_id"), purge_remote,
    )

    # Unblock pending approval gates so any paused flow thread exits.
    try:
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _unblock_gates_for_cancel,
        )
        _unblock_gates_for_cancel(run_id)
    except Exception:  # noqa: BLE001
        logger.debug(
            "Could not unblock gates for run_id=%s",
            run_id, exc_info=True,
        )

    # 1. Soft-delete the idea row.
    mark_deleted(run_id)

    # 2. Mirror to the crewJobs collection.
    try:
        from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
            update_job_status,
        )
        update_job_status(run_id, "deleted")
    except Exception:  # noqa: BLE001
        logger.debug(
            "Could not update crewJob status for run_id=%s",
            run_id, exc_info=True,
        )

    # 3. Cascade to ideation session.
    session_id = _cascade_ideation_session(run_id, tenant)

    # 4. Cascade to productRequirements.
    req_counts = _cascade_product_requirements(run_id)

    # 5. Clear UX design state.
    ux_cleared = _clear_ux_state(run_id)

    # 6. Remote purge (best-effort).
    purge_result = RemotePurgeResult()
    if purge_remote:
        purge_result = _purge_remote_integrations(run_id)
        if purge_result.errors:
            logger.warning(
                "[Ideas] Remote purge partial failure run_id=%s errors=%s",
                run_id, purge_result.errors,
            )

    # 7. Broadcast WebSocket event.
    _broadcast_idea_deleted(run_id)

    # 8. Invalidate response cache.
    response_cache.invalidate("ideas")

    # Build cascade result.
    cascade = CascadeResult(
        ideation_session_id=session_id,
        prd_run_id=run_id,
        sections_count=_count_sections(doc),
        jira_links_cleared=req_counts.get("jira_cleared", 0),
        confluence_links_cleared=req_counts.get("confluence_cleared", 0),
        ux_runs_cleared=ux_cleared,
        remote_purge=purge_result,
    )

    response = DeleteIdeaResponse(
        status="deleted",
        run_id=run_id,
        cascaded=cascade,
    )

    # If remote purge had errors, return 502 to signal partial failure.
    if purge_remote and purge_result.errors:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=response.model_dump(),
        )

    return response
