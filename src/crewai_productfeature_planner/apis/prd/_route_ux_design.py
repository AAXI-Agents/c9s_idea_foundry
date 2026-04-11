"""UX Design endpoint — trigger UX design generation for a completed PRD."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.prd.models import ErrorResponse
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

_ERROR_RESPONSES = {
    500: {"description": "Internal server error.", "model": ErrorResponse},
    503: {
        "description": (
            "LLM / OpenAI / Gemini service unavailable. The UX design "
            "flow will fail and status will reset to empty."
        ),
        "model": ErrorResponse,
    },
}

ux_design_router = APIRouter()


# ── Response model ────────────────────────────────────────────


class UXDesignKickoffResponse(BaseModel):
    """Response for POST /flow/ux-design/{run_id}."""

    run_id: str = Field(..., description="The PRD run ID being processed.")
    ux_design_status: str = Field(
        ..., description="UX design status: 'generating', 'completed', or ''.",
    )
    message: str = Field(..., description="Human-readable status message.")


# ── Background task ───────────────────────────────────────────


def _run_ux_design_background(run_id: str, idea_doc: dict) -> None:
    """Execute UX design flow in background thread."""
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow
    from crewai_productfeature_planner.flows.ux_design_flow import (
        kick_off_ux_design_flow,
    )
    from crewai_productfeature_planner.mongodb.working_ideas import save_ux_design
    from crewai_productfeature_planner.scripts.crewai_bus_fix import (
        ensure_crewai_event_bus,
    )

    try:
        ensure_crewai_event_bus()

        save_ux_design(run_id, status="generating")

        flow = PRDFlow()
        flow.state.run_id = run_id
        flow.state.idea = idea_doc.get("idea") or idea_doc.get("finalized_idea") or ""
        flow.state.executive_product_summary = idea_doc.get("finalized_idea") or ""
        flow.state.requirements_breakdown = idea_doc.get("requirements_breakdown") or ""

        result = kick_off_ux_design_flow(flow)

        save_ux_design(run_id, status="completed")
        logger.info("[UXDesign] Completed for run_id=%s", run_id)
    except Exception:
        logger.exception("[UXDesign] Failed for run_id=%s", run_id)
        save_ux_design(run_id, status="")


# ── Endpoint ──────────────────────────────────────────────────


@ux_design_router.post(
    "/flow/ux-design/{run_id}",
    status_code=202,
    tags=["Flow Runs"],
    summary="Trigger UX design generation",
    response_model=UXDesignKickoffResponse,
    description=(
        "Triggers UX design generation for a completed PRD. The PRD "
        "must be in `completed` status. The UX design flow runs "
        "asynchronously — poll `GET /flow/runs/{run_id}` and check "
        "the `ux_design_status` field for progress.\n\n"
        "Returns 409 if UX design is already generating or completed."
    ),
    responses={
        202: {"description": "UX design generation started."},
        404: {"description": "PRD run not found."},
        409: {"description": "PRD not completed or UX design already in progress."},
        **_ERROR_RESPONSES,
    },
)
async def kickoff_ux_design(
    run_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_sso_user),
):
    """Start UX design generation for a completed PRD."""
    logger.info(
        "[API] UX design kickoff by user_id=%s run_id=%s",
        user.get("user_id"), run_id,
    )

    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_run_any_status,
    )

    idea_doc = find_run_any_status(run_id)
    if idea_doc is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    status = idea_doc.get("status", "")
    if status != "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"PRD must be in 'completed' status to generate UX design "
                f"(current status: '{status}')"
            ),
        )

    ux_status = idea_doc.get("ux_design_status", "")
    if ux_status == "generating":
        raise HTTPException(
            status_code=409,
            detail="UX design is already being generated for this run",
        )

    background_tasks.add_task(_run_ux_design_background, run_id, idea_doc)

    return UXDesignKickoffResponse(
        run_id=run_id,
        ux_design_status="generating",
        message=(
            f"UX design generation started for run {run_id}. "
            f"Poll GET /flow/runs/{run_id} and check ux_design_status."
        ),
    )


# ── Web-app facing endpoints (A2/A3 from Gap Analysis) ──────


class UXDesignKickoffRequest(BaseModel):
    """Request body for ``POST /flow/ux/kickoff``."""

    run_id: str = Field(..., description="The PRD run ID to generate UX design for.")


class UXDesignStatusResponse(BaseModel):
    """Response for ``GET /flow/ux/status/{run_id}``."""

    run_id: str = Field(..., description="The PRD run ID.")
    status: str = Field(
        default="",
        description="UX design status: '', 'generating', or 'completed'.",
    )
    current_step: str = Field(
        default="",
        description="Current UX design step label, if available.",
    )
    design_md_ready: bool = Field(
        default=False,
        description="Whether the UX design markdown content is ready.",
    )
    stitch_completed: bool = Field(
        default=False,
        description="Whether the design sections have been stitched.",
    )
    figma_uploaded: bool = Field(
        default=False,
        description="Whether the design was uploaded to Figma.",
    )
    figma_url: str | None = Field(
        default=None,
        description="Figma file URL, if uploaded.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if UX design generation failed.",
    )


@ux_design_router.post(
    "/flow/ux/kickoff",
    status_code=202,
    tags=["UX Design"],
    summary="Trigger UX design generation (web-app format)",
    response_model=UXDesignKickoffResponse,
    description=(
        "Web-app-compatible endpoint for triggering UX design generation. "
        "Accepts ``run_id`` in the request body instead of the URL path. "
        "Delegates to the same background logic as ``POST /flow/ux-design/{run_id}``."
    ),
    responses={
        202: {"description": "UX design generation started."},
        404: {"description": "PRD run not found."},
        409: {"description": "PRD not completed or UX design already in progress."},
        **_ERROR_RESPONSES,
    },
)
async def kickoff_ux_design_web(
    body: UXDesignKickoffRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_sso_user),
):
    """Start UX design generation — body-based variant for the web app."""
    return await kickoff_ux_design(body.run_id, background_tasks, user)


@ux_design_router.get(
    "/flow/ux/status/{run_id}",
    tags=["UX Design"],
    summary="Get UX design status",
    response_model=UXDesignStatusResponse,
    description=(
        "Returns the current UX design generation status for a run. "
        "The frontend polls this endpoint after triggering "
        "``POST /flow/ux/kickoff``."
    ),
    responses={
        200: {"description": "UX design status returned successfully."},
        404: {"description": "PRD run not found."},
        **_ERROR_RESPONSES,
    },
)
async def get_ux_design_status(
    run_id: str,
    user: dict = Depends(require_sso_user),
) -> UXDesignStatusResponse:
    """Return UX design status for a run."""
    logger.info(
        "[API] UX design status requested by user_id=%s run_id=%s",
        user.get("user_id"), run_id,
    )

    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_run_any_status,
    )

    idea_doc = find_run_any_status(run_id)
    if idea_doc is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    ux_status = (
        idea_doc.get("ux_design_status")
        or idea_doc.get("figma_design_status")
        or ""
    )
    ux_content = idea_doc.get("ux_design_content", "")
    figma_url = idea_doc.get("figma_url") or None

    # Derive boolean flags from the stored status.
    is_completed = ux_status == "completed"
    design_md_ready = is_completed and bool(ux_content)
    stitch_completed = design_md_ready
    figma_uploaded = bool(figma_url)

    # Step label for in-progress runs.
    if ux_status == "generating":
        current_step = "Running UX design agents"
    elif is_completed:
        current_step = "Completed"
    else:
        current_step = ""

    # If status was reset to empty after an error, check for an error
    # field on the doc.
    error = idea_doc.get("ux_design_error") or None

    return UXDesignStatusResponse(
        run_id=run_id,
        status=ux_status,
        current_step=current_step,
        design_md_ready=design_md_ready,
        stitch_completed=stitch_completed,
        figma_uploaded=figma_uploaded,
        figma_url=figma_url,
        error=error,
    )
