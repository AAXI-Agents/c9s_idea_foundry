"""PRD flow router - kickoff, status, approval, pause, resume endpoints."""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from crewai_productfeature_planner.apis.prd.models import (
    ErrorResponse,
    JobDetail,
    JobListResponse,
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
    approval_selected,
    pause_requested,
    runs,
)
from crewai_productfeature_planner.mongodb.crew_jobs import (
    create_job,
    find_active_job,
    find_job,
    list_jobs,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Standard error responses documented on every endpoint.
_ERROR_RESPONSES = {
    500: {
        "description": (
            "Internal server error. The `error_code` field will be "
            "`INTERNAL_ERROR`. Check the `message` and `detail` fields "
            "for diagnostics."
        ),
        "model": ErrorResponse,
    },
    503: {
        "description": (
            "LLM / OpenAI / Gemini service unavailable. The `error_code` field "
            "will be `LLM_ERROR` (retries exhausted) or `BILLING_ERROR` "
            "(billing / quota issue). The affected flow run is "
            "automatically paused — resume it after resolving the issue."
        ),
        "model": ErrorResponse,
    },
}


@router.get(
    "/flow/runs/{run_id}",
    tags=["Flow Runs"],
    summary="Get flow run status",
    response_model=PRDRunStatusResponse,
    description=(
        "Returns the current status, iteration, section progress, and draft "
        "content for a flow run. Includes per-section approval status, "
        "current step number, and agent participation details.\n\n"
        "The flow uses a **two-phase architecture**:\n"
        "- **Phase 1** — Executive Summary: iterative refinement (≥ PRD_EXEC_RESUME_THRESHOLD cycles).\n"
        "- **Phase 2** — 9 remaining sections: each auto-iterates between "
        "PRD_SECTION_MIN_ITERATIONS and PRD_SECTION_MAX_ITERATIONS cycles. "
        "A section is auto-approved when the critique contains SECTION_READY "
        "after the minimum iterations are met.\n\n"
        "**Error handling**: any error during the flow sets the status to "
        "``paused`` (never ``failed``), allowing the run to be resumed.\n\n"
        "Use this endpoint to poll for state changes after kickoff, "
        "approval, pause, or resume actions."
    ),
    responses={
        200: {"description": "Run details returned successfully."},
        404: {"description": "Run not found."},
        **_ERROR_RESPONSES,
    },
)
async def get_run_status(run_id: str):
    """Check the status of a flow run."""
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    draft = run.current_draft
    approved_count = sum(1 for s in draft.sections if s.is_approved)
    total_sections = len(draft.sections)
    # Resolve current step number from draft
    current_section = draft.get_section(run.current_section_key) if run.current_section_key else None
    current_step = current_section.step if current_section else 0
    data = run.model_dump()
    data["current_draft"] = PRDDraftDetail(
        sections=[
            PRDSectionDetail(**s.model_dump()) for s in draft.sections
        ],
        all_approved=draft.all_approved(),
    ).model_dump()
    data["sections_approved"] = approved_count
    data["sections_total"] = total_sections
    data["current_step"] = current_step
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
        **_ERROR_RESPONSES,
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
        "Starts the PRD generation flow asynchronously.\n\n"
        "**Flow phases:**\n"
        "1. **Idea Refinement** — A Gemini-powered agent enriches the raw idea "
        "(3-10 cycles) before drafting begins.\n"
        "2. **Requirements Breakdown** — The enriched idea is decomposed into "
        "structured requirements.\n"
        "3. **Phase 1: Executive Summary** — Iterative drafting and refinement "
        "(≥ PRD_EXEC_RESUME_THRESHOLD cycles).\n"
        "4. **Phase 2: Sections** — 9 remaining sections are drafted and "
        "auto-iterated between PRD_SECTION_MIN_ITERATIONS and "
        "PRD_SECTION_MAX_ITERATIONS. A section is auto-approved when its "
        "critique contains SECTION_READY after the minimum iterations.\n\n"
        "**Degenerate output guard**: if a refine result exceeds "
        "PRD_SECTION_MAX_CHARS or grows by more than PRD_SECTION_GROWTH_FACTOR "
        "times the previous length, it is treated as garbage LLM output and "
        "the previous version is kept.\n\n"
        "**Error handling**: any error pauses the run (status=``paused``) "
        "rather than marking it failed, so it can be resumed later.\n\n"
        "Set ``auto_approve=true`` in the request body to run the entire "
        "flow without pausing for manual approval (same as CLI mode). "
        "The API responds immediately with 202 and the flow proceeds "
        "autonomously — poll GET /flow/runs/{run_id} for progress.\n\n"
        "Only one job may be active at a time — returns 409 if a job is "
        "already running.\n\n"
        "Poll GET /flow/runs/{run_id} to track progress."
    ),
    responses={
        202: {"description": "Flow accepted and queued."},
        409: {"description": "A job is already active. Only one job can run at a time."},
        422: {"description": "Validation error."},
        **_ERROR_RESPONSES,
    },
)
async def kickoff_prd_flow(
    request: PRDKickoffRequest, background_tasks: BackgroundTasks
):
    """Trigger the iterative PRD generation flow."""
    # Enforce single active job — reject if one is already running
    active = find_active_job()
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A job is already active (job_id={active['job_id']}, "
                f"status={active['status']}). Only one job can run at a time."
            ),
        )

    run_id = uuid.uuid4().hex[:12]
    run = FlowRun(run_id=run_id, flow_name="prd")
    runs[run_id] = run

    # Persist job to crewJobs collection (queued status)
    create_job(job_id=run_id, flow_name="prd", idea=request.idea)

    logger.info(
        "[API] Queueing PRD flow (run_id=%s, idea='%s')",
        run_id,
        request.idea[:80],
    )

    background_tasks.add_task(run_prd_flow, run_id, request.idea, request.auto_approve)

    if request.auto_approve:
        msg = (
            "PRD flow initiated in auto-approve mode — sections will "
            "iterate and approve automatically (like the CLI). "
            f"Poll GET /flow/runs/{run_id} for progress."
        )
    else:
        msg = (
            "PRD flow queued. Poll GET /flow/runs/{run_id} for status. "
            "POST /flow/prd/approve to approve or continue."
        )

    return PRDKickoffResponse(
        run_id=run_id,
        flow_name="prd",
        status=run.status.value,
        message=msg,
    )


@router.post(
    "/flow/prd/approve",
    tags=["Approvals"],
    summary="Approve or continue section refinement",
    response_model=PRDActionResponse,
    description=(
        "Submits a user decision for the current section. Actions:\n\n"
        "- **approve=true** — approve the current section; the flow moves "
        "to the next section.\n"
        "- **approve=false** — the agent self-critiques and refines the "
        "current section (another iteration).\n"
        "- **approve=false + feedback** — the user feedback replaces the "
        "agent self-critique for more targeted refinement.\n\n"
        "**Note:** In CLI mode, sections auto-iterate without manual "
        "approval. This endpoint is used in API/callback mode where "
        "the flow pauses at ``awaiting_approval`` and waits for an "
        "explicit decision.\n\n"
        "Only valid when the run is in ``awaiting_approval`` state."
    ),
    responses={
        200: {"description": "Decision accepted."},
        404: {"description": "Run not found."},
        409: {"description": "Run is not awaiting approval."},
        **_ERROR_RESPONSES,
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
    if request.selected_agent:
        approval_selected[request.run_id] = request.selected_agent

    event = approval_events.get(request.run_id)
    if event is not None:
        event.set()

    section_key = run.current_section_key

    # Compute approval progress
    draft = run.current_draft
    # Count the section being approved now + already approved ones
    approved_count = sum(1 for s in draft.sections if s.is_approved)
    if request.approve:
        # This section will be marked approved by the flow momentarily
        approved_count += 1
    total_sections = len(draft.sections)
    is_final = request.approve and approved_count >= total_sections

    # Resolve step number for the current section
    current_section = draft.get_section(section_key) if section_key else None
    current_step = current_section.step if current_section else 0

    if request.approve:
        action = "approved"
    elif request.feedback:
        action = "continuing refinement with user feedback"
    else:
        action = "continuing refinement"

    logger.info("[API] User %s section '%s' run_id=%s (%d/%d)",
                action, section_key, request.run_id, approved_count, total_sections)

    msg = f"Step {current_step}/{total_sections}: Section '{section_key}' {action}."
    if is_final:
        msg += " All sections approved — the flow will finalize the PRD."
    else:
        msg += f" Poll GET /flow/runs/{request.run_id} for updates."

    return PRDActionResponse(
        run_id=request.run_id,
        action=action,
        section=section_key,
        current_step=current_step,
        sections_approved=approved_count,
        sections_total=total_sections,
        is_final_section=is_final,
        active_agents=run.active_agents,
        dropped_agents=run.dropped_agents,
        agent_errors=run.agent_errors,
        message=msg,
    )


@router.post(
    "/flow/prd/pause",
    tags=["Approvals"],
    summary="Pause and save current progress",
    response_model=PRDActionResponse,
    description=(
        "Pauses the running PRD flow and saves current progress to MongoDB. "
        "The flow can be resumed later via POST /flow/prd/resume.\n\n"
        "- If the run is in ``awaiting_approval``, the pause takes effect "
        "immediately.\n"
        "- If the run is in ``running``, a pause flag is set and the flow "
        "will pause at the next approval checkpoint.\n\n"
        "**Error recovery**: if the flow encounters an error (LLM timeout, "
        "billing issue, etc.), it is automatically paused with status "
        "``paused`` — the run is never marked ``failed``, so it can always "
        "be resumed.\n\n"
        "Equivalent to the CLI pause action."
    ),
    responses={
        200: {"description": "Pause requested successfully."},
        404: {"description": "Run not found."},
        409: {"description": "Run cannot be paused in its current state."},
        **_ERROR_RESPONSES,
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

    # Compute progress to match CLI output
    draft = run.current_draft
    approved_count = sum(1 for s in draft.sections if s.is_approved)
    total_sections = len(draft.sections)
    current_section = draft.get_section(section_key) if section_key else None
    current_step = current_section.step if current_section else 0

    return PRDActionResponse(
        run_id=request.run_id,
        action="paused",
        section=section_key,
        current_step=current_step,
        sections_approved=approved_count,
        sections_total=total_sections,
        is_final_section=False,
        active_agents=run.active_agents,
        dropped_agents=run.dropped_agents,
        agent_errors=run.agent_errors,
        message=(
            f"Pause requested for run {request.run_id}. "
            f"Progress saved ({approved_count}/{total_sections} sections approved). "
            f"Use POST /flow/prd/resume to continue later."
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
        "interrupted (including runs that were automatically paused due "
        "to errors) and can be resumed via POST /flow/prd/resume.\n\n"
        "Each entry includes the section keys that already have draft "
        "content and the last iteration number.\n\n"
        "Equivalent to the CLI startup prompt that checks for unfinalized runs."
    ),
    responses={
        200: {"description": "Resumable runs listed successfully."},
        **_ERROR_RESPONSES,
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
            exec_summary_iterations=r.get("exec_summary_iterations", 0),
            req_breakdown_iterations=r.get("req_breakdown_iterations", 0),
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
        "Set ``auto_approve=true`` in the request body to resume without "
        "pausing for manual approval (same as CLI mode). The API responds "
        "immediately with 202 and the flow proceeds autonomously.\n\n"
        "**Resume behaviour:**\n"
        "- Sections that already have content skip the initial draft step "
        "and go directly into the critique→refine loop.\n"
        "- If Phase 1 (Executive Summary) has ≥ PRD_EXEC_RESUME_THRESHOLD "
        "iterations, Phase 1 is skipped entirely and Phase 2 resumes from "
        "the next unapproved section.\n"
        "- Any degenerate content (empty or whitespace-only) left by a "
        "previous crash is cleaned up before iteration resumes.\n"
        "- Requirements approval is skipped if already completed.\n\n"
        "The run_id must appear in the resumable list returned by "
        "GET /flow/prd/resumable.\n\n"
        "Equivalent to selecting a run to resume in the CLI startup prompt."
    ),
    responses={
        202: {"description": "Flow resumed and running."},
        404: {"description": "Run not found in resumable runs."},
        409: {"description": "Run is already active."},
        **_ERROR_RESPONSES,
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

    background_tasks.add_task(resume_prd_flow, request.run_id, request.auto_approve)

    sections_done = len(run_info.get("sections", []))
    total_sections = len(SECTION_KEYS)
    # Determine next section: first SECTION_KEY not yet in the completed list
    done_set = set(run_info.get("sections", []))
    next_section_key = next(
        (k for k in SECTION_KEYS if k not in done_set), None
    )
    # Resolve step number for the next section
    next_step = (SECTION_KEYS.index(next_section_key) + 1) if next_section_key else None

    if request.auto_approve:
        msg = (
            f"Resuming run {request.run_id} in auto-approve mode "
            f"(step {next_step or '?'}/{total_sections}, "
            f"{sections_done}/{total_sections} sections approved). "
            f"Sections will iterate and approve automatically. "
            f"Poll GET /flow/runs/{request.run_id} for progress."
        )
    else:
        msg = (
            f"Resuming run {request.run_id} from saved state "
            f"(step {next_step or '?'}/{total_sections}, "
            f"{sections_done}/{total_sections} sections approved). "
            f"Poll GET /flow/runs/{request.run_id} for status."
        )

    return PRDResumeResponse(
        run_id=request.run_id,
        flow_name="prd",
        status="running",
        sections_approved=sections_done,
        sections_total=total_sections,
        next_section=next_section_key,
        next_step=next_step,
        message=msg,
    )


# ── Job tracking endpoints ───────────────────────────────────


def _job_doc_to_detail(doc: dict) -> JobDetail:
    """Convert a raw MongoDB job document to a ``JobDetail`` response model."""

    def _iso(val):
        if val is None:
            return None
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    return JobDetail(
        job_id=doc.get("job_id", ""),
        flow_name=doc.get("flow_name", ""),
        idea=doc.get("idea", ""),
        status=doc.get("status", "unknown"),
        error=doc.get("error"),
        queued_at=_iso(doc.get("queued_at")),
        started_at=_iso(doc.get("started_at")),
        completed_at=_iso(doc.get("completed_at")),
        queue_time_ms=doc.get("queue_time_ms"),
        queue_time_human=doc.get("queue_time_human"),
        running_time_ms=doc.get("running_time_ms"),
        running_time_human=doc.get("running_time_human"),
        updated_at=_iso(doc.get("updated_at")),
        output_file=doc.get("output_file"),
        confluence_url=doc.get("confluence_url"),
    )


@router.get(
    "/flow/jobs",
    tags=["Jobs"],
    summary="List all persistent job records",
    response_model=JobListResponse,
    description=(
        "Returns job records from the ``crewJobs`` MongoDB collection. "
        "Each job tracks the full lifecycle of a flow run including "
        "queue time, running time, and terminal status.\n\n"
        "Optional query parameters ``status`` and ``flow_name`` can be "
        "used to filter results."
    ),
    responses={
        200: {"description": "Job list returned successfully."},
        **_ERROR_RESPONSES,
    },
)
async def list_all_jobs(
    status: str | None = None,
    flow_name: str | None = None,
    limit: int = 50,
):
    """List persistent job records, optionally filtered."""
    docs = list_jobs(status=status, flow_name=flow_name, limit=limit)
    items = [_job_doc_to_detail(d) for d in docs]
    return JobListResponse(count=len(items), jobs=items)


@router.get(
    "/flow/jobs/{job_id}",
    tags=["Jobs"],
    summary="Get a single job record",
    response_model=JobDetail,
    description=(
        "Returns a single job record by ``job_id`` from the ``crewJobs`` "
        "collection. Includes lifecycle timestamps and computed durations."
    ),
    responses={
        200: {"description": "Job details returned successfully."},
        404: {"description": "Job not found."},
        **_ERROR_RESPONSES,
    },
)
async def get_job(job_id: str):
    """Fetch a single persistent job record."""
    doc = find_job(job_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_doc_to_detail(doc)
