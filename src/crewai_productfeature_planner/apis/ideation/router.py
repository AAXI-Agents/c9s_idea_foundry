"""REST endpoints for the Ideation Flow API.

Provides the interactive agent chat workflow — a 5-step ideation
flow that refines a raw idea into a structured IdeaSpec ready
for PRD generation.

Endpoints:
    POST   /flow/ideation/kickoff              — start new session
    GET    /flow/ideation/sessions              — list sessions (paginated)
    GET    /flow/ideation/sessions/{id}         — session detail
    GET    /flow/ideation/sessions/{id}/messages — chat history
    POST   /flow/ideation/sessions/{id}/respond — user response
    POST   /flow/ideation/sessions/{id}/iterate — re-iterate current step
    POST   /flow/ideation/sessions/{id}/advance — move to next step
    POST   /flow/ideation/sessions/{id}/rollback — go back
    DELETE /flow/ideation/sessions/{id}         — archive session
    PATCH  /flow/ideation/sessions/{id}         — update metadata
"""

from __future__ import annotations

from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from crewai_productfeature_planner.apis.ideation.models import (
    IdeationAdvanceRequest,
    IdeationAdvanceResponse,
    IdeationDeleteResponse,
    IdeationErrorResponse,
    IdeationIterateRequest,
    IdeationIterateResponse,
    IdeationKickoffRequest,
    IdeationKickoffResponse,
    IdeationMessageItem,
    IdeationMessagesResponse,
    IdeationRespondRequest,
    IdeationRespondResponse,
    IdeationRollbackRequest,
    IdeationRollbackResponse,
    IdeationSessionListResponse,
    IdeationSessionResponse,
    IdeationSessionSummary,
    IdeationUpdateRequest,
    StepOutput,
)
from crewai_productfeature_planner.apis.ideation.service import (
    handle_advance,
    handle_iterate,
    handle_rollback,
    handle_trigger_step,
    handle_user_response,
    start_ideation_session,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
    STEP_ORDER,
    count_sessions,
    get_messages,
    get_session,
    list_sessions_paginated,
    name_to_step,
    step_to_name,
    update_session_metadata,
    update_session_status,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Ideation Flow"])

_ERROR_RESPONSES = {
    404: {"description": "Session not found.", "model": IdeationErrorResponse},
    500: {
        "description": "Internal server error.",
        "model": IdeationErrorResponse,
    },
    503: {
        "description": "LLM service unavailable.",
        "model": IdeationErrorResponse,
    },
}


# ── Serialization helpers ─────────────────────────────────────


def _serialize_session_summary(doc: dict[str, Any]) -> IdeationSessionSummary:
    """Convert a MongoDB session document to the frontend summary shape."""
    return IdeationSessionSummary(
        id=doc.get("session_id", ""),
        title=doc.get("title", "Untitled Idea"),
        status=doc.get("status", "active"),
        current_step=step_to_name(doc.get("current_step", "a")),
        iteration=_session_iteration(doc),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        completed_at=doc.get("completed_at"),
        project_id=doc.get("project_id"),
        prd_run_id=doc.get("prd_run_id"),
    )


def _serialize_session_detail(doc: dict[str, Any]) -> IdeationSessionResponse:
    """Convert a MongoDB session document to the frontend detail shape."""
    outputs: dict[str, StepOutput] = {}
    steps_data = doc.get("steps_data", {})
    current_step = doc.get("current_step", "a")

    for step_letter in STEP_ORDER:
        step_name = step_to_name(step_letter)
        sd = steps_data.get(step_letter, {})

        # Determine step status
        if sd.get("approved"):
            s_status = "completed"
        elif step_letter == current_step:
            s_status = "active"
        else:
            s_status = "pending"

        outputs[step_name] = StepOutput(
            status=s_status,
            iteration=sd.get("iteration", 1),
            started_at=sd.get("started_at"),
            completed_at=sd.get("completed_at"),
        )

    # Detect if the current step needs agent triggering (no cards output).
    # This happens when the auto-trigger on advance fails silently —
    # the frontend should call POST /trigger to recover.
    needs_trigger = False
    if doc.get("status") == "active" and current_step != "a":
        current_sd = steps_data.get(current_step, {})
        if not current_sd.get("output"):
            needs_trigger = True

    return IdeationSessionResponse(
        id=doc.get("session_id", ""),
        title=doc.get("title", "Untitled Idea"),
        status=doc.get("status", "active"),
        current_step=step_to_name(current_step),
        iteration=_session_iteration(doc),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        completed_at=doc.get("completed_at"),
        project_id=doc.get("project_id"),
        prd_run_id=doc.get("prd_run_id"),
        outputs=outputs,
        needs_trigger=needs_trigger,
    )


def _serialize_message(msg: dict[str, Any]) -> IdeationMessageItem:
    """Convert a stored message to the frontend message shape."""
    return IdeationMessageItem(
        id=msg.get("id", ""),
        role=msg.get("role", "system"),
        agent_name=msg.get("agent_name"),
        content=msg.get("content", ""),
        content_type=msg.get("content_type", "text"),
        metadata=msg.get("metadata"),
        flow_step=step_to_name(msg.get("step", "a")),
        created_at=msg.get("timestamp", msg.get("created_at", "")),
    )


def _session_iteration(doc: dict[str, Any]) -> int:
    """Compute the iteration count for the current step."""
    steps_data = doc.get("steps_data", {})
    current_step = doc.get("current_step", "a")
    sd = steps_data.get(current_step, {})
    return sd.get("iteration", 1)


# ── Endpoints ─────────────────────────────────────────────────


@router.post(
    "/flow/ideation/kickoff",
    status_code=201,
    response_model=IdeationKickoffResponse,
    summary="Start a new ideation session",
    description=(
        "Creates a new interactive ideation session. The session walks "
        "through 5 steps: Ideation → Persona → Solution → Goal → Tech Stack. "
        "Each step is powered by a specialist CrewAI agent."
    ),
    responses={201: {"description": "Session created."}, **_ERROR_RESPONSES},
)
async def kickoff_ideation(
    request: IdeationKickoffRequest,
    user: dict = Depends(require_sso_user),
):
    """Start a new ideation session."""
    tenant = TenantContext.from_user(user)
    user_id = user.get("user_id", "")

    logger.info(
        "[IdeationAPI] Kickoff user=%s title=%r project=%s",
        user_id,
        request.title,
        request.project_id,
    )

    session = await start_ideation_session(
        user_id=user_id,
        title=request.title,
        project_id=request.project_id,
        initial_idea=request.idea,
        tenant=tenant,
    )

    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session.")

    return IdeationKickoffResponse(
        session_id=session["session_id"],
        status=session["status"],
        current_step=step_to_name(session["current_step"]),
        message="Ideation session started. The Ideation Agent is analyzing your idea.",
    )


@router.get(
    "/flow/ideation/sessions",
    response_model=IdeationSessionListResponse,
    summary="List ideation sessions (paginated)",
    description="Returns ideation sessions for the authenticated user, newest first.",
    responses=_ERROR_RESPONSES,
)
async def list_ideation_sessions(
    status: str | None = Query(default=None, description="Filter by status"),
    project_id: str | None = Query(default=None, description="Filter by project"),
    search: str | None = Query(default=None, description="Search by title"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    user: dict = Depends(require_sso_user),
):
    """List the user's ideation sessions with pagination."""
    tenant = TenantContext.from_user(user)
    user_id = user.get("user_id", "")

    total = count_sessions(
        user_id=user_id,
        status=status,
        project_id=project_id,
        search=search,
        tenant=tenant,
    )
    total_pages = ceil(total / page_size) if total > 0 else 1

    sessions = list_sessions_paginated(
        user_id=user_id,
        status=status,
        project_id=project_id,
        search=search,
        page=page,
        page_size=page_size,
        tenant=tenant,
    )

    items = [_serialize_session_summary(s) for s in sessions]

    return IdeationSessionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/flow/ideation/sessions/{session_id}",
    response_model=IdeationSessionResponse,
    summary="Get ideation session detail",
    description="Returns full session state including steps data.",
    responses=_ERROR_RESPONSES,
)
async def get_ideation_session(
    session_id: str,
    user: dict = Depends(require_sso_user),
):
    """Get a single ideation session by ID."""
    tenant = TenantContext.from_user(user)
    session = get_session(session_id=session_id, tenant=tenant)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return _serialize_session_detail(session)


@router.get(
    "/flow/ideation/sessions/{session_id}/messages",
    response_model=IdeationMessagesResponse,
    summary="Get session chat messages",
    description="Returns all messages in the session, optionally filtered by step.",
    responses=_ERROR_RESPONSES,
)
async def get_ideation_messages(
    session_id: str,
    step: str | None = Query(default=None, description="Filter by step name"),
    after: str | None = Query(default=None, description="Messages after this timestamp"),
    limit: int = Query(default=100, ge=1, le=500, description="Max messages"),
    user: dict = Depends(require_sso_user),
):
    """Get messages for a session."""
    tenant = TenantContext.from_user(user)

    # Verify session exists
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Convert frontend step name to internal letter if provided
    internal_step = name_to_step(step) if step else None

    messages = get_messages(session_id=session_id, step=internal_step, tenant=tenant)

    # Filter by 'after' timestamp if provided
    if after:
        messages = [
            m for m in messages
            if (m.get("timestamp") or m.get("created_at", "")) > after
        ]

    # Apply limit
    total = len(messages)
    has_more = total > limit
    messages = messages[:limit]

    items = [_serialize_message(m) for m in messages]

    return IdeationMessagesResponse(
        messages=items,
        total=total,
        has_more=has_more,
    )


@router.post(
    "/flow/ideation/sessions/{session_id}/respond",
    response_model=IdeationRespondResponse,
    summary="Send user response",
    description=(
        "Submit a user response to the current agent prompt. "
        "The agent processes the input and returns a response via WebSocket."
    ),
    responses=_ERROR_RESPONSES,
)
async def respond_to_ideation(
    session_id: str,
    request: IdeationRespondRequest,
    user: dict = Depends(require_sso_user),
):
    """Handle user response in the ideation flow."""
    tenant = TenantContext.from_user(user)

    # Verify session exists and is active
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="Session is not active.")

    result = await handle_user_response(
        session_id=session_id,
        content=request.content,
        response_type=request.response_type,
        metadata=request.metadata,
        tenant=tenant,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to process response.")

    return IdeationRespondResponse(
        message_id=result.get("id", ""),
        status="completed",
        content=result.get("content", ""),
        step=result.get("step", ""),
        role=result.get("role", "agent"),
        message="Agent response ready.",
        metadata=result.get("metadata"),
    )


@router.post(
    "/flow/ideation/sessions/{session_id}/iterate",
    response_model=IdeationIterateResponse,
    summary="Re-iterate current step",
    description="Request the agent to re-iterate the current step output with optional feedback.",
    responses=_ERROR_RESPONSES,
)
async def iterate_ideation(
    session_id: str,
    request: IdeationIterateRequest | None = None,
    user: dict = Depends(require_sso_user),
):
    """Re-iterate the current step."""
    tenant = TenantContext.from_user(user)

    # Verify session exists and is active
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="Session is not active.")

    feedback = request.feedback if request else None
    result = await handle_iterate(
        session_id=session_id,
        feedback=feedback,
        tenant=tenant,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to iterate step.")

    step_name = step_to_name(result["step"])
    return IdeationIterateResponse(
        status="iterating",
        iteration=result["iteration"],
        message=f"Re-iterating {step_name} step with your feedback...",
    )


@router.post(
    "/flow/ideation/sessions/{session_id}/advance",
    response_model=IdeationAdvanceResponse,
    summary="Advance to next step",
    description=(
        "Approves the current step output and advances to the next step. "
        "If on the last step, completes the session and triggers PRD generation."
    ),
    responses=_ERROR_RESPONSES,
)
async def advance_ideation(
    session_id: str,
    request: IdeationAdvanceRequest | None = None,
    user: dict = Depends(require_sso_user),
):
    """Advance the ideation session to the next step."""
    tenant = TenantContext.from_user(user)

    # Verify session exists and is active
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="Session is not active.")

    approved_output = request.approved_output if request else None
    result = await handle_advance(
        session_id=session_id,
        approved_output=approved_output,
        tenant=tenant,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    previous_step = step_to_name(result["previous_step"])
    completed = result.get("completed", False)

    if completed:
        return IdeationAdvanceResponse(
            status="completed",
            previous_step=previous_step,
            current_step=None,
            message="All steps complete. PRD generation triggered.",
            prd_run_id=result.get("prd_run_id"),
            prd_status="initializing" if result.get("prd_run_id") else None,
        )

    new_step = step_to_name(result["new_step"])
    return IdeationAdvanceResponse(
        status="advanced",
        previous_step=previous_step,
        current_step=new_step,
        message=f"Advanced to {new_step} step.",
    )


@router.post(
    "/flow/ideation/sessions/{session_id}/trigger",
    response_model=IdeationRespondResponse,
    summary="Trigger agent for current step",
    description=(
        "Recovery endpoint: triggers the agent to generate structured "
        "questions for the current step when the auto-trigger on advance "
        "failed silently. Returns the agent's response via WebSocket and REST."
    ),
    responses=_ERROR_RESPONSES,
)
async def trigger_ideation_step(
    session_id: str,
    user: dict = Depends(require_sso_user),
):
    """Trigger agent for current step (recovery for failed auto-trigger)."""
    tenant = TenantContext.from_user(user)

    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="Session is not active.")

    result = await handle_trigger_step(session_id=session_id, tenant=tenant)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to trigger agent.")

    # If already generated, return a success response
    if result.get("status") == "already_generated":
        return IdeationRespondResponse(
            message_id="",
            status="completed",
            content="Decision cards already generated for this step.",
            step=step_to_name(result.get("step", "")),
            role="agent",
            message="Agent output already exists.",
        )

    metadata = result.get("metadata")
    errored = isinstance(metadata, dict) and metadata.get("error")

    return IdeationRespondResponse(
        message_id=result.get("id", ""),
        status="error" if errored else "completed",
        content=result.get("content", ""),
        step=step_to_name(result.get("step", "")),
        role=result.get("role", "agent"),
        message="Agent encountered an error — retry with /trigger."
        if errored
        else "Agent response ready.",
        metadata=metadata,
    )


@router.post(
    "/flow/ideation/sessions/{session_id}/rollback",
    response_model=IdeationRollbackResponse,
    summary="Roll back to previous step",
    description="Goes back to the previous step, clearing its approval.",
    responses=_ERROR_RESPONSES,
)
async def rollback_ideation(
    session_id: str,
    request: IdeationRollbackRequest | None = None,
    user: dict = Depends(require_sso_user),
):
    """Roll back the ideation session to the previous step."""
    tenant = TenantContext.from_user(user)

    # Verify session exists and is active
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="Session is not active.")

    result = await handle_rollback(session_id=session_id, tenant=tenant)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    new_step = step_to_name(result["new_step"])
    return IdeationRollbackResponse(
        status="rolled_back",
        current_step=new_step,
        iteration=1,
        message=f"Rolled back to {new_step} step.",
    )


@router.delete(
    "/flow/ideation/sessions/{session_id}",
    response_model=IdeationDeleteResponse,
    summary="Archive/delete a session",
    description="Soft-deletes (archives) an ideation session.",
    responses=_ERROR_RESPONSES,
)
async def delete_ideation_session(
    session_id: str,
    user: dict = Depends(require_sso_user),
):
    """Archive (soft-delete) an ideation session."""
    tenant = TenantContext.from_user(user)

    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    success = update_session_status(
        session_id=session_id,
        status="archived",
        tenant=tenant,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to archive session.")

    # Cascade: soft-delete the linked working idea so it disappears from
    # GET /ideas as well.
    prd_run_id = session.get("prd_run_id")
    if prd_run_id:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            mark_deleted,
        )

        mark_deleted(prd_run_id, tenant=tenant)

        from crewai_productfeature_planner.apis._response_cache import response_cache

        response_cache.invalidate("ideas")

    return IdeationDeleteResponse(status="archived", message="Session archived")


@router.patch(
    "/flow/ideation/sessions/{session_id}",
    response_model=IdeationSessionResponse,
    summary="Update session metadata",
    description="Update session title or project association.",
    responses=_ERROR_RESPONSES,
)
async def update_ideation_session(
    session_id: str,
    request: IdeationUpdateRequest,
    user: dict = Depends(require_sso_user),
):
    """Update session metadata (title, project_id)."""
    tenant = TenantContext.from_user(user)

    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    updated = update_session_metadata(
        session_id=session_id,
        title=request.title,
        project_id=request.project_id,
        tenant=tenant,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update session.")

    return _serialize_session_detail(updated)
