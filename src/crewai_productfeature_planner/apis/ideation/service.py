"""Ideation Flow service layer — orchestrates agent interactions."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from crewai_productfeature_planner.apis.ideation.models import (
    ProcessingPhase,
    QuestionAnswer,
    StructuredIdeationResponse,
)
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
    STEP_ORDER,
    advance_step,
    append_message,
    clear_step_output,
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

# Strong references to background tasks to prevent garbage collection.
# Tasks are removed via a done-callback once they finish.
_background_tasks: dict[str, asyncio.Task] = {}

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


async def handle_trigger_step(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Trigger agent for the current step if it has no cards output yet.

    This is a recovery mechanism for when the auto-trigger on advance
    fails silently.  The frontend detects a step with no agent cards
    and calls this endpoint to re-trigger.

    Returns:
        The agent's response dict, or None on failure.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return None

    if session["status"] != "active":
        logger.warning(
            "[IdeationService] Cannot trigger agent on inactive session=%s",
            session_id,
        )
        return None

    current_step = session["current_step"]

    # Check if this step already has cards output
    steps_data = session.get("steps_data", {})
    step_data = steps_data.get(current_step, {})

    if step_data.get("output") and isinstance(step_data["output"], dict):
        # Already has structured output — skip
        logger.info(
            "[IdeationService] Step already has output session=%s step=%s",
            session_id,
            current_step,
        )
        return {
            "status": "already_generated",
            "step": current_step,
        }

    # If there's a previous error string output, clear it before retrying
    # so the step gets a clean slate.
    if step_data.get("output") and isinstance(step_data["output"], str):
        logger.info(
            "[IdeationService] Clearing previous error output session=%s step=%s",
            session_id,
            current_step,
        )
        clear_step_output(
            session_id=session_id,
            step=current_step,
            tenant=tenant,
        )

    logger.info(
        "[IdeationService] Manual trigger for session=%s step=%s",
        session_id,
        current_step,
    )

    # Trigger the agent for this step
    result = await _run_agent_for_step(
        session_id=session_id,
        step=current_step,
        user_input=(
            "Analyze the context from previous steps and generate "
            "your initial set of structured questions for this step."
        ),
        session_context=session,
        tenant=tenant,
    )

    return result

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
        # Session completed (was on last step) — auto-create Idea + trigger PRD
        idea_doc = _auto_create_idea_from_session(
            session_id=session_id, tenant=tenant
        )
        prd_run_id = await trigger_prd_from_ideation(
            session_id=session_id, tenant=tenant
        )
        result: dict[str, Any] = {
            "previous_step": current_step,
            "new_step": None,
            "completed": True,
            "prd_run_id": prd_run_id,
        }
        if idea_doc:
            result["idea_id"] = idea_doc["idea_id"]
        return result

    # Emit the agent's opening prompt for the new step
    append_message(
        session_id=session_id,
        role="agent",
        content=STEP_PROMPTS[new_step],
        step=new_step,
        tenant=tenant,
    )

    # Auto-trigger the agent for the new step so structured questions
    # are generated immediately (background task with strong reference).
    # Re-read the session to pick up the approved previous step output.
    updated_session = get_session(session_id=session_id, tenant=tenant)

    async def _auto_trigger_agent() -> None:
        try:
            logger.info(
                "[IdeationService] Auto-trigger starting session=%s step=%s",
                session_id,
                new_step,
            )
            await _run_agent_for_step(
                session_id=session_id,
                step=new_step,
                user_input=(
                    "Analyze the context from previous steps and generate "
                    "your initial set of structured questions for this step."
                ),
                session_context=updated_session,
                tenant=tenant,
            )
            logger.info(
                "[IdeationService] Auto-trigger completed session=%s step=%s",
                session_id,
                new_step,
            )
        except Exception as exc:
            logger.error(
                "[IdeationService] Auto-trigger failed session=%s step=%s: %s",
                session_id,
                new_step,
                exc,
                exc_info=True,
            )

    task_key = f"{session_id}:{new_step}"

    def _on_task_done(t: asyncio.Task) -> None:
        _background_tasks.pop(task_key, None)
        if t.cancelled():
            logger.warning(
                "[IdeationService] Auto-trigger cancelled session=%s step=%s",
                session_id, new_step,
            )
        elif t.exception():
            logger.error(
                "[IdeationService] Auto-trigger exception session=%s step=%s: %s",
                session_id, new_step, t.exception(),
                exc_info=True,
            )

    task = asyncio.create_task(
        _auto_trigger_agent(),
        name=f"ideation-auto-{session_id[:8]}-{new_step}",
    )
    task.add_done_callback(_on_task_done)
    _background_tasks[task_key] = task

    logger.info(
        "[IdeationService] Auto-triggered agent for session=%s step=%s",
        session_id,
        new_step,
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
    from crewai_productfeature_planner.apis.ideation._streaming import (
        streaming_session,
    )

    # Build context from previous steps
    context = _build_step_context(session_context, step) if session_context else {}

    # Build conversation history for multi-turn awareness within this step
    conversation_history = _build_conversation_history(session_id, step, tenant)

    # Broadcast typing indicator via WebSocket
    _broadcast_typing(session_id, step)

    # Phase 1: analyzing responses (context + history built above)
    _broadcast_processing_status(
        session_id, ProcessingPhase.ANALYZING_RESPONSES, step, 0.1,
    )

    # Phase 2: agent reviewing — start progress ticker during LLM call
    _broadcast_processing_status(
        session_id, ProcessingPhase.AGENT_REVIEWING, step, 0.2,
    )

    ticker = _ProgressTicker(session_id, step)
    ticker.start()

    # Run the agent in a thread pool (CrewAI is synchronous).
    # The streaming_session context manager sets thread-local state so the
    # global LLMStreamChunkEvent handler can route tokens to this session's WS.
    loop = asyncio.get_event_loop()
    agent_errored = False

    def _run_agent_in_thread() -> str | StructuredIdeationResponse:
        with streaming_session(session_id, step):
            return run_ideation_step(
                step=step,
                user_input=user_input,
                context=context,
                conversation_history=conversation_history,
            )

    try:
        agent_output = await loop.run_in_executor(
            _executor,
            _run_agent_in_thread,
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
        agent_errored = True
    finally:
        ticker.stop()

    # Phase 3: preparing questions (post-processing)
    _broadcast_processing_status(
        session_id, ProcessingPhase.PREPARING_QUESTIONS, step, 0.9,
    )

    # Determine content text and metadata based on output type
    is_structured = isinstance(agent_output, StructuredIdeationResponse)
    if is_structured:
        content_text = agent_output.acknowledgment
        msg_metadata = {
            "render_type": "structured_questions",
            "can_iterate": True,
            "can_advance": False,
            "structured": agent_output.model_dump(),
        }
        output_data = agent_output.model_dump()
    else:
        content_text = str(agent_output)
        msg_metadata = None
        output_data = content_text

    content_type = "cards" if is_structured else "markdown"
    agent_name = STEP_AGENTS.get(step, "ideation_agent")

    # Save agent response as message (with metadata for structured output)
    if agent_errored:
        msg_metadata = msg_metadata or {}
        msg_metadata["error"] = True
    msg_id = append_message(
        session_id=session_id,
        role="agent",
        content=content_text,
        step=step,
        metadata=msg_metadata,
        agent_name=agent_name,
        content_type=content_type,
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
    # First, send a final agent_token event to signal end of streaming
    _broadcast_agent_token_final(session_id, step)
    _broadcast_message(session_id, msg_id, content_text, step, msg_metadata,
                       agent_name=agent_name, content_type=content_type)

    # If the agent errored, also broadcast an explicit error event so
    # frontends can show appropriate UI (retry button, etc.)
    if agent_errored:
        try:
            from crewai_productfeature_planner.apis.ideation._route_websocket import (
                broadcast_sync,
            )
            from datetime import datetime, timezone

            broadcast_sync(session_id, {
                "event": "error",
                "data": {
                    "code": "AGENT_ERROR",
                    "message": "The AI agent encountered an error. You can retry your message.",
                    "recoverable": True,
                    "step": step,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            })
        except Exception as exc:
            logger.warning(
                "[IdeationService] Failed to broadcast error event session=%s: %s",
                session_id, exc,
            )

    return {
        "id": msg_id,
        "role": "agent",
        "content": content_text,
        "step": step,
        "metadata": msg_metadata,
    }


def _build_step_context(session: dict[str, Any], current_step: str) -> dict[str, Any]:
    """Build context from completed previous steps.

    Extracts readable text from step outputs, handling both plain-string
    and structured-dict (``StructuredIdeationResponse.model_dump()``)
    formats so the LLM receives clean prose instead of raw dicts.
    """
    context: dict[str, Any] = {}
    steps_data = session.get("steps_data", {})

    for step in STEP_ORDER:
        if step == current_step:
            break
        step_data = steps_data.get(step, {})
        if step_data.get("approved") and step_data.get("output"):
            context[step] = _extract_readable_output(step_data["output"])

    return context


def _extract_readable_output(output: Any) -> str:
    """Convert a step output (dict or str) into readable text for context.

    When the output is a ``StructuredIdeationResponse.model_dump()`` dict,
    extracts the acknowledgment, user decisions from questions, and any
    summary draft into a coherent text block.
    """
    if isinstance(output, str):
        return output

    if not isinstance(output, dict):
        return str(output)

    parts: list[str] = []

    # Extract acknowledgment / summary
    if output.get("acknowledgment"):
        parts.append(output["acknowledgment"])
    if output.get("summary_draft"):
        parts.append(f"Summary: {output['summary_draft']}")
    if output.get("agent_insight"):
        parts.append(f"Insight: {output['agent_insight']}")

    # Extract questions and selected recommendations
    questions = output.get("questions", [])
    for q in questions:
        q_text = q.get("question", "")
        recs = q.get("recommendations", [])
        rec_idx = q.get("recommended_index")
        # Show recommended option if available
        if rec_idx is not None and 0 <= rec_idx < len(recs):
            rec = recs[rec_idx]
            parts.append(
                f"- {q_text}: Recommended \"{rec.get('label', '')}\" — "
                f"Pro: {rec.get('pro', '')}; Con: {rec.get('con', '')}"
            )
        elif recs:
            # Show all options briefly
            opts = ", ".join(r.get("label", "") for r in recs)
            parts.append(f"- {q_text}: Options — {opts}")
        else:
            parts.append(f"- {q_text}")

    return "\n".join(parts) if parts else str(output)


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

        broadcast_sync(session_id, {
            "event": "agent_typing",
            "data": {
                "agent_name": "ideation_agent",
                "step": step_to_name(step),
            },
        })
    except Exception as exc:
        logger.warning(
            "[IdeationService] Failed to broadcast typing session=%s: %s",
            session_id, exc,
        )


def _broadcast_agent_token_final(session_id: str, step: str) -> None:
    """Broadcast a final ``agent_token`` event to signal end of streaming."""
    try:
        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            broadcast_sync,
        )

        broadcast_sync(session_id, {
            "event": "agent_token",
            "data": {
                "message_id": f"streaming-{session_id[:8]}",
                "token": "",
                "is_final": True,
                "step": step_to_name(step),
            },
        })
    except Exception as exc:
        logger.warning(
            "[IdeationService] Failed to broadcast final token session=%s: %s",
            session_id, exc,
        )


def _broadcast_processing_status(
    session_id: str,
    phase: ProcessingPhase,
    step: str,
    progress: float,
) -> None:
    """Broadcast a ``processing_status`` event via WebSocket."""
    try:
        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            broadcast_sync,
        )

        label_map = {
            ProcessingPhase.ANALYZING_RESPONSES: "Analyzing your responses…",
            ProcessingPhase.AGENT_REVIEWING: "Agent is reviewing…",
            ProcessingPhase.PREPARING_QUESTIONS: "Preparing next questions…",
        }
        broadcast_sync(session_id, {
            "event": "processing_status",
            "data": {
                "phase": phase.value,
                "step": step_to_name(step),
                "progress": round(min(progress, 1.0), 2),
                "label": label_map.get(phase, phase.value),
            },
        })
    except Exception as exc:
        logger.warning(
            "[IdeationService] Failed to broadcast processing_status session=%s: %s",
            session_id, exc,
        )


class _ProgressTicker:
    """Emits incremental ``processing_status`` events while the LLM runs.

    Start with :meth:`start` before the executor call, stop with
    :meth:`stop` after it returns.  The ticker emits
    ``agent_reviewing`` events with increasing progress (0.25 → 0.8)
    every *interval* seconds from a background thread.
    """

    def __init__(
        self,
        session_id: str,
        step: str,
        interval: float = 3.0,
    ) -> None:
        self._session_id = session_id
        self._step = step
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"progress-{self._session_id[:8]}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self) -> None:
        progress = 0.25
        while not self._stop_event.wait(self._interval):
            progress = min(progress + 0.05, 0.8)
            _broadcast_processing_status(
                self._session_id,
                ProcessingPhase.AGENT_REVIEWING,
                self._step,
                progress,
            )


def _broadcast_message(
    session_id: str,
    msg_id: str | None,
    content: str,
    step: str,
    metadata: dict | None = None,
    *,
    agent_name: str = "ideation_agent",
    content_type: str = "markdown",
) -> None:
    """Broadcast a complete agent message via WebSocket (fire-and-forget)."""
    try:
        from crewai_productfeature_planner.apis.ideation._route_websocket import (
            broadcast_sync,
        )
        from datetime import datetime, timezone

        broadcast_sync(session_id, {
            "event": "new_message",
            "data": {
                "id": msg_id,
                "role": "agent",
                "agent_name": agent_name,
                "content": content,
                "content_type": content_type,
                "metadata": metadata,
                "flow_step": step_to_name(step),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        })
    except Exception as exc:
        logger.warning(
            "[IdeationService] Failed to broadcast message session=%s: %s",
            session_id, exc,
        )


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

        # Run in background with error tracking
        loop = asyncio.get_event_loop()

        def _run_prd_with_error_handling() -> None:
            """Wrapper that catches errors and broadcasts them back."""
            try:
                run_prd_flow(
                    run_id=run_id,
                    idea=structured_idea,
                    auto_approve=True,
                )
            except Exception as exc:
                logger.error(
                    "[IdeationService] PRD flow failed run_id=%s session=%s: %s",
                    run_id, session_id, exc, exc_info=True,
                )
                # Broadcast error back to the session WebSocket
                try:
                    from crewai_productfeature_planner.apis.ideation._route_websocket import (
                        broadcast_sync,
                    )
                    broadcast_sync(session_id, {
                        "event": "error",
                        "data": {
                            "code": "PRD_GENERATION_FAILED",
                            "message": "PRD generation failed. You can retry from the session.",
                            "recoverable": True,
                            "prd_run_id": run_id,
                        },
                    })
                except Exception:
                    pass  # Best effort — WS may already be closed

        loop.run_in_executor(_executor, _run_prd_with_error_handling)

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


def _auto_create_idea_from_session(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Auto-create an Idea document when an ideation session completes.

    Extracts title, project_id, and description from the session and
    creates a new Idea in ``draft`` status linked to the session.

    Returns:
        The created idea document, or ``None`` on failure.
    """
    from crewai_productfeature_planner.mongodb.ideas.repository import (
        create_idea as ideas_create,
    )

    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        logger.warning(
            "[IdeationService] Cannot auto-create idea — session not found: %s",
            session_id,
        )
        return None

    # Build description from step outputs
    steps_data = session.get("steps_data", {})
    description_parts: list[str] = []
    labels = {
        "a": "Executive Summary & Mission",
        "b": "User Personas",
        "c": "Solution Architecture",
        "d": "Feature Goals",
        "e": "Technology Stack",
    }
    for step_key in STEP_ORDER:
        output = steps_data.get(step_key, {}).get("output")
        if output:
            if isinstance(output, dict):
                # Structured output — extract text summary
                text = output.get("acknowledgment") or output.get("summary") or str(output)
            else:
                text = str(output)
            description_parts.append(f"## {labels[step_key]}\n{text}")

    description = "\n\n".join(description_parts) if description_parts else ""

    idea_doc = ideas_create(
        project_id=session.get("project_id") or "",
        title=session.get("title") or "Untitled Idea",
        description=description,
        created_by=session.get("user_id") or "",
        ideation_session_id=session_id,
        tenant=tenant,
    )

    if idea_doc:
        logger.info(
            "[IdeationService] Auto-created idea=%s from session=%s",
            idea_doc["idea_id"],
            session_id,
        )
    else:
        logger.error(
            "[IdeationService] Failed to auto-create idea from session=%s",
            session_id,
        )

    return idea_doc
