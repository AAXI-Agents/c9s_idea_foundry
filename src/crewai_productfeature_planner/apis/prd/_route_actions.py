"""PRD flow action endpoints — kickoff, approve, pause, resume."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.apis.prd.models import (
    ErrorResponse,
    PRDActionResponse,
    PRDApproveRequest,
    PRDKickoffRequest,
    PRDKickoffResponse,
    PRDPauseRequest,
    PRDResumeRequest,
    PRDResumeResponse,
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
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.crew_jobs import (
    create_job,
    find_active_job,
)
from crewai_productfeature_planner.mongodb.project_config import get_project
from crewai_productfeature_planner.mongodb.working_ideas import (
    find_recent_duplicate_idea,
    save_project_ref,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

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

action_router = APIRouter()


@action_router.post(
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
        409: {
            "description": (
                "A job is already active, or a duplicate idea was recently "
                "submitted to the same project (24 h cooldown)."
            ),
        },
        422: {"description": "Validation error."},
        **_ERROR_RESPONSES,
    },
)
async def kickoff_prd_flow(
    request: PRDKickoffRequest, background_tasks: BackgroundTasks,
    user: dict = Depends(require_sso_user),
):
    """Trigger the iterative PRD generation flow."""
    logger.info("[API] PRD kickoff by user_id=%s", user.get("user_id"))

    tenant = TenantContext.from_user(user)

    # Validate project_id exists in projectConfig (if provided)
    if request.project_id:
        project = get_project(request.project_id, tenant=tenant)
        if project is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"project_id '{request.project_id}' does not exist. "
                    "Create the project first via POST /projects/ or provide "
                    "a valid project_id."
                ),
            )

    # Reject duplicate idea submitted to the same project within 24h
    # Also check for active (in-progress) flows with the same idea
    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_active_duplicate_idea,
    )
    active_dup = find_active_duplicate_idea(
        request.idea, project_id=request.project_id or "",
    )
    if active_dup:
        raise HTTPException(
            status_code=409,
            detail=(
                "This idea already has an active flow "
                f"(run_id={active_dup.get('run_id')}, "
                f"status={active_dup.get('status')}). "
                "Resume or archive the existing run first."
            ),
        )
    if request.project_id:
        dup = find_recent_duplicate_idea(request.idea, request.project_id)
        if dup is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Duplicate idea recently submitted to this project "
                    f"(run_id={dup.get('run_id')}, "
                    f"created_at={dup.get('created_at')}). "
                    "Wait 24 hours or use a different idea text."
                ),
            )

    # Enforce single active job — reject if one is already running
    try:
        active = find_active_job()
    except Exception as exc:
        logger.error("[API] Failed to check active jobs: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to check active jobs",
        ) from exc
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
    create_job(job_id=run_id, flow_name="prd", idea=request.idea, tenant=tenant)

    # Link idea to project (if provided)
    if request.project_id:
        save_project_ref(run_id, request.project_id, idea=request.idea, tenant=tenant)

    # Store title in working idea (if provided)
    if request.title:
        try:
            from crewai_productfeature_planner.mongodb.client import get_db
            get_db()["workingIdeas"].update_one(
                {"run_id": run_id},
                {"$set": {"title": request.title}},
                upsert=True,
            )
        except Exception:
            logger.warning("[API] Failed to save title for run_id=%s", run_id, exc_info=True)

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


@action_router.post(
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
async def approve_prd(request: PRDApproveRequest, user: dict = Depends(require_sso_user)):
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


@action_router.post(
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
async def pause_prd(request: PRDPauseRequest, user: dict = Depends(require_sso_user)):
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


@action_router.post(
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
    request: PRDResumeRequest, background_tasks: BackgroundTasks,
    user: dict = Depends(require_sso_user),
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
