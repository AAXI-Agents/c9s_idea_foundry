"""Status endpoint for querying Agentic Team pipeline progress.

GET /api/agentic-team/status/{idea_id} — Returns pipeline status for
all tasks related to an idea, including per-task progress and overall
completion percentage.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from crewai_productfeature_planner.apis.agentic_team._config import (
    AGENTIC_TEAM_ENABLED,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agentic-team", tags=["Agentic Team"])


@router.get(
    "/status/{idea_id}",
    summary="Get Agentic Team pipeline status for an idea",
    description=(
        "Queries the Agentic Team service for pipeline status of all tasks "
        "related to the given idea. Returns per-task progress and overall "
        "completion percentage."
    ),
    response_model=dict[str, Any],
)
async def get_agent_status(idea_id: str) -> dict[str, Any]:
    """Return pipeline status for all tasks related to an idea."""
    if not AGENTIC_TEAM_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agentic Team integration is not enabled",
        )

    from crewai_productfeature_planner.apis.agentic_team._service import (
        get_idea_agent_status,
    )

    logger.info("[AgenticTeamStatus] Querying status for idea_id=%s", idea_id)

    result = await get_idea_agent_status(idea_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Agentic Team service",
        )

    return result


@router.get(
    "/dashboard",
    summary="Get Agentic Team pipeline dashboard",
    description=(
        "Returns an overview of all pipeline runs, including active, "
        "completed, and failed tasks."
    ),
    response_model=dict[str, Any],
)
async def get_dashboard() -> dict[str, Any]:
    """Return the Agentic Team pipeline dashboard overview."""
    if not AGENTIC_TEAM_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agentic Team integration is not enabled",
        )

    from crewai_productfeature_planner.apis.agentic_team._service import (
        get_pipeline_dashboard,
    )

    logger.info("[AgenticTeamDashboard] Querying pipeline dashboard")

    result = await get_pipeline_dashboard()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Agentic Team service",
        )

    return result


@router.get(
    "/task/{issue_key}",
    summary="Get pipeline status for a single Jira task",
    description=(
        "Returns the Agentic Team pipeline status for a single Jira issue, "
        "including current stage, progress, and any errors."
    ),
    response_model=dict[str, Any],
)
async def get_task_pipeline_status(issue_key: str) -> dict[str, Any]:
    """Return pipeline status for a single Jira task."""
    if not AGENTIC_TEAM_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agentic Team integration is not enabled",
        )

    from crewai_productfeature_planner.apis.agentic_team._service import (
        get_task_status,
    )

    logger.info("[AgenticTeamTask] Querying status for issue_key=%s", issue_key)

    result = await get_task_status(issue_key)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Agentic Team service",
        )

    return result
