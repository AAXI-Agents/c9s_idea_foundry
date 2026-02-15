"""PRD flow router - kickoff, status, approval, pause, resume endpoints."""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from crewai_productfeature_planner.apis.prd.models import (
    PRDActionResponse,
    PRDApproveRequest,
    PRDDraftDetail,
    PRDKickoffRequest,
    PRDKickoffResponse,
    PRDPauseRequest,
    PRDResumableListResponse,
    PRDResumableRun,
    PRDResumeRequest,
    PRDResumeResponse,
    PRDRunStatusResponse,
    PRDSectionDetail,
    SECTION_KEYS,
)
from crewai_productfeature_planner.apis.prd.service import (
    resume_prd_flow,
    run_prd_flow,
)
from crewai_productfeature_planner.apis.shared import (
    FlowRun,
    FlowStatus,
    approval_decisions,
    approval_events,
    approval_feedback,
    pause_requested,
    runs,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/flow/runs/{run_id}",
    tags=["Flow Runs"],
    summary="Get flow run status",
    response_model=PRDRunStatusResponse,
    description=(
        "Returns the current status, iteration, section progress, and draft "
        "content for a flow run. Includes per-section approval status. "
        "Use this endpoint to poll for state changes after kickoff, "
        "approval, pause, or resume actions."
    ),
    responses={
        200: {"description": "Run details returned successfully."},
        404: {"description": "Run not found."},
    },
)
async def get_run_status(run_id: str):
    """Check the status of a flow run."""
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    data = run.model_dump()
    data["current_draft"] = PRDDraftDetail(
        sections=[
            PRDSectionDetail(**s.model_dump()) for s in run.current_draft.sections
        ],
        all_approved=run.current_draft.all_approved(),
    ).model_dump()
    return data


@router.get(
    "/flow/runs",
    tags=["Flow Runs"],
    summary="List all flow runs",
    description=(
        "Returns all in-memory flow runs. Useful for dashboards and MCP "
        "clients to discover active, paused, or completed runs."
    ),
    responses={
        200: {"description": "List of all runs."},
    },
)
async def list_runs():
    """Return a summary of all in-memory runs."""
    result = []
    for run in runs.values():
        result.append({
            "run_id": run.run_id,
            "flow_name": run.flow_name,
            "status": run.status.value,
            "iteration": run.iteration,
            "created_at": run.created_at,
            "current_section_key": run.current_section_key,
        })
    return {"count": len(result), "runs": result}


@router.post(
    "/flow/prd/kickoff",
    status_code=202,
    tags=["Flow Runs"],
    summary="Kick off PRD flow",
    response_model=PRDKickoffResponse,
    description=(
        "Starts the PRD generation flow asynchronously. The flow drafts "
        "each section one by one, starting with Executive Summary. "
        "After each section draft, the flow pauses and waits for user "
        "approval via POST /flow/prd/approve. "
        "Poll GET /flow/runs/{run_id} to track progress."
    ),
    responses={
        202: {"description": "Flow accepted and queued."},
        422: {"description": "Validation error."},
    },
)
async def kickoff_prd_flow(
    request: PRDKickoffRequest, background_tasks: BackgroundTasks
):
    """Trigger the iterative PRD generation flow."""
    run_id = uuid.uuid4().hex[:12]
    run = FlowRun(run_id=run_id, flow_name="prd")
    runs[run_id] = run

    logger.info(
        "[API] Queueing PRD flow (run_id=%s, idea='%s')",
        run_id,
        request.idea[:80],
    )

    background_tasks.add_task(run_prd_flow, run_id, request.idea)

    return PRDKickoffResponse(
        run_id=run_id,
        flow_name="prd",
        status=run.status.value,
        message=(
            "PRD flow queued. Poll GET /flow/runs/{run_id} for status. "
            "POST /flow/prd/approve to approve or continue."
        ),
    )


@router.post(
    "/flow/prd/approve",
    tags=["Approvals"],
    summary="Approve or continue section refinement",
    response_model=PRDActionResponse,
    description=(
        "Submits a user decision for the current section. Actions:\n\n"
        "- **approve=true** - approve the current section, the flow moves "
        "to the next section.\n"
        "- **approve=false** - the agent self-critiques and refines the "
        "current section.\n"
        "- **approve=false + feedback** - the user feedback replaces the "
        "agent self-critique for more targeted refinement.\n\n"
        "Only valid when the run is in awaiting_approval state."
    ),
    responses={
        200: {"description": "Decision accepted."},
        404: {"description": "Run not found."},
        409: {"description": "Run is not awaiting approval."},
    },
)
async def approve_prd(request: PRDApproveRequest):
    """Approve, continue refining, or provide critique feedback."""
    run = runs.get(request.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != FlowStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Run is not awaiting approval (status={run.status.value})",
        )

    approval_decisions[request.run_id] = request.approve
    if request.feedback and not request.approve:
        approval_feedback[request.run_id] = request.feedback

    event = approval_events.get(request.run_id)
    if event is not None:
        event.set()

    section_key = run.current_section_key

    if request.approve:
        action = "approved"
    elif request.feedback:
        action = "continuing refinement with user feedback"
    else:
        action = "continuing refinement"

    logger.info("[API] User %s section '%s' run_id=%s", action, section_key, request.run_id)
    return PRDActionResponse(
        run_id=request.run_id,
        action=action,
        section=section_key,
        message=f"Section '{section_key}' {action}. Poll GET /flow/runs/{request.run_id} for updates.",
    )


@router.post(
    "/flow/prd/pause",
    tags=["Approvals"],
    summary="Pause and save current progress",
    response_model=PRDActionResponse,
    description=(
        "Pauses the running PRD flow and saves current progress to MongoDB. "
        "The flow can be resumed later via POST /flow/prd/resume.\n\n"
        "- If the run is in awaiting_approval, the pause takes effect immediately.\n"
        "- If the run is in running, a pause flag is set and the flow "
        "will pause at the next approval checkpoint.\n\n"
        "Equivalent to the CLI pause action."
    ),
    responses={
        200: {"description": "Pause requested successfully."},
        404: {"description": "Run not found."},
        409: {"description": "Run cannot be paused in its current state."},
    },
)
async def pause_prd(request: PRDPauseRequest):
    """Pause a running or awaiting-approval flow."""
    run = runs.get(request.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in (FlowStatus.RUNNING, FlowStatus.AWAITING_APPROVAL):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Run cannot be paused (status={run.status.value}). "
                f"Only running or awaiting_approval runs can be paused."
            ),
        )

    section_key = run.current_section_key
    pause_requested[request.run_id] = True

    if run.status == FlowStatus.AWAITING_APPROVAL:
        event = approval_events.get(request.run_id)
        if event is not None:
            event.set()
        logger.info("[API] Pause triggered immediately for run_id=%s", request.run_id)
    else:
        logger.info("[API] Pause flag set for run_id=%s (will pause at next checkpoint)", request.run_id)

    return PRDActionResponse(
        run_id=request.run_id,
        action="paused",
        section=section_key,
        message=(
            f"Pause requested for run {request.run_id}. "
            f"Progress will be saved. Use POST /flow/prd/resume to continue later."
        ),
    )


@router.get(
    "/flow/prd/resumable",
    tags=["Flow Runs"],
    summary="List resumable (unfinalized) runs",
    response_model=PRDResumableListResponse,
    description=(
        "Returns a list of working ideas from MongoDB that have not been "
        "finalized. These are runs that were paused, abandoned, or "
        "interrupted and can be resumed via POST /flow/prd/resume.\n\n"
        "Equivalent to the CLI startup prompt that checks for unfinalized runs."
    ),
    responses={
        200: {"description": "Resumable runs listed successfully."},
    },
)
async def list_resumable_runs():
    """List unfinalized working ideas that can be resumed."""
    from crewai_productfeature_planner.mongodb import find_unfinalized

    unfinalized = find_unfinalized()
    items = []
    for r in unfinalized:
        created = r.get("created_at")
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        items.append(PRDResumableRun(
            run_id=r["run_id"],
            idea=r.get("idea", ""),
            iteration=r.get("iteration", 0),
            created_at=str(created) if created else None,
            sections=r.get("sections", []),
        ))
    return PRDResumableListResponse(count=len(items), runs=items)


@router.post(
    "/flow/prd/resume",
    status_code=202,
    tags=["Flow Runs"],
    summary="Resume a paused or unfinalized run",
    response_model=PRDResumeResponse,
    description=(
        "Resumes a previously paused or unfinalized PRD flow. Restores "
        "section state from MongoDB and continues the iteration loop "
        "from the next unapproved section.\n\n"
        "The run_id must appear in the resumable list returned by "
        "GET /flow/prd/resumable.\n\n"
        "Equivalent to selecting a run to resume in the CLI startup prompt."
    ),
    responses={
        202: {"description": "Flow resumed and running."},
        404: {"description": "Run not found in resumable runs."},
        409: {"description": "Run is already active."},
    },
)
async def resume_prd(
    request: PRDResumeRequest, background_tasks: BackgroundTasks
):
    """Resume a paused/unfinalized PRD flow from saved state."""
    existing = runs.get(request.run_id)
    if existing is not None and existing.status in (
        FlowStatus.RUNNING, FlowStatus.AWAITING_APPROVAL, FlowStatus.PENDING,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Run is already active (status={existing.status.value})",
        )

    from crewai_productfeature_planner.mongodb import find_unfinalized
    unfinalized = find_unfinalized()
    run_info = next((r for r in unfinalized if r["run_id"] == request.run_id), None)
    if run_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run {request.run_id} not found in resumable (unfinalized) runs",
        )

    run = FlowRun(run_id=request.run_id, flow_name="prd")
    runs[request.run_id] = run

    background_tasks.add_task(resume_prd_flow, request.run_id)

    sections_done = len(run_info.get("sections", []))
    return PRDResumeResponse(
        run_id=request.run_id,
        flow_name="prd",
        status="running",
        sections_approved=sections_done,
        sections_total=len(SECTION_KEYS),
        next_section=None,
        message=(
            f"Resuming run {request.run_id} from saved state. "
            f"Poll GET /flow/runs/{request.run_id} for status."
        ),
    )
