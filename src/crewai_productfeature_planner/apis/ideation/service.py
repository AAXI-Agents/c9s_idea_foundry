"""Ideation Flow service layer — orchestrates agent interactions."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from crewai_productfeature_planner.apis.ideation.models import (
    QuestionAnswer,
    StructuredIdeationResponse,
)
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
    STEP_ORDER,
    advance_step,
    append_message,
    complete_session,
    create_session,
    get_messages,
    get_session,
    list_sessions,
    rollback_step,
    save_step_data,
    step_to_name,
    update_session_metadata,
    update_session_status,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Thread pool for running synchronous CrewAI agent calls
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ideation-agent")

# Step → agent role label (maps to CrewAI agent configs)
STEP_AGENTS: dict[str, str] = {
    "a": "product_ideation_specialist",
    "b": "user_research_specialist",
    "c": "solution_architect",
    "d": "goal_strategist",
    "e": "tech_stack_advisor",
}

STEP_PROMPTS: dict[str, str] = {
    "a": (
        "Welcome! I'm your CEO & Product Visionary. "
        "Tell me about your idea — describe the problem you want to solve "
        "and who it's for. I'll help you refine it into a clear executive "
        "summary and mission statement with structured decision cards."
    ),
    "b": (
        "Great idea foundation! Now let's identify your target users. "
        "I'm your Product Manager — User Research Lead. Based on what "
        "we've defined, I'll help you identify key user personas and "
        "segments through structured questions."
    ),
    "c": (
        "Now let's define the solution shape. I'm your Product Manager & "
        "UX Architect. I'll help evaluate form factors, platforms, and UX "
        "paradigms with clear trade-offs for each option."
    ),
    "d": (
        "Let's prioritize what matters most. I'm your CEO & Product Manager — "
        "Goal Strategist. I'll help you define and prioritize feature goals "
        "with MVP scope through structured decision cards."
    ),
    "e": (
        "Final step — technology recommendations. I'm your CTO & Staff "
        "Engineer. I'll recommend the right technology stack with honest "
        "trade-offs on scalability, cost, and time-to-market."
    ),
}


async def start_ideation_session(
    *,
    user_id: str,
    title: str | None = None,
    project_id: str | None = None,
    initial_idea: str | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Create a session and emit the first agent prompt.

    Returns:
        The new session document, or None on failure.
    """
    session = create_session(
        user_id=user_id,
        title=title,
        project_id=project_id,
        tenant=tenant,
    )
    if not session:
        return None

    session_id = session["session_id"]

    # Add initial system message
    append_message(
        session_id=session_id,
        role="system",
        content="Ideation session started.",
        step="a",
        tenant=tenant,
    )

    # Add the agent's opening prompt for step A
    append_message(
        session_id=session_id,
        role="agent",
        content=STEP_PROMPTS["a"],
        step="a",
        tenant=tenant,
    )

    # If user provided an initial idea, record it as user message
    if initial_idea:
        append_message(
            session_id=session_id,
            role="user",
            content=initial_idea,
            step="a",
            tenant=tenant,
        )
        save_step_data(
            session_id=session_id,
            step="a",
            input_data=initial_idea,
            tenant=tenant,
        )
        # Trigger agent processing for the initial idea
        await _run_agent_for_step(
            session_id=session_id,
            step="a",
            user_input=initial_idea,
            tenant=tenant,
        )

    return session


async def handle_user_response(
    *,
    session_id: str,
    content: str,
    response_type: str = "text",
    metadata: dict[str, Any] | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Process a user response and run the agent for the current step.

    For structured answers (``response_type="selection"``), metadata must
    contain an ``answers`` list matching the ``QuestionAnswer`` schema.

    Returns:
        The agent's response message dict, or None on failure.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return None

    if session["status"] != "active":
        logger.warning(
            "[IdeationService] Cannot respond to inactive session=%s status=%s",
            session_id,
            session["status"],
        )
        return None

    current_step = session["current_step"]

    # Build the effective user_input depending on response type
    if response_type == "selection" and metadata and "answers" in metadata:
        # Parse structured answers and format as context for the agent
        answers = [QuestionAnswer(**a) for a in metadata["answers"]]
        user_input = _format_answers_as_context(answers, metadata)
        msg_metadata = {"response_type": "selection", "answers": metadata["answers"]}
    else:
        user_input = content
        msg_metadata = None

    # Save user message (with metadata if structured)
    append_message(
        session_id=session_id,
        role="user",
        content=content,
        step=current_step,
        metadata=msg_metadata,
        tenant=tenant,
    )

    # Save as step input
    save_step_data(
        session_id=session_id,
        step=current_step,
        input_data=user_input,
        tenant=tenant,
    )

    # Run agent
    agent_response = await _run_agent_for_step(
        session_id=session_id,
        step=current_step,
        user_input=user_input,
        session_context=session,
        tenant=tenant,
    )

    return agent_response


async def handle_iterate(
    *,
    session_id: str,
    feedback: str | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Re-iterate the current step with optional feedback.

    Returns:
        Dict with {iteration, step} or None on failure.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return None

    if session["status"] != "active":
        return None

    current_step = session["current_step"]
    steps_data = session.get("steps_data", {})
    step_data = steps_data.get(current_step, {})

    # Compute new iteration (count completed outputs + 1)
    current_iteration = step_data.get("iteration", 1) if "iteration" in step_data else 1
    new_iteration = current_iteration + 1

    # Record feedback as user message if provided
    if feedback:
        append_message(
            session_id=session_id,
            role="user",
            content=f"[Iteration feedback] {feedback}",
            step=current_step,
            tenant=tenant,
        )

    # Insert system message about re-iteration
    append_message(
        session_id=session_id,
        role="system",
        content=f"Re-iterating step with feedback (iteration {new_iteration}).",
        step=current_step,
        tenant=tenant,
    )

    # Re-run the agent with accumulated context + feedback
    user_input = feedback or "Please re-iterate and improve your previous output."
    await _run_agent_for_step(
        session_id=session_id,
        step=current_step,
        user_input=user_input,
        session_context=session,
        tenant=tenant,
    )

    return {
        "iteration": new_iteration,
        "step": current_step,
    }


async def handle_advance(
    *,
    session_id: str,
    feedback: str | None = None,
    approved_output: dict | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    """Advance the session to the next step.

    Returns:
        Dict with advance info: {previous_step, new_step, completed}.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return {"error": "Session not found"}

    current_step = session["current_step"]

    # If feedback provided, record it
    if feedback:
        append_message(
            session_id=session_id,
            role="user",
            content=f"[Feedback before advancing] {feedback}",
            step=current_step,
            tenant=tenant,
        )

    # Advance
    new_step = advance_step(session_id=session_id, tenant=tenant)

    if new_step is None:
        # Session completed (was on last step) — auto-trigger PRD
        prd_run_id = await trigger_prd_from_ideation(
            session_id=session_id, tenant=tenant
        )
        return {
            "previous_step": current_step,
            "new_step": None,
            "completed": True,
            "prd_run_id": prd_run_id,
        }

    # Emit the agent's opening prompt for the new step
    append_message(
        session_id=session_id,
        role="agent",
        content=STEP_PROMPTS[new_step],
        step=new_step,
        tenant=tenant,
    )

    return {
        "previous_step": current_step,
        "new_step": new_step,
        "completed": False,
    }


async def handle_rollback(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    """Roll back to the previous step.

    Returns:
        Dict with rollback info: {previous_step, new_step} or {error}.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return {"error": "Session not found"}

    current_step = session["current_step"]
    new_step = rollback_step(session_id=session_id, tenant=tenant)

    if new_step is None:
        return {"error": "Already at first step — cannot roll back."}

    # Add system message about rollback
    append_message(
        session_id=session_id,
        role="system",
        content=f"Rolled back from step {current_step} to step {new_step}.",
        step=new_step,
        tenant=tenant,
    )

    return {
        "previous_step": current_step,
        "new_step": new_step,
    }


async def _run_agent_for_step(
    *,
    session_id: str,
    step: str,
    user_input: str,
    session_context: dict[str, Any] | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Run the CrewAI agent for the given step and record the response.

    Executes the synchronous CrewAI crew in a thread pool to avoid
    blocking the async event loop.  When the agent returns a
    ``StructuredIdeationResponse``, the message is stored with
    ``render_type="structured_questions"`` metadata so the frontend
    can render decision cards.
    """
    from crewai_productfeature_planner.agents.ideation import run_ideation_step

    # Build context from previous steps
    context = _build_step_context(session_context, step) if session_context else {}

    # Build conversation history for multi-turn awareness within this step
    conversation_history = _build_conversation_history(session_id, step, tenant)

    # Broadcast typing indicator via WebSocket
    _broadcast_typing(session_id, step)

    # Run the agent in a thread pool (CrewAI is synchronous)
    loop = asyncio.get_event_loop()
    try:
        agent_output = await loop.run_in_executor(
            _executor,
            lambda: run_ideation_step(
                step=step,
                user_input=user_input,
                context=context,
                conversation_history=conversation_history,
            ),
        )
    except Exception as exc:
        logger.error(
            "[IdeationService] Agent failed session=%s step=%s: %s",
            session_id,
            step,
            exc,
            exc_info=True,
        )
        agent_output = (
            "I encountered an issue processing your input. "
            "Could you try rephrasing or providing more detail?"
        )

    # Determine content text and metadata based on output type
    if isinstance(agent_output, StructuredIdeationResponse):
        content_text = agent_output.acknowledgment
        msg_metadata = {
            "render_type": "structured_questions",
            "structured": agent_output.model_dump(),
        }
        output_data = agent_output.model_dump()
    else:
        content_text = str(agent_output)
        msg_metadata = None
        output_data = content_text

    # Save agent response as message (with metadata for structured output)
    msg_id = append_message(
        session_id=session_id,
        role="agent",
        content=content_text,
        step=step,
        metadata=msg_metadata,
        tenant=tenant,
    )

    # Save step output
    save_step_data(
        session_id=session_id,
        step=step,
        output_data=output_data,
        tenant=tenant,
    )

    # Broadcast the agent message via WebSocket
    _broadcast_message(session_id, msg_id, content_text, step, msg_metadata)

    return {
        "id": msg_id,
        "role": "agent",
        "content": content_text,
        "step": step,
        "metadata": msg_metadata,
    }


def _build_step_context(session: dict[str, Any], current_step: str) -> dict[str, Any]:
    """Build context from completed previous steps."""
    context: dict[str, Any] = {}
    steps_data = session.get("steps_data", {})

    for step in STEP_ORDER:
        if step == current_step:
            break
        step_data = steps_data.get(step, {})
        if step_data.get("approved") and step_data.get("output"):
            context[step] = step_data["output"]

    return context


def _build_conversation_history(
    session_id: str,
    step: str,
    tenant: TenantContext | None = None,
) -> list[dict[str, str]]:
    """Fetch prior user/agent messages for the current step.

    Returns a list of {role, content} dicts representing the conversation
    so far within this step, excluding system messages.  Limited to the
    last 10 messages to keep the prompt within token budget.
    """
    messages = get_messages(session_id=session_id, step=step, tenant=tenant)
    # Filter to user and agent messages only (skip system)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "agent") and m.get("content")
    ]
    # Keep last 10 messages to avoid token overflow
    return history[-10:]


def _step_label(step: str) -> str:
    """Human-readable step label."""
    labels = {
        "a": "Ideation",
        "b": "Persona",
        "c": "Solution",
        "d": "Primary Goal",
        "e": "Technical Stack",
    }
    return labels.get(step, step)


def _broadcast_typing(session_id: str, step: str) -> None:
    """Broadcast a typing indicator via WebSocket (fire-and-forget)."""
    try:
        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            broadcast_sync,
        )
        from datetime import datetime, timezone

        broadcast_sync(session_id, {
            "type": "agent_typing",
            "session_id": session_id,
            "step": step,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass  # WebSocket broadcast is best-effort


def _broadcast_message(
    session_id: str,
    msg_id: str | None,
    content: str,
    step: str,
    metadata: dict | None = None,
) -> None:
    """Broadcast a complete agent message via WebSocket (fire-and-forget)."""
    try:
        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            broadcast_sync,
        )
        from datetime import datetime, timezone

        payload: dict[str, Any] = {
            "type": "agent_message",
            "session_id": session_id,
            "id": msg_id,
            "role": "agent",
            "content": content,
            "step": step,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            payload["metadata"] = metadata
        broadcast_sync(session_id, payload)
    except Exception:
        pass


def _format_answers_as_context(
    answers: list[QuestionAnswer],
    metadata: dict[str, Any],
) -> str:
    """Convert structured answers into a context string for the agent.

    Produces a readable summary of what the user selected (or typed)
    for each question, so the agent can build on the decisions.
    """
    # Try to find the original questions from the metadata to enrich context
    original_questions = metadata.get("original_questions", [])
    q_map: dict[int, dict] = {}
    for q in original_questions:
        q_map[q.get("id", 0)] = q

    parts: list[str] = []
    for ans in answers:
        q_info = q_map.get(ans.question_id)
        q_text = q_info["question"] if q_info else f"Question {ans.question_id}"

        if ans.custom_feedback:
            parts.append(f"Q{ans.question_id}: {q_text}\n  → Custom: {ans.custom_feedback}")
        elif ans.selected_option is not None:
            # Try to get the recommendation label
            label = f"Option {ans.selected_option + 1}"
            if q_info and "recommendations" in q_info:
                recs = q_info["recommendations"]
                if 0 <= ans.selected_option < len(recs):
                    label = recs[ans.selected_option].get("label", label)
            parts.append(f"Q{ans.question_id}: {q_text}\n  → Selected: {label}")
        else:
            parts.append(f"Q{ans.question_id}: {q_text}\n  → (no answer)")

    return "User's decisions:\n" + "\n".join(parts)


async def trigger_prd_from_ideation(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> str | None:
    """Auto-trigger PRD generation after ideation completes.

    Builds a structured idea from all 5 step outputs and kicks off
    the existing PRD flow.

    Returns:
        The PRD run_id on success, or None on failure.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        logger.error("[IdeationService] Cannot trigger PRD — session not found: %s", session_id)
        return None

    steps_data = session.get("steps_data", {})

    # Build structured idea text from all step outputs
    idea_parts: list[str] = []
    labels = {
        "a": "Executive Summary & Mission",
        "b": "User Personas",
        "c": "Solution Architecture",
        "d": "Feature Goals",
        "e": "Technology Stack",
    }
    for step_key in STEP_ORDER:
        step_output = steps_data.get(step_key, {}).get("output")
        if step_output:
            idea_parts.append(f"## {labels[step_key]}\n{step_output}")

    structured_idea = "\n\n".join(idea_parts)

    # Use the session title as the idea title
    title = session.get("title", "Untitled Idea")

    logger.info(
        "[IdeationService] Triggering PRD for session=%s title=%r idea_len=%d",
        session_id,
        title,
        len(structured_idea),
    )

    # Kick off the PRD flow using the existing service
    try:
        import uuid
        from crewai_productfeature_planner.apis.prd.service import run_prd_flow

        run_id = uuid.uuid4().hex

        # Import needed functions for job creation
        from crewai_productfeature_planner.mongodb.crew_jobs import create_job
        from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs

        # Create the job record
        create_job(job_id=run_id, idea=f"[Ideation: {title}] {structured_idea[:500]}")

        # Create in-memory flow run
        flow_run = FlowRun(run_id=run_id, idea=structured_idea, status=FlowStatus.QUEUED)
        runs[run_id] = flow_run

        # Run in background
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            _executor,
            lambda: run_prd_flow(
                run_id=run_id,
                idea=structured_idea,
                auto_approve=True,
            ),
        )

        logger.info(
            "[IdeationService] PRD flow triggered run_id=%s from session=%s",
            run_id,
            session_id,
        )
        return run_id

    except Exception as exc:
        logger.error(
            "[IdeationService] Failed to trigger PRD for session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return None
