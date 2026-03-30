"""Core message interpretation and action routing for Slack events.

Extracted from ``events_router.py`` to keep the router slim.
Contains ``interpret_and_act()`` which classifies user intent via
the LLM and dispatches to the appropriate handler, plus the
interaction-logging wrapper.

**Late-binding note**: Handler functions (``prompt_project_selection``,
``kick_off_prd_flow``, etc.) are resolved at call time through the
``events_router`` module so that test patches on the module-level
aliases (e.g. ``events_router._prompt_project_selection``) take effect.

Sub-modules:
- ``_intent_phrases``   — phrase constants + ``_phrase_fallback()``
- ``_handler_proxies``  — late-bound handler proxy functions
- ``_message_utils``    — ``extract_idea_number()``, ``log_tracked_interaction()``
"""

from __future__ import annotations

import json
from typing import Any  # noqa: F401 — kept for downstream compatibility

from crewai_productfeature_planner.apis.slack._handler_proxies import (
    _handle_check_publish_intent,
    _handle_configure_memory,
    _handle_create_jira_intent,
    _handle_create_project_intent,
    _handle_current_project,
    _handle_end_session,
    _handle_list_ideas,
    _handle_list_products,
    _handle_publish_intent,
    _handle_restart_prd,
    _handle_resume_prd,
    _handle_switch_project,
    _handle_update_config,
    _kick_off_prd_flow,
    _prompt_project_selection,
    _reply,
)
from crewai_productfeature_planner.apis.slack._intent_phrases import (
    _CONFIGURE_MEMORY_PHRASES,
    _CREATE_JIRA_PHRASES,
    _CREATE_PROJECT_PHRASES,
    _CURRENT_PROJECT_PHRASES,
    _END_SESSION_PHRASES,
    _IDEA_PHRASES,
    _LIST_IDEAS_PHRASES,
    _LIST_PRODUCTS_PHRASES,
    _LIST_PROJECTS_PHRASES,
    _RESTART_PRD_PHRASES,
    _RESUME_PRD_PHRASES,
    _SUMMARIZE_IDEAS_PHRASES,
    _SWITCH_PROJECT_PHRASES,
    _UPDATE_CONFIG_PHRASES,
    _phrase_fallback,
)
from crewai_productfeature_planner.apis.slack._message_utils import (
    extract_idea_number,
    log_tracked_interaction,
)
from crewai_productfeature_planner.apis.slack._thread_state import (
    append_to_thread,
    get_thread_history,
)

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Phrases that indicate the user is asking about flow status / summary
_SUMMARY_PHRASES = (
    "summary", "status", "progress", "where are we",
    "how far", "what stage", "current state", "what's happening",
    "what is happening", "update me", "give me an update",
    "how's it going", "how is it going", "what section",
)


def _is_summary_request(text: str) -> bool:
    """Return ``True`` if *text* looks like a request for flow status."""
    lower = text.lower()
    return any(phrase in lower for phrase in _SUMMARY_PHRASES)


# Minimum word count for a legitimate idea description.
# "new idea", "create prd", "add idea" are commands, not ideas.
_MIN_IDEA_WORDS = 4


def _is_command_phrase_idea(idea_text: str) -> bool:
    """Return ``True`` if the LLM-extracted idea is really just a command.

    When a user says "add new idea" or "create a prd", the LLM sometimes
    extracts the command text itself as the idea (e.g. ``"new idea"``).
    This guard prevents auto-starting the flow with meaningless ideas.
    """
    stripped = idea_text.strip().lower()
    # Direct match against known command phrases
    if any(stripped == p for p in _IDEA_PHRASES):
        return True
    # Very short "ideas" are almost certainly just commands
    if len(stripped.split()) < _MIN_IDEA_WORDS:
        # Check if it's a substring of any command phrase or vice versa
        if any(p in stripped or stripped in p for p in _IDEA_PHRASES):
            return True
    return False


def _build_flow_summary(doc: dict) -> str | None:
    """Build a human-readable summary of the flow state from a working-idea doc.

    Returns ``None`` if the document doesn't contain enough data.
    """
    from crewai_productfeature_planner.apis.prd._sections import SECTION_ORDER

    status = doc.get("status", "unknown")
    idea_text = doc.get("idea") or doc.get("finalized_idea") or "Unknown idea"
    # Truncate long idea text
    if len(idea_text) > 200:
        idea_text = idea_text[:200] + "…"

    section_obj = doc.get("section") or {}
    completed_sections: list[str] = []
    for key, label in SECTION_ORDER:
        if key == "executive_summary":
            raw_exec = doc.get("executive_summary", [])
            if isinstance(raw_exec, list) and raw_exec:
                completed_sections.append(label)
        elif key in section_obj:
            entries = section_obj[key]
            if isinstance(entries, list) and entries:
                completed_sections.append(label)

    total = len(SECTION_ORDER)
    done = len(completed_sections)

    # Build status label
    status_labels = {
        "inprogress": ":gear: *In Progress*",
        "completed": ":white_check_mark: *Completed*",
        "paused": ":pause_button: *Paused*",
        "failed": ":x: *Failed*",
    }
    status_label = status_labels.get(status, f"*{status.title()}*")

    parts = [
        f"{status_label} — {done}/{total} sections complete",
        f"*Idea:* {idea_text}",
    ]
    if completed_sections:
        parts.append("*Sections done:* " + ", ".join(completed_sections))

    remaining = [
        label for key, label in SECTION_ORDER
        if label not in completed_sections
    ]
    if remaining and status == "inprogress":
        parts.append("*Remaining:* " + ", ".join(remaining))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Active-flow guard helper
# ---------------------------------------------------------------------------


def _is_flow_active(project_id: str) -> bool:
    """Return ``True`` if the project has any in-progress idea flow."""
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            has_active_idea_flow,
        )
        return has_active_idea_flow(project_id)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Summarize Ideas — uses Engagement Manager for AI-powered summary
# ---------------------------------------------------------------------------


def _handle_summarize_ideas(
    channel: str,
    thread_ts: str,
    user: str,
    clean_text: str,
    history: list[dict] | None,
    session_project_id: str | None,
    session_project_name: str | None,
    send_tool: object,
) -> str:
    """Summarize all ideas for the current project using the Engagement Manager.

    Unlike ``handle_list_ideas`` (which shows a formatted list), this uses
    the AI agent to produce a narrative summary — themes, synergies,
    gaps, and status overview.
    """
    from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
        BTN_HELP,
        BTN_LIST_IDEAS,
        BTN_NEW_IDEA,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    if not session_project_id:
        from crewai_productfeature_planner.apis.slack._handler_proxies import (
            _prompt_project_selection,
        )
        _prompt_project_selection(channel, thread_ts, user)
        return "(project selection required)"

    # Use the engagement manager with an explicit summarize instruction
    try:
        from crewai_productfeature_planner.agents.engagement_manager import (
            handle_unknown_intent,
        )
        ctx_parts: list[str] = []
        if session_project_id:
            ctx_parts.append(
                f"Active project: {session_project_name or session_project_id}"
            )
        active_context = " | ".join(ctx_parts) or "(no active context)"

        agent_response = handle_unknown_intent(
            user_message=(
                "Please provide a comprehensive summary of all ideas in this project. "
                "Include themes, synergies between ideas, status of each idea, "
                "coverage gaps, and any notable patterns."
            ),
            conversation_history=history,
            active_context=active_context,
            project_id=session_project_id,
        )
    except Exception:
        logger.warning(
            "Engagement Manager failed for summarize_ideas — using fallback",
            exc_info=True,
        )
        agent_response = ""

    if agent_response:
        text = f"<@{user}> :memo: *Ideas Summary*\n\n{agent_response}"
    else:
        text = (
            f"<@{user}> I couldn't generate a summary right now. "
            "Try listing your ideas instead."
        )

    buttons = [BTN_LIST_IDEAS, BTN_NEW_IDEA, BTN_HELP]

    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                    {"type": "actions", "elements": buttons},
                ],
                text=text,
            )
        except Exception:
            send_tool.run(channel=channel, text=text, thread_ts=thread_ts)
    else:
        send_tool.run(channel=channel, text=text, thread_ts=thread_ts)

    append_to_thread(channel, thread_ts, "assistant", text)
    return text


# ---------------------------------------------------------------------------
# Engagement Manager — handles unknown / general_question intents
# ---------------------------------------------------------------------------


def _handle_engagement_manager(
    channel: str,
    thread_ts: str,
    user: str,
    clean_text: str,
    history: list[dict] | None,
    session_project_id: str | None,
    session_project_name: str | None,
    reply_text: str,
    send_tool: object,
) -> str:
    """Use the Engagement Manager agent to handle unknown intents.

    Calls the agent synchronously to generate a context-aware response,
    then posts it with relevant action buttons.  Falls back to a static
    help message if the agent fails.
    """
    from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
        BTN_HELP,
        BTN_NEW_IDEA,
        BTN_LIST_IDEAS,
        BTN_RESUME_PRD,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    # Build active context description for the agent
    ctx_parts: list[str] = []
    if session_project_id:
        ctx_parts.append(
            f"Active project: {session_project_name or session_project_id}"
        )
    else:
        ctx_parts.append("No project selected yet.")
    active_context = " | ".join(ctx_parts)

    # Try the engagement manager agent
    try:
        from crewai_productfeature_planner.agents.engagement_manager import (
            handle_unknown_intent,
        )
        agent_response = handle_unknown_intent(
            user_message=clean_text,
            conversation_history=history,
            active_context=active_context,
            project_id=session_project_id,
        )
    except Exception:
        logger.warning(
            "Engagement Manager agent failed — using static fallback",
            exc_info=True,
        )
        agent_response = ""

    if agent_response:
        fallback_text = f"<@{user}> {agent_response}"
        # Track clarification requests in user_suggestions
        if agent_response.startswith("[CLARIFICATION]"):
            try:
                from crewai_productfeature_planner.mongodb.user_suggestions import (
                    log_suggestion,
                )
                log_suggestion(
                    user_message=clean_text,
                    agent_interpretation=agent_response,
                    suggestion_type="clarification_needed",
                    user_id=user,
                    project_id=session_project_id,
                    channel=channel,
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.debug(
                    "Failed to log clarification suggestion", exc_info=True,
                )
    else:
        fallback_text = reply_text or (
            f"<@{user}> I'm not sure what you'd like me to do. "
            ":thinking_face:\n\n"
            "Try mentioning me with a product idea to create a PRD, like:\n"
            ">  _\"iterate an idea for a mobile app\"_"
        )
        if not fallback_text.startswith(f"<@{user}>"):
            fallback_text = f"<@{user}> {fallback_text}"
        # Log unknown intents for learning
        try:
            from crewai_productfeature_planner.mongodb.user_suggestions import (
                log_suggestion,
            )
            log_suggestion(
                user_message=clean_text,
                agent_interpretation="(agent failed — static fallback)",
                suggestion_type="unknown_intent",
                user_id=user,
                project_id=session_project_id,
                channel=channel,
                thread_ts=thread_ts,
            )
        except Exception:
            logger.debug(
                "Failed to log unknown_intent suggestion", exc_info=True,
            )

    # Pick action buttons based on context
    buttons = [BTN_NEW_IDEA, BTN_HELP]
    if session_project_id:
        buttons = [BTN_NEW_IDEA, BTN_LIST_IDEAS, BTN_RESUME_PRD, BTN_HELP]

    client = _get_slack_client()
    posted = False
    if client:
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": fallback_text}},
                    {"type": "actions", "elements": buttons},
                ],
                text=fallback_text,
            )
            posted = True
        except Exception:
            logger.warning(
                "Block Kit post failed for engagement manager response "
                "(channel=%s thread=%s) — trying plain text fallback",
                channel, thread_ts, exc_info=True,
            )
            try:
                result = send_tool.run(channel=channel, text=fallback_text, thread_ts=thread_ts)
                import json as _json
                _parsed = _json.loads(result) if isinstance(result, str) else {}
                if _parsed.get("status") == "ok":
                    posted = True
            except Exception:
                logger.error(
                    "Plain text fallback also failed (channel=%s thread=%s)",
                    channel, thread_ts, exc_info=True,
                )
    else:
        try:
            result = send_tool.run(channel=channel, text=fallback_text, thread_ts=thread_ts)
            import json as _json
            _parsed = _json.loads(result) if isinstance(result, str) else {}
            if _parsed.get("status") == "ok":
                posted = True
        except Exception:
            logger.error(
                "send_tool.run failed — no Slack client (channel=%s thread=%s)",
                channel, thread_ts, exc_info=True,
            )

    if not posted:
        logger.error(
            "[EngagementManager] DELIVERY FAILED — response generated but "
            "could not be delivered to user. channel=%s thread=%s user=%s "
            "response_len=%d. Check Slack token validity.",
            channel, thread_ts, user, len(fallback_text),
        )

    append_to_thread(channel, thread_ts, "assistant", fallback_text)
    return fallback_text


# ---------------------------------------------------------------------------
# Idea Agent — handles questions/feedback during active idea iterations
# ---------------------------------------------------------------------------


def _handle_idea_agent(
    channel: str,
    thread_ts: str,
    user: str,
    clean_text: str,
    history: list[dict] | None,
    flow_doc: dict,
    send_tool: object,
) -> str:
    """Use the Idea Agent to answer questions about an active iteration.

    The Idea Agent has full access to the working-idea MongoDB document
    and can answer questions about the current idea, sections, critiques,
    and provide steering recommendations for upcoming iterations.

    Falls back to ``_build_flow_summary`` if the agent fails.
    """
    from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
        BTN_LIST_IDEAS,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    try:
        from crewai_productfeature_planner.agents.idea_agent import (
            handle_idea_query,
            extract_steering_feedback,
        )
        agent_response = handle_idea_query(
            user_message=clean_text,
            flow_doc=flow_doc,
            conversation_history=history,
        )
    except Exception:
        logger.warning(
            "[IdeaAgent] Agent failed — falling back to flow summary",
            exc_info=True,
        )
        agent_response = ""

    if agent_response:
        response_text = f"<@{user}> {agent_response}"

        # If the response contains steering feedback, persist it so
        # downstream agents can incorporate it in the next iteration.
        try:
            from crewai_productfeature_planner.agents.idea_agent import (
                extract_steering_feedback,
            )
            steering = extract_steering_feedback(agent_response)
            if steering:
                run_id = flow_doc.get("run_id")
                if run_id:
                    from crewai_productfeature_planner.mongodb.agent_interactions import (
                        log_interaction,
                    )
                    log_interaction(
                        source="slack",
                        user_message=clean_text,
                        intent="idea_agent_steering",
                        agent_response=steering,
                        run_id=run_id,
                        channel=channel,
                        thread_ts=thread_ts,
                        user_id=user,
                        metadata={"steering_feedback": steering},
                    )
                    logger.info(
                        "[IdeaAgent] Steering feedback saved for run_id=%s",
                        run_id,
                    )
        except Exception:
            logger.debug(
                "[IdeaAgent] Failed to persist steering feedback",
                exc_info=True,
            )
    else:
        # Fallback to the basic flow summary
        summary = _build_flow_summary(flow_doc)
        response_text = f"<@{user}> {summary}" if summary else (
            f"<@{user}> An idea iteration is active in this thread, "
            "but I couldn't fetch the details. Try asking again."
        )

    buttons = [BTN_LIST_IDEAS]

    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": response_text}},
                    {"type": "actions", "elements": buttons},
                ],
                text=response_text,
            )
        except Exception:
            send_tool.run(channel=channel, text=response_text, thread_ts=thread_ts)
    else:
        send_tool.run(channel=channel, text=response_text, thread_ts=thread_ts)

    append_to_thread(channel, thread_ts, "assistant", response_text)
    return response_text


# ---------------------------------------------------------------------------
# "Thinking…" acknowledgment
# ---------------------------------------------------------------------------


def _post_thinking(channel: str, thread_ts: str, user: str) -> None:
    """Post an immediate *Thinking…* indicator so the user knows the bot
    received their message.  Best-effort — never raises."""
    try:
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

        client = _get_slack_client()
        if client:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f":thinking_face: <@{user}> Thinking\u2026",
            )
    except Exception:  # noqa: BLE001
        logger.debug("_post_thinking failed", exc_info=True)


# ---------------------------------------------------------------------------
# Core: interpret + act
# ---------------------------------------------------------------------------


def interpret_and_act(
    channel: str,
    thread_ts: str,
    user: str,
    clean_text: str,
    event_ts: str,
) -> None:
    """Interpret the message via LLM and respond or kick off a PRD flow.

    Stateless intents (``help``, ``greeting``) are answered immediately,
    even without an active project session — they also nudge the user to
    select a project if none is active.

    Action-oriented intents (``create_prd``, ``publish``, etc.) require
    an active project session.  If the user has not selected a project
    yet, a project-selection prompt is posted and the current request is
    deferred — except for explicit session-management commands (switch
    project, end session, current project).
    """
    try:
        _post_thinking(channel, thread_ts, user)
        _interpret_and_act_inner(channel, thread_ts, user, clean_text, event_ts)
    except Exception:
        logger.exception(
            "Unhandled error in interpret_and_act "
            "(channel=%s thread=%s user=%s text=%r)",
            channel, thread_ts, user, clean_text[:80],
        )
        # Best-effort error reply so the user isn't left waiting
        try:
            from crewai_productfeature_planner.tools.slack_tools import (
                SlackSendMessageTool,
            )
            SlackSendMessageTool().run(
                channel=channel,
                thread_ts=thread_ts,
                text=(
                    f"<@{user}> :warning: Something went wrong while "
                    "processing your request. Please try again."
                ),
            )
        except Exception:
            logger.debug("Error-reply in interpret_and_act failed", exc_info=True)


def _interpret_and_act_inner(
    channel: str,
    thread_ts: str,
    user: str,
    clean_text: str,
    event_ts: str,
) -> None:
    """Inner implementation of interpret_and_act (unwrapped)."""
    from crewai_productfeature_planner.apis.slack._next_step import (
        predict_and_post_next_step,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
        get_context_session,
        is_dm,  # noqa: F811
    )
    from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
        log_interaction,
    )
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackInterpretMessageTool,
        SlackSendMessageTool,
    )

    history = get_thread_history(channel, thread_ts)
    append_to_thread(channel, thread_ts, "user", clean_text)

    interpret_tool = SlackInterpretMessageTool()
    send_tool = SlackSendMessageTool()

    history_json = json.dumps(history or [])
    try:
        interpretation = json.loads(
            interpret_tool.run(text=clean_text, conversation_history=history_json)
        )
    except Exception:
        logger.exception("LLM interpretation failed – falling back to phrase matching")
        interpretation = _phrase_fallback(clean_text)

    intent = interpretation.get("intent", "unknown")
    idea = interpretation.get("idea")
    reply_text = interpretation.get("reply", "")

    logger.info(
        "Interpretation: intent=%s idea=%r reply=%r",
        intent, idea, reply_text[:80] if reply_text else "",
    )

    # Collect the agent response for tracking
    tracked_response: str = ""
    tracked_run_id: str | None = None
    tracked_metadata: dict | None = None

    # Resolve active project session — context-aware (DM vs channel)
    session = get_context_session(user, channel)
    session_project_id = session.get("project_id") if session else None
    session_project_name = session.get("project_name") if session else None

    lower_text = clean_text.lower().strip()
    # Strip Slack mrkdwn formatting chars (*bold* _italic_ ~strike~)
    lower_text_bare = lower_text.strip("*_~ \t")

    has_idea_phrase = any(p in lower_text_bare for p in _IDEA_PHRASES)
    has_project_phrase = any(p in lower_text_bare for p in _CREATE_PROJECT_PHRASES)
    has_list_phrase = any(p in lower_text_bare for p in _LIST_PROJECTS_PHRASES)
    has_list_ideas_phrase = any(p in lower_text_bare for p in _LIST_IDEAS_PHRASES)
    has_summarize_phrase = any(p in lower_text_bare for p in _SUMMARIZE_IDEAS_PHRASES)
    has_switch_phrase = any(p in lower_text_bare for p in _SWITCH_PROJECT_PHRASES)
    has_end_phrase = any(p in lower_text_bare for p in _END_SESSION_PHRASES)
    has_current_phrase = any(p in lower_text_bare for p in _CURRENT_PROJECT_PHRASES)
    has_memory_phrase = any(p in lower_text_bare for p in _CONFIGURE_MEMORY_PHRASES)
    has_config_phrase = any(p in lower_text_bare for p in _UPDATE_CONFIG_PHRASES)
    has_list_products_phrase = any(p in lower_text_bare for p in _LIST_PRODUCTS_PHRASES)
    has_resume_phrase = any(p in lower_text_bare for p in _RESUME_PRD_PHRASES)
    has_restart_phrase = any(p in lower_text_bare for p in _RESTART_PRD_PHRASES)
    has_create_jira_phrase = any(p in lower_text_bare for p in _CREATE_JIRA_PHRASES)

    # ── Phrase overrides ──
    # These correct the LLM only for short, unambiguous command phrases
    # that have no overlap with idea descriptions.  Memory/config phrases
    # ("add memory", "update memory", "add knowledge", …) are NOT
    # overridden here because they can appear as substrings in real idea
    # text.  The LLM is the primary classifier for those intents.
    #
    # IMPORTANT: ``has_idea_phrase`` must be checked BEFORE
    # ``has_create_jira_phrase`` because long idea descriptions often
    # contain words like "jira tickets" or "jira epics" as part of the
    # idea body, which would falsely match _CREATE_JIRA_PHRASES.
    # Additionally, when the LLM already classified as ``create_prd``
    # with an idea, we trust the LLM over a jira phrase substring match.
    if has_restart_phrase:
        intent = "restart_prd"
    elif has_resume_phrase:
        intent = "resume_prd"
    elif has_idea_phrase:
        intent = "create_prd"
    elif has_create_jira_phrase and intent != "create_prd":
        intent = "create_jira"

    # ── Session-management & navigation intents ──

    # ── List products (must be checked BEFORE list_ideas) ──
    if intent == "list_products_intent" or (not has_idea_phrase and has_list_products_phrase):
        _handle_list_products(channel, thread_ts, user, session)
        tracked_response = "(list products)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "list_products_intent",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    # ── Summarize ideas (must be checked BEFORE list_ideas) ──
    if intent == "summarize_ideas" or (not has_idea_phrase and has_summarize_phrase):
        _handle_summarize_ideas(
            channel, thread_ts, user, clean_text, history,
            session_project_id, session_project_name, send_tool,
        )
        tracked_response = "(summarize ideas)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "summarize_ideas",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    # ── List ideas (must be checked BEFORE list_projects) ──
    # Guard: if the text matches memory/config phrases, don't let a
    # misclassified "list_ideas" LLM intent catch it — let it fall
    # through to the configure_memory / update_config dispatch below.
    if (intent == "list_ideas" and not has_memory_phrase and not has_config_phrase) or (not has_idea_phrase and has_list_ideas_phrase and not has_summarize_phrase):
        _handle_list_ideas(channel, thread_ts, user, session)
        tracked_response = "(list ideas)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "list_ideas",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "list_projects" or (not has_idea_phrase and not has_list_ideas_phrase and has_list_phrase):
        _prompt_project_selection(channel, thread_ts, user)
        tracked_response = "(list projects)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "list_projects",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "switch_project" or (not has_idea_phrase and has_switch_phrase):
        _handle_switch_project(channel, thread_ts, user)
        tracked_response = "(switch project prompt)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "switch_project",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "end_session" or (not has_idea_phrase and has_end_phrase):
        _handle_end_session(channel, thread_ts, user)
        tracked_response = "(session ended)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "end_session",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "current_project" or (not has_idea_phrase and has_current_phrase):
        _handle_current_project(channel, thread_ts, user, session)
        tracked_response = "(current project info)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "current_project",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if not has_memory_phrase and (intent == "update_config" or (not has_idea_phrase and has_config_phrase)):
        if not can_manage_memory(user, channel):
            _reply(
                channel, thread_ts,
                ":lock: Only workspace admins can configure project "
                "settings in a channel. Please ask an admin.",
            )
            tracked_response = "(admin required)"
            log_tracked_interaction(
                log_interaction, "slack", clean_text, "update_config",
                tracked_response, None, None, session_project_id,
                channel, thread_ts, user, history,
            )
            return
        # Block config changes while an idea flow is in-progress
        if session_project_id and _is_flow_active(session_project_id):
            _reply(
                channel, thread_ts,
                ":warning: Cannot configure project settings while an idea "
                "flow is in progress. Please wait for the current flow to "
                "complete or publish before making changes.",
            )
            tracked_response = "(blocked — active flow)"
            log_tracked_interaction(
                log_interaction, "slack", clean_text, "update_config",
                tracked_response, None, None, session_project_id,
                channel, thread_ts, user, history,
            )
            return
        _handle_update_config(
            channel, thread_ts, user, session,
            confluence_space_key=interpretation.get("confluence_space_key"),
            jira_project_key=interpretation.get("jira_project_key"),
        )
        tracked_response = "(update config)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "update_config",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "configure_memory" or (not has_idea_phrase and has_memory_phrase):
        if not can_manage_memory(user, channel):
            _reply(
                channel, thread_ts,
                ":lock: Only workspace admins can configure project "
                "memory in a channel. Please ask an admin.",
            )
            tracked_response = "(admin required)"
        else:
            # Block config changes while an idea flow is in-progress
            if session_project_id and _is_flow_active(session_project_id):
                _reply(
                    channel, thread_ts,
                    ":warning: Cannot configure project memory while an idea "
                    "flow is in progress. Please wait for the current flow to "
                    "complete or publish before making changes.",
                )
                tracked_response = "(blocked — active flow)"
            else:
                _handle_configure_memory(channel, thread_ts, user, session)
                tracked_response = "(memory configuration prompt)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, "configure_memory",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    # ── Stateless intents (no project session required) ──
    if intent == "help":
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            help_blocks,
        )
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

        help_text = f"<@{user}> Here's what I can do:"
        if not session_project_id:
            help_text += " To get started, select a project first."
        is_admin = can_manage_memory(user, channel)
        blocks = help_blocks(user, has_project=bool(session_project_id), is_admin=is_admin)
        client = _get_slack_client()
        if client:
            try:
                client.chat_postMessage(
                    channel=channel, thread_ts=thread_ts,
                    blocks=blocks, text=help_text,
                )
            except Exception:
                # Fallback to plain text
                send_tool.run(channel=channel, text=help_text, thread_ts=thread_ts)
        else:
            send_tool.run(channel=channel, text=help_text, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", help_text)
        tracked_response = help_text
        log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "greeting":
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            BTN_HELP,
            BTN_NEW_IDEA,
        )
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

        greeting = reply_text or (
            f"<@{user}> Hey there! :wave: I'm ready to help you iterate "
            "on a product idea."
        )
        if not greeting.startswith(f"<@{user}>"):
            greeting = f"<@{user}> {greeting}"
        if not session_project_id:
            greeting += (
                "\n\n:point_right: *First, let's pick a project* — "
                "mention me with any request and I'll show you the project picker."
            )
        # Post with action buttons
        client = _get_slack_client()
        if client:
            try:
                buttons = [BTN_NEW_IDEA, BTN_HELP]
                client.chat_postMessage(
                    channel=channel, thread_ts=thread_ts,
                    blocks=[
                        {"type": "section", "text": {"type": "mrkdwn", "text": greeting}},
                        {"type": "actions", "elements": buttons},
                    ],
                    text=greeting,
                )
            except Exception:
                send_tool.run(channel=channel, text=greeting, thread_ts=thread_ts)
        else:
            send_tool.run(channel=channel, text=greeting, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", greeting)
        tracked_response = greeting
        log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    # ── Create-project intent (no project session required) ──
    if has_idea_phrase:
        is_create_project = False
    elif session_project_id:
        is_create_project = has_project_phrase
    else:
        is_create_project = (
            intent == "create_project" or has_project_phrase
        )
    logger.debug(
        "Create-project check: intent=%s lower_text=%r "
        "phrase_match=%s idea_phrase=%s session_active=%s is_create_project=%s",
        intent, lower_text,
        [p for p in _CREATE_PROJECT_PHRASES if p in lower_text],
        has_idea_phrase, bool(session_project_id),
        is_create_project,
    )
    if is_create_project:
        intent = "create_project"
        _handle_create_project_intent(channel, thread_ts, user)
        tracked_response = "(create project prompt)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    # ── Global project-session gate ──
    if not session_project_id:
        _prompt_project_selection(channel, thread_ts, user)
        tracked_response = "(project selection required)"
        tracked_metadata_gate: dict | None = None
        if idea:
            tracked_metadata_gate = {"deferred_idea": idea}
        log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, None,
            channel, thread_ts, user, history, tracked_metadata_gate,
        )
        return

    if intent == "resume_prd":
        idea_num = extract_idea_number(clean_text)
        _handle_resume_prd(
            channel, thread_ts, user, send_tool,
            project_id=session_project_id,
            idea_number=idea_num,
        )
        tracked_response = "(resume_prd triggered)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, session_project_id,
            channel, thread_ts, user, history, tracked_metadata,
        )
        return

    if intent == "restart_prd":
        idea_num = extract_idea_number(clean_text)
        _handle_restart_prd(
            channel, thread_ts, user, send_tool, event_ts,
            project_id=session_project_id,
            idea_number=idea_num,
        )
        tracked_response = "(restart_prd triggered)"
        log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, session_project_id,
            channel, thread_ts, user, history, tracked_metadata,
        )
        return

    if intent == "create_prd":
        # Guard: if the LLM extracted a "idea" that is really just the
        # command phrase itself (e.g. "new idea", "add new idea",
        # "create a prd"), treat it as no-idea and prompt the user for
        # a real idea description instead of auto-starting the flow.
        if idea and _is_command_phrase_idea(idea):
            logger.info(
                "Idea text %r looks like a command phrase — prompting user",
                idea[:60],
            )
            idea = None

        if not idea:
            ask_text = reply_text or (
                f"<@{user}> I'd love to help you iterate on an idea! "
                ":bulb: What product or feature idea would you like to work on?"
            )
            if not ask_text.startswith(f"<@{user}>"):
                ask_text = f"<@{user}> {ask_text}"
            send_tool.run(channel=channel, text=ask_text, thread_ts=thread_ts)
            append_to_thread(channel, thread_ts, "assistant", ask_text)
            tracked_response = ask_text
        else:
            lower_text = clean_text.lower()
            # Automated (fully autonomous) is the DEFAULT.  The user
            # must explicitly opt-in with "interactive", "step-by-step",
            # etc. to get the manual approval gates.
            interactive_mode = any(
                kw in lower_text
                for kw in (
                    "interactive", "step-by-step", "step by step",
                    "manual", "walk me through",
                )
            )
            interactive = interactive_mode

            if interactive:
                ack_text = (
                    f"<@{user}> Got it! :gear: Starting an *interactive* idea iteration for:\n"
                    f"> _{idea}_\n\n"
                    "I'll walk you through each step — refinement, approval, "
                    "and requirements — right here in this thread."
                )
            else:
                ack_text = (
                    f"<@{user}> Got it! :rocket: I'm starting a *fully automated* "
                    f"idea iteration for:\n> _{idea}_\n\n"
                    "I'll keep you updated with progress summaries at each step. "
                    "Reply in this thread at any time to provide feedback or "
                    "steer the direction."
                )
            send_tool.run(channel=channel, text=ack_text, thread_ts=thread_ts)
            append_to_thread(channel, thread_ts, "assistant", ack_text)
            tracked_response = ack_text
            tracked_metadata = {"interactive": interactive}
            if session_project_id:
                tracked_metadata["project_id"] = session_project_id
                tracked_metadata["project_name"] = session_project_name
            _kick_off_prd_flow(
                channel=channel,
                thread_ts=thread_ts,
                user=user,
                idea=idea,
                event_ts=event_ts,
                interactive=interactive,
                project_id=session_project_id,
            )

    elif intent == "publish":
        _handle_publish_intent(channel, thread_ts, user, send_tool)
        tracked_response = "(publish pipeline triggered)"

    elif intent == "create_jira":
        _handle_create_jira_intent(channel, thread_ts, user, send_tool)
        tracked_response = "(create_jira pipeline triggered)"

    elif intent == "check_publish":
        _handle_check_publish_intent(channel, thread_ts, user, send_tool)
        tracked_response = "(check_publish status reported)"

    elif intent == "general_question":
        # Check if there's an active idea flow in this thread.
        # If so, route to the Idea Agent for context-rich answers
        # instead of the generic flow summary or engagement manager.
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_idea_by_thread,
        )
        flow_doc = find_idea_by_thread(channel, thread_ts)
        if flow_doc and flow_doc.get("status") in ("inprogress", "paused"):
            tracked_response = _handle_idea_agent(
                channel, thread_ts, user, clean_text, history,
                flow_doc, send_tool,
            )
            log_tracked_interaction(
                log_interaction, "slack", clean_text, "idea_agent_query",
                tracked_response, idea, flow_doc.get("run_id"),
                session_project_id,
                channel, thread_ts, user, history,
            )
            return

        # No active flow — general questions get a conversational reply
        # from the LLM intent classifier.
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            BTN_HELP,
            BTN_NEW_IDEA,
        )
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

        gq_text = reply_text or (
            f"<@{user}> I generate comprehensive PRD (Product Requirements Documents) "
            "by iterating on your idea through multiple refinement rounds. "
            "Try describing a product idea to get started!"
        )
        if not gq_text.startswith(f"<@{user}>"):
            gq_text = f"<@{user}> {gq_text}"
        client = _get_slack_client()
        if client:
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    blocks=[
                        {"type": "section", "text": {"type": "mrkdwn", "text": gq_text}},
                        {"type": "actions", "elements": [BTN_NEW_IDEA, BTN_HELP]},
                    ],
                    text=gq_text,
                )
            except Exception:
                send_tool.run(channel=channel, text=gq_text, thread_ts=thread_ts)
        else:
            send_tool.run(channel=channel, text=gq_text, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", gq_text)
        tracked_response = gq_text

    else:
        # Unknown intent — check for active idea flow first.
        # During an active iteration, the Idea Agent handles all
        # unrecognised questions (the Engagement Manager is disengaged).
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_idea_by_thread,
        )
        flow_doc = find_idea_by_thread(channel, thread_ts)
        if flow_doc and flow_doc.get("status") in ("inprogress", "paused"):
            tracked_response = _handle_idea_agent(
                channel, thread_ts, user, clean_text, history,
                flow_doc, send_tool,
            )
        else:
            tracked_response = _handle_engagement_manager(
                channel, thread_ts, user, clean_text, history,
                session_project_id, session_project_name,
                reply_text, send_tool,
            )

    # ── Track this interaction for fine-tuning data ──
    interaction_id = log_tracked_interaction(
        log_interaction, "slack", clean_text, intent,
        tracked_response, idea, tracked_run_id, session_project_id,
        channel, thread_ts, user, history, tracked_metadata,
    )

    # ── Proactive next-step suggestion ──
    # After certain *completed* actions, predict and suggest the next step.
    # Note: create_prd is intentionally excluded — the flow runs in a
    # background thread and hasn't completed any steps yet; a prediction
    # is posted after the flow finishes (see router._run_slack_prd_flow).
    _SUGGEST_AFTER_INTENTS = {"publish", "create_jira", "check_publish"}
    if intent in _SUGGEST_AFTER_INTENTS and session_project_id:
        predict_and_post_next_step(
            channel=channel,
            thread_ts=thread_ts,
            user=user,
            project_id=session_project_id,
            trigger_action=f"intent_{intent}",
            interaction_id=interaction_id,
        )
