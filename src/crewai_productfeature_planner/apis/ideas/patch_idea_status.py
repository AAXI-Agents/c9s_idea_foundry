"""PATCH /ideas/{run_id}/status — Update idea status (archive / pause).

Request:  Path param ``run_id``, body IdeaStatusUpdate.
Response: Updated IdeaItem.
Database: Calls ``mark_archived()`` or ``mark_paused()`` on ``workingIdeas``;
          also updates ``crewJobs`` status when archiving.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from crewai_productfeature_planner.apis.ideas.models import (
    IdeaItem,
    IdeaStatusUpdate,
    idea_fields,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
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
    return IdeaItem(**idea_fields(updated or doc))
