"""GET /flow/runs/{run_id}/versions — PRD version history.

Returns the git-style version history for a PRD, including full section
snapshots and changelog entries for each version.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Response models ───────────────────────────────────────────────────


class VersionEntry(BaseModel):
    """A single PRD version snapshot."""

    version: int = Field(..., description="Version number (1, 2, 3, ...).")
    changelog: str = Field(default="", description="What changed in this version.")
    sections: dict[str, str] = Field(
        default_factory=dict,
        description="Section key → content snapshot.",
    )
    created_at: str = Field(default="", description="ISO-8601 creation timestamp.")


class VersionHistoryResponse(BaseModel):
    """PRD version history."""

    run_id: str = Field(..., description="Flow run identifier.")
    current_version: int = Field(default=0, description="Latest version number.")
    versions: list[VersionEntry] = Field(
        default_factory=list,
        description="Version snapshots, oldest first.",
    )


# ── Endpoint ──────────────────────────────────────────────────────────


@router.get(
    "/flow/runs/{run_id}/versions",
    tags=["Flow Runs"],
    summary="Get PRD version history",
    response_model=VersionHistoryResponse,
    description=(
        "Returns the git-style version history for a PRD run. "
        "Each version includes a full section content snapshot and "
        "a changelog entry describing what changed."
    ),
    responses={
        200: {"description": "Version history returned successfully."},
        404: {"description": "Run not found."},
        500: {"description": "Internal server error."},
        503: {"description": "Service unavailable."},
    },
)
async def get_run_versions(
    run_id: str,
    user: dict = Depends(require_sso_user),
):
    """Return version history for a PRD run."""
    from crewai_productfeature_planner.mongodb.product_requirements import (
        get_current_version,
        get_version_history,
    )
    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_run_any_status,
    )

    idea_doc = find_run_any_status(run_id)
    if idea_doc is None:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        history = get_version_history(run_id)
        current = get_current_version(run_id)
    except Exception as exc:
        logger.error(
            "[Versions] Failed to fetch version history for run_id=%s: %s",
            run_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to fetch version history",
        ) from exc

    entries = [
        VersionEntry(
            version=v.get("version", 0),
            changelog=v.get("changelog", ""),
            sections=v.get("sections", {}),
            created_at=v.get("created_at", ""),
        )
        for v in history
    ]

    return VersionHistoryResponse(
        run_id=run_id,
        current_version=current,
        versions=entries,
    )
