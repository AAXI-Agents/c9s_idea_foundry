"""GET /ideas/{run_id} — Get a single idea by run_id.

Request:  Path param ``run_id``.
Response: IdeaItem.
Database: Queries ``workingIdeas`` collection via ``find_run_any_status()``.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from crewai_productfeature_planner.apis.ideas.models import IdeaItem, idea_fields
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


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
    return IdeaItem(**idea_fields(doc))
