"""Core message interpretation and action routing for Slack events.

Extracted from ``events_router.py`` to keep the router slim.
Contains ``interpret_and_act()`` which classifies user intent via
the LLM and dispatches to the appropriate handler, plus the
interaction-logging wrapper.

**Late-binding note**: Handler functions (``prompt_project_selection``,
``kick_off_prd_flow``, etc.) are resolved at call time through the
``events_router`` module so that test patches on the module-level
aliases (e.g. ``events_router._prompt_project_selection``) take effect.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from crewai_productfeature_planner.apis.slack._thread_state import (
    append_to_thread,
    get_thread_history,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Late-bound handler accessors
# ---------------------------------------------------------------------------
# These resolve handler functions through ``events_router`` at call time
# so that ``unittest.mock.patch("...events_router._<name>")`` in tests
# always takes effect.  We import ``events_router`` lazily to avoid
# circular imports (events_router imports *us*).

_ER_MODULE = "crewai_productfeature_planner.apis.slack.events_router"


def _er():
    """Return the events_router module (lazy)."""
    return sys.modules[_ER_MODULE]


def _prompt_project_selection(channel, thread_ts, user):
    return _er()._prompt_project_selection(channel, thread_ts, user)


def _handle_switch_project(channel, thread_ts, user):
    return _er()._handle_switch_project(channel, thread_ts, user)


def _handle_end_session(channel, thread_ts, user):
    return _er()._handle_end_session(channel, thread_ts, user)


def _handle_current_project(channel, thread_ts, user, session):
    return _er()._handle_current_project(channel, thread_ts, user, session)


def _handle_configure_memory(channel, thread_ts, user, session):
    return _er()._handle_configure_memory(channel, thread_ts, user, session)


def _handle_update_config(channel, thread_ts, user, session, **kwargs):
    return _er()._handle_update_config(channel, thread_ts, user, session, **kwargs)


def _handle_create_project_intent(channel, thread_ts, user):
    return _er()._handle_create_project_intent(channel, thread_ts, user)


def _kick_off_prd_flow(**kwargs):
    return _er()._kick_off_prd_flow(**kwargs)


def _handle_publish_intent(channel, thread_ts, user, send_tool):
    return _er()._handle_publish_intent(channel, thread_ts, user, send_tool)


def _handle_check_publish_intent(channel, thread_ts, user, send_tool):
    return _er()._handle_check_publish_intent(channel, thread_ts, user, send_tool)


def _reply(channel, thread_ts, text):
    return _er()._reply(channel, thread_ts, text)


# ---------------------------------------------------------------------------
# Phrase constants for text-level safety-net matching
# ---------------------------------------------------------------------------

_IDEA_PHRASES = (
    "iterate an idea", "iterate a new idea", "iterate idea",
    "new idea", "start an idea", "brainstorm an idea",
    "refine my idea", "refine an idea", "plan an idea",
    "work on an idea", "create a prd", "create prd",
    "plan a feature", "build a prd", "help me iterate",
    "let's iterate", "let's brainstorm",
)
_CREATE_PROJECT_PHRASES = (
    "create a project", "create project", "new project",
    "set up a project", "setup a project", "start a project",
    "create a new project", "create new project",
    "setup project", "set up project",
    "start a new project", "start new project",
    "add a project", "add project", "add new project",
    "i need a project", "need a project",
    "project for this channel", "project for channel",
)
_LIST_PROJECTS_PHRASES = (
    "list projects", "show projects", "available projects",
    "show me available projects", "what projects",
    "which projects", "my projects", "all projects",
    "show me projects", "view projects",
)
_SWITCH_PROJECT_PHRASES = (
    "switch project", "change project", "different project",
    "another project", "swap project", "switch to project",
    "change to project", "switch to another project",
    "change to another project", "use a different project",
)
_END_SESSION_PHRASES = (
    "end session", "stop session", "close session",
    "i'm done", "im done", "quit session",
)
_CURRENT_PROJECT_PHRASES = (
    "current project", "my project", "which project",
    "active project", "what project",
)
_CONFIGURE_MEMORY_PHRASES = (
    "configure memory", "configure more memory",
    "project memory", "setup memory",
    "set up memory", "memory settings", "memory config",
    "edit memory", "update memory", "view memory",
    "show memory", "add memory", "add more memory",
    "manage memory", "memory configuration",
)
_UPDATE_CONFIG_PHRASES = (
    "confluence key", "confluence space key", "jira key",
    "jira project key", "set confluence", "add confluence",
    "add jira", "configure confluence", "configure jira",
    "space key", "parent page id", "parent id",
    "update config", "set config",
)


# ---------------------------------------------------------------------------
# Interaction logging helper
# ---------------------------------------------------------------------------


def log_tracked_interaction(
    log_fn,
    source: str,
    user_message: str,
    intent: str,
    agent_response: str,
    idea: str | None,
    run_id: str | None,
    project_id: str | None,
    channel: str,
    thread_ts: str,
    user_id: str,
    history: list | None = None,
    metadata: dict | None = None,
    predicted_next_step: dict | None = None,
) -> str | None:
    """Wrapper to log an agent interaction, swallowing errors.

    Returns the ``interaction_id`` on success, or ``None``.
    """
    try:
        return log_fn(
            source=source,
            user_message=user_message,
            intent=intent,
            agent_response=agent_response,
            idea=idea,
            run_id=run_id,
            project_id=project_id,
            channel=channel,
            thread_ts=thread_ts,
            user_id=user_id,
            conversation_history=history or None,
            metadata=metadata,
            predicted_next_step=predicted_next_step,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log agent interaction", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Phrase-based fallback when LLM interpretation fails
# ---------------------------------------------------------------------------

_PHRASE_INTENT_MAP: list[tuple[tuple[str, ...], str]] = [
    (_IDEA_PHRASES, "create_prd"),
    (_CONFIGURE_MEMORY_PHRASES, "configure_memory"),
    (_UPDATE_CONFIG_PHRASES, "update_config"),
    (_LIST_PROJECTS_PHRASES, "list_projects"),
    (_SWITCH_PROJECT_PHRASES, "switch_project"),
    (_END_SESSION_PHRASES, "end_session"),
    (_CURRENT_PROJECT_PHRASES, "current_project"),
    (_CREATE_PROJECT_PHRASES, "create_project"),
]


def _phrase_fallback(text: str) -> dict:
    """Derive intent from keyword phrases when the LLM is unavailable."""
    lower = text.lower().strip("* \t\n")
    for phrases, intent in _PHRASE_INTENT_MAP:
        if any(p in lower for p in phrases):
            logger.info("Phrase-fallback matched intent=%s for %r", intent, text[:80])
            return {"intent": intent, "idea": None, "reply": ""}
    # Check for common greetings/help
    if lower in ("help", "help me", "what can you do"):
        return {"intent": "help", "idea": None, "reply": ""}
    if lower in ("hi", "hello", "hey", "yo", "sup"):
        return {"intent": "greeting", "idea": None, "reply": ""}
    return {"intent": "unknown", "idea": None, "reply": ""}


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
        is_dm,
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
    has_switch_phrase = any(p in lower_text_bare for p in _SWITCH_PROJECT_PHRASES)
    has_end_phrase = any(p in lower_text_bare for p in _END_SESSION_PHRASES)
    has_current_phrase = any(p in lower_text_bare for p in _CURRENT_PROJECT_PHRASES)
    has_memory_phrase = any(p in lower_text_bare for p in _CONFIGURE_MEMORY_PHRASES)
    has_config_phrase = any(p in lower_text_bare for p in _UPDATE_CONFIG_PHRASES)

    # ── Idea-phrase override (highest priority) ──
    if has_idea_phrase:
        intent = "create_prd"

    # ── Session-management & navigation intents ──

    if intent == "list_projects" or (not has_idea_phrase and has_list_phrase):
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

    if intent == "update_config" or (not has_idea_phrase and not has_memory_phrase and has_config_phrase):
        _handle_update_config(
            channel, thread_ts, user, session,
            confluence_space_key=interpretation.get("confluence_space_key"),
            jira_project_key=interpretation.get("jira_project_key"),
            confluence_parent_id=interpretation.get("confluence_parent_id"),
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
        help_msg = (
            f"<@{user}> Here's what I can do:\n\n"
            "*Project Management*\n"
            "\u2022 Create a new project\n"
            "\u2022 List / show available projects\n"
            "\u2022 Switch to a different project\n"
            "\u2022 Show current project\n"
            "\u2022 End your session\n\n"
            "*PRD Generation*\n"
            "\u2022 Create a PRD — just describe your product idea\n"
            "\u2022 Publish PRDs to Confluence & create Jira tickets\n"
            "\u2022 Check publishing status\n\n"
            "*Configuration*\n"
            "\u2022 Configure project memory\n\n"
            "Just say what you need naturally — for example:\n"
            ">  _\"Create a PRD for a fitness tracking app\"_\n"
            ">  _\"Show me available projects\"_\n"
            ">  _\"Switch project\"_"
        )
        if not session_project_id:
            help_msg += (
                "\n\n:point_right: *To get started, select a project first* — "
                "just say something and I'll prompt you to pick one."
            )
        send_tool.run(channel=channel, text=help_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", help_msg)
        tracked_response = help_msg
        log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "greeting":
        greeting = reply_text or (
            f"<@{user}> Hey there! :wave: I'm ready to help you create "
            "a Product Requirements Document. Just give me a product idea "
            "and I'll get started!"
        )
        if not greeting.startswith(f"<@{user}>"):
            greeting = f"<@{user}> {greeting}"
        if not session_project_id:
            greeting += (
                "\n\n:point_right: *First, let's pick a project* — "
                "mention me with any request and I'll show you the project picker."
            )
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

    if intent == "create_prd":
        if not idea:
            ask_text = reply_text or (
                f"<@{user}> I'd love to create a PRD for you! "
                ":bulb: What product or feature idea would you like me to plan?"
            )
            if not ask_text.startswith(f"<@{user}>"):
                ask_text = f"<@{user}> {ask_text}"
            send_tool.run(channel=channel, text=ask_text, thread_ts=thread_ts)
            append_to_thread(channel, thread_ts, "assistant", ask_text)
            tracked_response = ask_text
        else:
            lower_text = clean_text.lower()
            interactive = any(
                kw in lower_text
                for kw in ("interactive", "step by step", "step-by-step", "guided")
            )

            if interactive:
                ack_text = (
                    f"<@{user}> Got it! :gear: Starting an *interactive* PRD flow for:\n"
                    f"> _{idea}_\n\n"
                    "I'll walk you through each step — refinement, approval, "
                    "and requirements — right here in this thread."
                )
            else:
                ack_text = (
                    f"<@{user}> Got it! :rocket: I'm starting a PRD generation "
                    f"flow for:\n> _{idea}_\n\n"
                    "I'll post the results here when done."
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

    elif intent == "check_publish":
        _handle_check_publish_intent(channel, thread_ts, user, send_tool)
        tracked_response = "(check_publish status reported)"

    else:
        fallback = reply_text or (
            f"<@{user}> I'm not sure what you'd like me to do. "
            ":thinking_face:\n\n"
            "Try mentioning me with a product idea, like:\n"
            ">  `@crewai-prd-bot create a PRD for a mobile app`\n\n"
            "Or type `help` for more options."
        )
        if not fallback.startswith(f"<@{user}>"):
            fallback = f"<@{user}> {fallback}"
        send_tool.run(channel=channel, text=fallback, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", fallback)
        tracked_response = fallback

    # ── Track this interaction for fine-tuning data ──
    interaction_id = log_tracked_interaction(
        log_interaction, "slack", clean_text, intent,
        tracked_response, idea, tracked_run_id, session_project_id,
        channel, thread_ts, user, history, tracked_metadata,
    )

    # ── Proactive next-step suggestion ──
    # After certain actions, predict and suggest the next step
    _SUGGEST_AFTER_INTENTS = {"create_prd", "publish", "check_publish"}
    if intent in _SUGGEST_AFTER_INTENTS and session_project_id:
        predict_and_post_next_step(
            channel=channel,
            thread_ts=thread_ts,
            user=user,
            project_id=session_project_id,
            trigger_action=f"intent_{intent}",
            interaction_id=interaction_id,
        )
