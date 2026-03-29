"""Engagement Manager agent factory, PRD orchestrator, and runner.

Creates an agent that:
1. Handles unknown or ambiguous user intents (navigation guide)
2. Orchestrates the full idea-to-PRD lifecycle (PRD orchestrator)
3. Provides continuous heartbeat updates during processing
4. Detects and incorporates user steering during active flows
5. Enforces session isolation (initiator-only engagement)

Uses the base Gemini model (``GEMINI_MODEL``) since this is a
lightweight routing/conversational task, not a deep-reasoning one.

Environment variables:

* ``ENGAGEMENT_MANAGER_MODEL`` — override the Gemini model used
  (defaults to ``GEMINI_MODEL`` → ``DEFAULT_GEMINI_MODEL``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

import yaml
from crewai import Agent, Crew, Process, Task, LLM

from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

# LLM defaults — basic tier for conversational routing
DEFAULT_LLM_TIMEOUT = 120
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config from the engagement manager's config directory."""
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_engagement_llm() -> LLM:
    """Build the Gemini LLM for the engagement manager agent.

    Uses the **basic** model tier because this is a lightweight
    conversational routing task — no deep reasoning required.

    Resolution order for model name:
        1. ``ENGAGEMENT_MANAGER_MODEL`` env var
        2. ``GEMINI_MODEL`` env var
        3. Hard-coded default (``DEFAULT_GEMINI_MODEL``)
    """
    from crewai_productfeature_planner.agents.gemini_utils import (
        DEFAULT_GEMINI_MODEL,
        ensure_gemini_env,
    )

    ensure_gemini_env()

    model_name = os.environ.get(
        "ENGAGEMENT_MANAGER_MODEL",
        os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    ).strip()
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info(
        "Engagement Manager LLM: %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def _build_project_tools(project_id: str | None) -> tuple[list, str]:
    """Build file-reading tools scoped to a project's knowledge base.

    Returns:
        A tuple of (tools_list, ideas_context_str).
        When *project_id* is ``None`` or the project has no knowledge
        folder, returns ``([], "")``.
    """
    if not project_id:
        return [], ""

    from crewai_productfeature_planner.scripts.project_knowledge import (
        _PROJECTS_ROOT,
        _safe_dirname,
        load_completed_ideas_context,
    )
    from crewai_productfeature_planner.tools.file_read_tool import (
        create_file_read_tool,
    )
    from crewai_productfeature_planner.tools.directory_read_tool import (
        create_directory_read_tool,
    )

    ideas_context = ""
    tools: list = []

    try:
        # Try to resolve the project name for the directory
        from crewai_productfeature_planner.mongodb.project_config import (
            get_project,
        )
        config = get_project(project_id)
        if config:
            dirname = _safe_dirname(config.get("name", ""))
            project_dir = _PROJECTS_ROOT / dirname
            if project_dir.is_dir():
                tools = [
                    create_file_read_tool(),
                    create_directory_read_tool(str(project_dir)),
                ]
                logger.info(
                    "[EngagementManager] Project tools enabled for '%s' (%s)",
                    dirname, project_dir,
                )
    except Exception:
        logger.debug(
            "[EngagementManager] Could not build project tools for %s",
            project_id, exc_info=True,
        )

    try:
        ideas_context = load_completed_ideas_context(project_id)
    except Exception:
        logger.debug(
            "[EngagementManager] Could not load ideas context for %s",
            project_id, exc_info=True,
        )

    return tools, ideas_context


def create_engagement_manager(
    project_id: str | None = None,
) -> Agent:
    """Create the Engagement Manager agent powered by Google Gemini.

    When *project_id* is provided the agent receives file-reading tools
    scoped to the project's knowledge folder and completed-ideas
    context is appended to its backstory, enabling it to answer
    questions about existing ideas holistically.

    Raises ``EnvironmentError`` when neither ``GOOGLE_API_KEY`` nor
    ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT is required "
            "to create the Engagement Manager agent."
        )

    agent_config = _load_yaml("agent.yaml")["engagement_manager"]
    logger.info(
        "Creating Engagement Manager agent (role='%s', project_id=%s)",
        agent_config["role"].strip(),
        project_id or "(none)",
    )

    tools, ideas_context = _build_project_tools(project_id)
    backstory = agent_config["backstory"].strip()
    if ideas_context:
        backstory = f"{backstory}\n\n{ideas_context}"

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_engagement_llm(),
        tools=tools,
        verbose=is_verbose(),
        allow_delegation=False,
        respect_context_window=True,
        max_iter=8,
    )


def handle_unknown_intent(
    user_message: str,
    conversation_history: list[dict] | None = None,
    active_context: str = "",
    project_id: str | None = None,
) -> str:
    """Run the engagement manager to produce a helpful response.

    Uses a **direct Gemini REST API call** to avoid CrewAI framework
    overhead (~2-4 s).  Falls back to CrewAI ``Crew.kickoff()`` when
    ``ENGAGEMENT_MANAGER_USE_CREWAI=true`` or when the fast path fails.

    Args:
        user_message: The user's raw message text.
        conversation_history: Optional list of prior messages in the thread.
        active_context: Description of the user's current state
            (active project, running flows, etc.).
        project_id: Optional project ID to enable project-knowledge
            tools and completed-ideas context.

    Returns:
        The agent's response text — a concise navigation guide.
    """
    use_crewai = os.environ.get(
        "ENGAGEMENT_MANAGER_USE_CREWAI", ""
    ).strip().lower() in ("true", "1", "yes")

    if not use_crewai:
        result = _handle_unknown_intent_fast(
            user_message, conversation_history, active_context, project_id,
        )
        if result is not None:
            return result
        logger.warning(
            "[EngagementManager] Fast path failed — falling back to CrewAI",
        )

    return _handle_unknown_intent_crewai(
        user_message, conversation_history, active_context, project_id,
    )


def _handle_unknown_intent_fast(
    user_message: str,
    conversation_history: list[dict] | None,
    active_context: str,
    project_id: str | None,
) -> str | None:
    """Fast path: direct Gemini REST API call (~200-800 ms)."""
    from crewai_productfeature_planner.tools.gemini_chat import (
        generate_chat_response,
    )

    agent_config = _load_yaml("agent.yaml")["engagement_manager"]
    task_configs = _load_yaml("tasks.yaml")

    # Build project knowledge
    project_knowledge = "(no project selected — no ideas context available)"
    if project_id:
        try:
            from crewai_productfeature_planner.scripts.project_knowledge import (
                load_completed_ideas_context,
            )
            ctx = load_completed_ideas_context(project_id)
            if ctx:
                project_knowledge = ctx
        except Exception:
            logger.debug(
                "[EngagementManager] Could not load ideas context",
                exc_info=True,
            )

    history_str = ""
    if conversation_history:
        history_str = json.dumps(conversation_history[-10:], ensure_ascii=False)
    if not history_str:
        history_str = "(no prior conversation)"
    if not active_context:
        active_context = "(no active context available)"

    system_prompt = (
        f"Role: {agent_config['role'].strip()}\n"
        f"Goal: {agent_config['goal'].strip()}\n\n"
        f"{agent_config['backstory'].strip()}"
    )

    task_description = task_configs["engagement_response_task"]["description"].format(
        user_message=user_message,
        conversation_history=history_str,
        active_context=active_context,
        project_knowledge=project_knowledge,
    )
    expected_output = task_configs["engagement_response_task"]["expected_output"]
    user_prompt = f"{task_description}\n\n## Expected Output\n{expected_output}"

    model = os.environ.get(
        "ENGAGEMENT_MANAGER_MODEL",
        os.environ.get("GEMINI_MODEL", ""),
    ).strip() or None

    logger.info(
        "[EngagementManager] Fast path for message: '%s'",
        user_message[:80],
    )

    response = generate_chat_response(
        system_prompt=system_prompt,
        user_message=user_prompt,
        conversation_history=conversation_history,
        model_override=model,
    )

    if response:
        logger.info(
            "[EngagementManager] Fast response (%d chars): '%s'",
            len(response), response[:200],
        )
    return response


def _handle_unknown_intent_crewai(
    user_message: str,
    conversation_history: list[dict] | None,
    active_context: str,
    project_id: str | None,
) -> str:
    """Slow path: CrewAI Crew.kickoff() (~3-5 s)."""
    from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

    task_configs = _load_yaml("tasks.yaml")
    agent = create_engagement_manager(project_id=project_id)

    history_str = ""
    if conversation_history:
        history_str = json.dumps(conversation_history[-10:], ensure_ascii=False)
    if not history_str:
        history_str = "(no prior conversation)"

    if not active_context:
        active_context = "(no active context available)"

    # Build project knowledge summary for the task prompt
    project_knowledge = "(no project selected — no ideas context available)"
    if project_id:
        try:
            from crewai_productfeature_planner.scripts.project_knowledge import (
                load_completed_ideas_context,
            )
            ctx = load_completed_ideas_context(project_id)
            if ctx:
                project_knowledge = ctx
        except Exception:
            logger.debug(
                "[EngagementManager] Could not load ideas context",
                exc_info=True,
            )

    task = Task(
        description=task_configs["engagement_response_task"]["description"].format(
            user_message=user_message,
            conversation_history=history_str,
            active_context=active_context,
            project_knowledge=project_knowledge,
        ),
        expected_output=task_configs["engagement_response_task"]["expected_output"],
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=is_verbose(),
    )

    logger.info(
        "[EngagementManager] CrewAI path for message: '%s'",
        user_message[:80],
    )

    result = crew_kickoff_with_retry(crew)
    response = str(result).strip()

    logger.info(
        "[EngagementManager] CrewAI response: '%s'",
        response[:200],
    )
    return response


# ── Heartbeat helpers ──────────────────────────────────────────

# Emoji map for heartbeat status prefixes
_HEARTBEAT_EMOJI: dict[str, str] = {
    "PLANNING": "\U0001f9e0",   # 🧠
    "STARTING": "\u2699\ufe0f",  # ⚙️
    "PROGRESS": "\u2699\ufe0f",  # ⚙️
    "COMPLETED": "\u2705",       # ✅
    "WAITING": "\U0001f4ac",     # 💬
    "STEERING": "\U0001f504",    # 🔄
}

# Map PRD flow progress events → (status, template) pairs
_PROGRESS_EVENT_MAP: dict[str, tuple[str, str]] = {
    "section_start": (
        "STARTING",
        "Drafting *{section_title}*\u2026",
    ),
    "section_complete": (
        "COMPLETED",
        "*{section_title}* approved after {iterations} iteration(s).",
    ),
    "all_sections_complete": (
        "COMPLETED",
        "All {total_sections} sections drafted and approved!",
    ),
    "idea_refinement_start": (
        "STARTING",
        "Refining your idea with industry expertise\u2026",
    ),
    "idea_refinement_complete": (
        "COMPLETED",
        "Idea refinement complete.",
    ),
    "exec_summary_start": (
        "STARTING",
        "Drafting executive summary\u2026",
    ),
    "exec_summary_iteration": (
        "PROGRESS",
        "Executive summary iteration {iteration}\u2026",
    ),
    "exec_summary_complete": (
        "COMPLETED",
        "Executive summary approved.",
    ),
    "requirements_start": (
        "STARTING",
        "Breaking down requirements \u2014 entities, APIs, state machines\u2026",
    ),
    "requirements_complete": (
        "COMPLETED",
        "Requirements breakdown complete.",
    ),
    "ceo_review_start": (
        "STARTING",
        "CEO review in progress \u2014 executive product summary\u2026",
    ),
    "ceo_review_complete": (
        "COMPLETED",
        "CEO review complete.",
    ),
    "eng_plan_start": (
        "STARTING",
        "Engineering Manager drafting architecture plan\u2026",
    ),
    "eng_plan_complete": (
        "COMPLETED",
        "Engineering plan complete.",
    ),
    "ux_design_start": (
        "STARTING",
        "UX Designer creating prototype\u2026",
    ),
    "ux_design_complete": (
        "COMPLETED",
        "UX design complete.",
    ),
    "finalize_start": (
        "STARTING",
        "Finalizing PRD document\u2026",
    ),
    "finalize_complete": (
        "COMPLETED",
        "PRD finalized and ready for publication.",
    ),
}


def generate_heartbeat(
    phase: str,
    status: str,
    agent_name: str = "",
    details: str = "",
) -> str:
    """Build a concise heartbeat message for a PRD flow event.

    Uses template-based formatting for instant response (no LLM call).

    Args:
        phase: Current flow phase (e.g. ``"idea_refinement"``).
        status: Heartbeat code — PLANNING, STARTING, PROGRESS,
            COMPLETED, WAITING, or STEERING.
        agent_name: Name of the active agent (optional).
        details: Extra context to include in the message.

    Returns:
        A short emoji-prefixed status message.
    """
    emoji = _HEARTBEAT_EMOJI.get(status.upper(), "\u2139\ufe0f")
    parts = [emoji]
    if agent_name:
        parts.append(f"[{agent_name}]")
    parts.append(details if details else f"{phase} \u2014 {status.lower()}")
    return " ".join(parts)


def make_heartbeat_progress_callback(
    initiator_user_id: str,
    notify: Callable[[str], None] | None = None,
) -> Callable[[str, dict], None]:
    """Create a progress callback that generates heartbeat messages.

    The returned callback translates PRD flow progress events into
    user-friendly heartbeat messages and optionally forwards them
    via *notify*.

    Args:
        initiator_user_id: Slack user ID of the session initiator.
        notify: Optional function to send the heartbeat message
            (e.g. post a Slack message).  If ``None``, heartbeats
            are logged only.

    Returns:
        A ``progress_callback(event_type, details)`` compatible with
        :func:`~…apis.prd.service.run_prd_flow`.
    """

    def _progress_callback(event_type: str, details: dict) -> None:
        mapping = _PROGRESS_EVENT_MAP.get(event_type)
        if mapping is None:
            logger.debug(
                "[Heartbeat] Unmapped event: %s (details=%s)",
                event_type,
                details,
            )
            return

        status, template = mapping
        try:
            message = template.format(**details)
        except KeyError:
            message = template  # use raw template when keys are missing

        heartbeat = generate_heartbeat(
            phase=event_type,
            status=status,
            details=message,
        )
        logger.info(
            "[Heartbeat] %s (user=%s)", heartbeat, initiator_user_id,
        )
        if notify is not None:
            try:
                notify(heartbeat)
            except Exception:
                logger.debug("Heartbeat notify failed", exc_info=True)

    return _progress_callback


# ── User steering detection ────────────────────────────────────

def detect_user_steering(
    user_message: str,
    current_phase: str,
    current_agent: str,
    idea: str,
    initiator_user_id: str,
    message_author_id: str,
) -> dict[str, Any]:
    """Classify a user message during an active PRD orchestration.

    Uses a **direct Gemini REST API call** to avoid CrewAI framework
    overhead.  Falls back to CrewAI when ``ENGAGEMENT_MANAGER_USE_CREWAI=true``
    or when the fast path fails.

    **Session isolation**: If *message_author_id* differs from
    *initiator_user_id*, returns ``{"classification": "IGNORE"}``
    immediately — no LLM call.

    Returns:
        A dict with keys ``classification``, ``action``,
        ``extracted_intent``, ``target_phase``.
    """
    # Session isolation — fast path
    if message_author_id != initiator_user_id:
        logger.info(
            "[Steering] Ignoring message from %s (initiator=%s)",
            message_author_id,
            initiator_user_id,
        )
        return {
            "classification": "IGNORE",
            "action": "Message is from a different user \u2014 ignored.",
            "extracted_intent": "",
            "target_phase": "",
        }

    use_crewai = os.environ.get(
        "ENGAGEMENT_MANAGER_USE_CREWAI", ""
    ).strip().lower() in ("true", "1", "yes")

    if not use_crewai:
        result = _detect_user_steering_fast(
            user_message, current_phase, current_agent, idea,
            initiator_user_id, message_author_id,
        )
        if result is not None:
            return result
        logger.warning(
            "[Steering] Fast path failed — falling back to CrewAI",
        )

    return _detect_user_steering_crewai(
        user_message, current_phase, current_agent, idea,
        initiator_user_id, message_author_id,
    )


def _detect_user_steering_fast(
    user_message: str,
    current_phase: str,
    current_agent: str,
    idea: str,
    initiator_user_id: str,
    message_author_id: str,
) -> dict[str, Any] | None:
    """Fast path: direct Gemini REST API call (~200-800 ms)."""
    from crewai_productfeature_planner.tools.gemini_chat import (
        generate_chat_response,
    )

    agent_config = _load_yaml("agent.yaml")["engagement_manager"]
    task_configs = _load_yaml("tasks.yaml")

    system_prompt = (
        f"Role: {agent_config['role'].strip()}\n"
        f"Goal: {agent_config['goal'].strip()}\n\n"
        f"{agent_config['backstory'].strip()}\n\n"
        "IMPORTANT: You MUST respond with valid JSON containing exactly "
        "these keys: classification, action, extracted_intent, target_phase."
    )

    task_description = task_configs["user_steering_detection_task"][
        "description"
    ].format(
        user_message=user_message,
        current_phase=current_phase,
        current_agent=current_agent,
        idea=idea[:500],
        initiator_user_id=initiator_user_id,
        message_author_id=message_author_id,
    )
    expected_output = task_configs["user_steering_detection_task"]["expected_output"]
    user_prompt = f"{task_description}\n\n## Expected Output\n{expected_output}"

    model = os.environ.get(
        "ENGAGEMENT_MANAGER_MODEL",
        os.environ.get("GEMINI_MODEL", ""),
    ).strip() or None

    logger.info(
        "[Steering] Fast path for message from %s: '%s'",
        message_author_id, user_message[:80],
    )

    try:
        raw = generate_chat_response(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.1,
            max_output_tokens=512,
            model_override=model,
        )
        if raw is None:
            return None
        return _parse_steering_result(raw)
    except Exception:
        logger.warning(
            "[Steering] Fast path classification failed",
            exc_info=True,
        )
        return None


def _detect_user_steering_crewai(
    user_message: str,
    current_phase: str,
    current_agent: str,
    idea: str,
    initiator_user_id: str,
    message_author_id: str,
) -> dict[str, Any]:
    """Slow path: CrewAI Crew.kickoff() (~3-5 s)."""
    from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

    task_configs = _load_yaml("tasks.yaml")
    agent = create_engagement_manager()

    task = Task(
        description=task_configs["user_steering_detection_task"][
            "description"
        ].format(
            user_message=user_message,
            current_phase=current_phase,
            current_agent=current_agent,
            idea=idea[:500],
            initiator_user_id=initiator_user_id,
            message_author_id=message_author_id,
        ),
        expected_output=task_configs["user_steering_detection_task"][
            "expected_output"
        ],
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=is_verbose(),
    )

    logger.info(
        "[Steering] CrewAI path for message from %s: '%s'",
        message_author_id,
        user_message[:80],
    )

    try:
        result = crew_kickoff_with_retry(crew, step_label="steering_detection")
        raw = str(result).strip()
        return _parse_steering_result(raw)
    except Exception:
        logger.warning(
            "[Steering] LLM classification failed, defaulting to QUESTION",
            exc_info=True,
        )
        return {
            "classification": "QUESTION",
            "action": "Unable to classify \u2014 treating as a question.",
            "extracted_intent": user_message[:200],
            "target_phase": current_phase,
        }


def _parse_steering_result(raw: str) -> dict[str, Any]:
    """Parse LLM steering detection output into a structured dict."""
    result: dict[str, Any] = {
        "classification": "QUESTION",
        "action": "",
        "extracted_intent": "",
        "target_phase": "",
    }

    # Try JSON parse first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for key in result:
                if key in parsed:
                    result[key] = parsed[key]
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Fall back to keyword extraction
    upper = raw.upper()
    for classification in ("IGNORE", "STEERING", "FEEDBACK", "UNRELATED", "QUESTION"):
        if classification in upper:
            result["classification"] = classification
            break

    result["action"] = raw[:500]
    return result


# ── Orchestration entry point ──────────────────────────────────

def orchestrate_idea_to_prd(
    idea: str,
    initiator_user_id: str,
    run_id: str,
    *,
    notify: Callable[[str], None] | None = None,
    conversation_history: list[dict] | None = None,
    auto_approve: bool = False,
    exec_summary_user_feedback_callback: Callable | None = None,
    executive_summary_callback: Callable | None = None,
    requirements_approval_callback: Callable | None = None,
) -> dict[str, Any]:
    """Orchestrate the full idea-to-PRD lifecycle with heartbeat updates.

    Wraps :func:`~…apis.prd.service.run_prd_flow` with heartbeat
    progress callbacks and session-isolation enforcement.

    Args:
        idea: Raw product idea text.
        initiator_user_id: Slack user ID of the session initiator.
            Only messages from this user are processed.
        run_id: Unique identifier for this PRD run.
        notify: Optional function to send heartbeat messages to the
            user (e.g. post a Slack message).
        conversation_history: Prior messages for context.
        auto_approve: Pass through to ``run_prd_flow``.
        exec_summary_user_feedback_callback: Pass through.
        executive_summary_callback: Pass through.
        requirements_approval_callback: Pass through.

    Returns:
        A dict with ``run_id``, ``initiator_user_id``, ``status``,
        and ``heartbeats`` list.
    """
    heartbeats: list[str] = []

    def _track_and_notify(message: str) -> None:
        heartbeats.append(message)
        if notify is not None:
            try:
                notify(message)
            except Exception:
                logger.debug("Heartbeat notify failed", exc_info=True)

    progress_cb = make_heartbeat_progress_callback(
        initiator_user_id=initiator_user_id,
        notify=_track_and_notify,
    )

    # Send initial planning heartbeat
    planning_msg = generate_heartbeat(
        phase="orchestration",
        status="PLANNING",
        details="Planning idea-to-PRD orchestration for your idea\u2026",
    )
    _track_and_notify(planning_msg)

    logger.info(
        "[Orchestrator] Starting idea-to-PRD (run_id=%s, initiator=%s, idea='%s')",
        run_id,
        initiator_user_id,
        idea[:80],
    )

    from crewai_productfeature_planner.apis.prd.service import run_prd_flow

    run_prd_flow(
        run_id=run_id,
        idea=idea,
        auto_approve=auto_approve,
        progress_callback=progress_cb,
        exec_summary_user_feedback_callback=exec_summary_user_feedback_callback,
        executive_summary_callback=executive_summary_callback,
        requirements_approval_callback=requirements_approval_callback,
    )

    completion_msg = generate_heartbeat(
        phase="orchestration",
        status="COMPLETED",
        details="Idea-to-PRD orchestration complete.",
    )
    _track_and_notify(completion_msg)

    logger.info(
        "[Orchestrator] Idea-to-PRD finished (run_id=%s, heartbeats=%d)",
        run_id,
        len(heartbeats),
    )

    return {
        "run_id": run_id,
        "initiator_user_id": initiator_user_id,
        "status": "completed",
        "heartbeats": heartbeats,
    }
