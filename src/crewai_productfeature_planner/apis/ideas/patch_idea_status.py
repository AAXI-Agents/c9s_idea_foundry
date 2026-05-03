"""PATCH /ideas/{run_id}/status — Update idea status (archive / pause).

Request:  Path param ``run_id``, body IdeaStatusUpdate.
Response: Updated IdeaItem.
Database: Calls ``mark_archived()`` or ``mark_paused()`` on ``workingIdeas``;
          also updates ``crewJobs`` status when archiving.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from crewai_productfeature_planner.apis._response_cache import response_cache
from crewai_productfeature_planner.apis.ideas.models import (
    IdeaItem,
    IdeaStatusUpdate,
    idea_fields,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


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

    tenant = TenantContext.from_user(user)
    doc = find_run_any_status(run_id, tenant=tenant)
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
        mark_archived(run_id, tenant=tenant)
        # Also archive the crew job
        try:
            from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
                update_job_status,
            )
            update_job_status(run_id, "archived")
        except Exception:  # noqa: BLE001
            logger.debug("Could not archive crewJob for %s", run_id, exc_info=True)
    elif body.status == "paused":
        mark_paused(run_id, tenant=tenant)

    # Invalidate the GET /ideas response cache so the just-archived /
    # paused row disappears from the dashboard immediately instead of
    # lingering for the 5-second TTL window. Without this, repeated
    # 'delete' actions appear to do nothing because the cached list is
    # served back to the client.
    response_cache.invalidate("ideas")

    updated = find_run_any_status(run_id, tenant=tenant)
    return IdeaItem(**idea_fields(updated or doc))
