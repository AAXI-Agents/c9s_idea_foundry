"""Slack Events API router.

Handles inbound events from the Slack Events API:

* **url_verification** – Responds with the ``challenge`` token so Slack can
  verify the endpoint during setup.
* **member_joined_channel** – When the bot joins a channel, posts an
  introductory message explaining how users can interact with it.
* **app_mention** – When a user @mentions the bot, the message is
  interpreted via OpenAI and either kicks off a PRD flow or asks
  follow-up questions in a thread.
* **message** (in threads the bot is part of) – Continues a multi-turn
  conversation.

All event payloads are verified using ``verify_slack_request`` (HMAC-SHA256
signing secret or deprecated verification-token fallback).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from crewai_productfeature_planner.apis.slack.verify import verify_slack_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Slack Events"])

# ---------------------------------------------------------------------------
# Bot identity cache
# ---------------------------------------------------------------------------

_bot_user_id: str | None = None


def _get_bot_user_id() -> str | None:
    """Return the bot's own Slack user ID (cached after first call)."""
    global _bot_user_id
    if _bot_user_id:
        return _bot_user_id

    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return None
    try:
        resp = client.auth_test()
        if resp.get("ok"):
            _bot_user_id = resp["user_id"]
            logger.info("Resolved bot user ID: %s", _bot_user_id)
            return _bot_user_id
    except Exception as exc:
        logger.warning("Could not resolve bot user ID: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Thread conversation state
# ---------------------------------------------------------------------------

_thread_lock = threading.Lock()
_thread_conversations: dict[tuple[str, str], list[dict]] = {}
_thread_last_active: dict[tuple[str, str], float] = {}
_THREAD_TTL_SECONDS = 600  # 10 minutes


def _get_thread_history(channel: str, thread_ts: str) -> list[dict]:
    with _thread_lock:
        _expire_threads()
        return list(_thread_conversations.get((channel, thread_ts), []))


def _append_to_thread(channel: str, thread_ts: str, role: str, content: str) -> None:
    with _thread_lock:
        key = (channel, thread_ts)
        if key not in _thread_conversations:
            _thread_conversations[key] = []
        _thread_conversations[key].append({"role": role, "content": content})
        _thread_last_active[key] = time.time()
        if len(_thread_conversations[key]) > 20:
            _thread_conversations[key] = _thread_conversations[key][-20:]


def _expire_threads() -> None:
    now = time.time()
    expired = [
        k for k, t in _thread_last_active.items()
        if now - t > _THREAD_TTL_SECONDS
    ]
    for k in expired:
        _thread_conversations.pop(k, None)
        _thread_last_active.pop(k, None)


# ---------------------------------------------------------------------------
# Deduplication (Slack may retry events)
# ---------------------------------------------------------------------------

_seen_events_lock = threading.Lock()
_seen_events: dict[str, float] = {}
_SEEN_TTL_SECONDS = 300


def _is_duplicate_event(event_id: str) -> bool:
    if not event_id:
        return False
    now = time.time()
    with _seen_events_lock:
        expired = [k for k, t in _seen_events.items() if now - t > _SEEN_TTL_SECONDS]
        for k in expired:
            del _seen_events[k]
        if event_id in _seen_events:
            return True
        _seen_events[event_id] = now
        return False


# ---------------------------------------------------------------------------
# Intro message
# ---------------------------------------------------------------------------

INTRO_MESSAGE = (
    ":wave: *Hey there!* I'm the *CrewAI Product Feature Planner Bot*.\n\n"
    "I can help you generate comprehensive Product Requirements Documents (PRDs). "
    "Just @mention me with your product idea:\n\n"
    ">  `@crewai-prd-bot create a PRD for a mobile fitness tracking app`\n"
    ">  `@crewai-prd-bot plan a feature for user onboarding flow`\n\n"
    "I'll kick off a PRD generation flow that:\n"
    ":one:  Refines your idea\n"
    ":two:  Breaks down requirements\n"
    ":three:  Drafts an executive summary and all PRD sections\n"
    ":four:  Posts a summary right here in this channel\n\n"
    "If I need more info, I'll ask you in a thread. :thread:\n\n"
    "_Type_ `@crewai-prd-bot help` _anytime._"
)


def _post_intro(channel_id: str, team_id: str | None = None) -> None:
    """Post the bot introduction message to a channel."""
    from crewai_productfeature_planner.tools.slack_tools import (
        _get_slack_client,
        current_team_id,
    )

    if team_id:
        current_team_id.set(team_id)

    client = _get_slack_client()
    if not client:
        logger.warning("Cannot post intro – no Slack client available")
        return
    try:
        client.chat_postMessage(channel=channel_id, text=INTRO_MESSAGE)
        logger.info("Posted intro message to channel %s", channel_id)
    except Exception as exc:
        logger.error("Failed to post intro to %s: %s", channel_id, exc)


# ---------------------------------------------------------------------------
# Slack reply helper
# ---------------------------------------------------------------------------


def _reply(channel: str, thread_ts: str, text: str) -> None:
    """Post a threaded reply in Slack."""
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
        except Exception as exc:
            logger.error("Slack reply failed: %s", exc)
    else:
        logger.error(
            "Cannot reply in %s — no Slack client available", channel,
        )


# ---------------------------------------------------------------------------
# Core: interpret + act
# ---------------------------------------------------------------------------


def _interpret_and_act(
    channel: str,
    thread_ts: str,
    user: str,
    clean_text: str,
    event_ts: str,
) -> None:
    """Interpret the message via OpenAI and respond or kick off a PRD flow.

    Stateless intents (``help``, ``greeting``) are answered immediately,
    even without an active project session — they also nudge the user to
    select a project if none is active.

    Action-oriented intents (``create_prd``, ``publish``, etc.) require
    an active project session.  If the user has not selected a project
    yet, a project-selection prompt is posted and the current request is
    deferred — except for explicit session-management commands (switch
    project, end session, current project).
    """
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

    history = _get_thread_history(channel, thread_ts)
    _append_to_thread(channel, thread_ts, "user", clean_text)

    interpret_tool = SlackInterpretMessageTool()
    send_tool = SlackSendMessageTool()

    history_json = json.dumps(history or [])
    interpretation = json.loads(
        interpret_tool.run(text=clean_text, conversation_history=history_json)
    )

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

    # ── Phrase constants for text-level safety-net matching ──
    lower_text = clean_text.lower().strip()

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
        "configure memory", "project memory", "setup memory",
        "edit memory", "update memory", "view memory",
        "show memory",
    )

    has_idea_phrase = any(p in lower_text for p in _IDEA_PHRASES)
    has_project_phrase = any(p in lower_text for p in _CREATE_PROJECT_PHRASES)
    has_list_phrase = any(p in lower_text for p in _LIST_PROJECTS_PHRASES)
    has_switch_phrase = any(p in lower_text for p in _SWITCH_PROJECT_PHRASES)
    has_end_phrase = any(p in lower_text for p in _END_SESSION_PHRASES)
    has_current_phrase = any(p in lower_text for p in _CURRENT_PROJECT_PHRASES)
    has_memory_phrase = any(p in lower_text for p in _CONFIGURE_MEMORY_PHRASES)

    # ── Idea-phrase override (highest priority) ──
    # If the text clearly describes an idea/PRD action, force create_prd
    # regardless of what the LLM returned.
    if has_idea_phrase:
        intent = "create_prd"

    # ── Session-management & navigation intents ──
    # Each is triggered by EITHER the LLM classification OR a text-phrase
    # safety net.  Phrase checks are skipped when an idea phrase matched
    # (intent already overridden to create_prd above).

    if intent == "list_projects" or (not has_idea_phrase and has_list_phrase):
        _prompt_project_selection(channel, thread_ts, user)
        tracked_response = "(list projects)"
        _log_tracked_interaction(
            log_interaction, "slack", clean_text, "list_projects",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "switch_project" or (not has_idea_phrase and has_switch_phrase):
        _handle_switch_project(channel, thread_ts, user)
        tracked_response = "(switch project prompt)"
        _log_tracked_interaction(
            log_interaction, "slack", clean_text, "switch_project",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "end_session" or (not has_idea_phrase and has_end_phrase):
        _handle_end_session(channel, thread_ts, user)
        tracked_response = "(session ended)"
        _log_tracked_interaction(
            log_interaction, "slack", clean_text, "end_session",
            tracked_response, None, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    if intent == "current_project" or (not has_idea_phrase and has_current_phrase):
        _handle_current_project(channel, thread_ts, user, session)
        tracked_response = "(current project info)"
        _log_tracked_interaction(
            log_interaction, "slack", clean_text, "current_project",
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
        _log_tracked_interaction(
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
        _append_to_thread(channel, thread_ts, "assistant", help_msg)
        tracked_response = help_msg
        _log_tracked_interaction(
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
        _append_to_thread(channel, thread_ts, "assistant", greeting)
        tracked_response = greeting
        _log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    # ── Create-project intent (no project session required) ──
    # Detect explicit "create project" requests via LLM intent or
    # text-level fallback so the user is never told to "select a
    # project" when they already asked to create one.
    # When user has an active session, only honour create_project if there
    # is an explicit project-creation phrase in the text.  This prevents
    # the LLM's "create_project" guess from overriding idea-related
    # requests like "iterate an idea".
    if has_idea_phrase:
        is_create_project = False
    elif session_project_id:
        # Session is active — only allow create_project on explicit phrase
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
        intent = "create_project"  # normalise for logging
        _handle_create_project_intent(channel, thread_ts, user)
        tracked_response = "(create project prompt)"
        _log_tracked_interaction(
            log_interaction, "slack", clean_text, intent,
            tracked_response, idea, None, session_project_id,
            channel, thread_ts, user, history,
        )
        return

    # ── Global project-session gate ──
    # Action-oriented intents (create_prd, publish, etc.) require
    # an active project session.  If the user hasn't selected a project
    # yet, prompt them and defer the current request.
    if not session_project_id:
        _prompt_project_selection(channel, thread_ts, user)
        tracked_response = "(project selection required)"
        tracked_metadata_gate: dict | None = None
        if idea:
            tracked_metadata_gate = {"deferred_idea": idea}
        _log_tracked_interaction(
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
            _append_to_thread(channel, thread_ts, "assistant", ask_text)
            tracked_response = ask_text
        else:
            # Check if the user wants interactive mode (mirrors CLI)
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
            _append_to_thread(channel, thread_ts, "assistant", ack_text)
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
        _append_to_thread(channel, thread_ts, "assistant", fallback)
        tracked_response = fallback

    # ── Track this interaction for fine-tuning data ──
    _log_tracked_interaction(
        log_interaction, "slack", clean_text, intent,
        tracked_response, idea, tracked_run_id, session_project_id,
        channel, thread_ts, user, history, tracked_metadata,
    )


# ---------------------------------------------------------------------------
# Session helpers (used by _interpret_and_act)
# ---------------------------------------------------------------------------


def _log_tracked_interaction(
    log_fn,
    source, user_message, intent, agent_response,
    idea, run_id, project_id,
    channel, thread_ts, user_id,
    history=None, metadata=None,
) -> None:
    """Wrapper to log an agent interaction, swallowing errors."""
    try:
        log_fn(
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
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log agent interaction", exc_info=True)


def _prompt_project_selection(channel: str, thread_ts: str, user: str) -> None:
    """Post the project-selection Block Kit prompt.

    In channels, only admins may select a project.  Non-admins are
    told to ask an admin.
    """
    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
        is_dm,
    )
    from crewai_productfeature_planner.apis.slack.blocks import project_selection_blocks
    from crewai_productfeature_planner.mongodb.project_config import list_projects
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        logger.error(
            "[ProjectSelection] Cannot post project selection for user=%s "
            "channel=%s — no Slack client available (SLACK_ACCESS_TOKEN not set?)",
            user, channel,
        )
        return

    # In channels, non-admins cannot select a project
    if not is_dm(channel) and not can_manage_memory(user, channel):
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=(
                    f"<@{user}> :lock: No project has been configured "
                    "for this channel yet. Please ask a workspace admin "
                    "to select a project first."
                ),
            )
        except Exception as exc:
            logger.error("Failed to post admin-required notice: %s", exc)
        return

    projects = list_projects(limit=20)
    blocks = project_selection_blocks(projects, user)
    msg = (
        f"<@{user}> Before we get started, please select a project "
        "to work on (or create a new one)."
    )
    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=blocks, text=msg,
        )
    except Exception as exc:
        logger.error("Failed to post project selection: %s", exc)


def _handle_switch_project(channel: str, thread_ts: str, user: str) -> None:
    """End the current session and show the project picker."""
    from crewai_productfeature_planner.apis.slack.session_manager import (
        deactivate_channel_session,
        deactivate_session,
        is_dm,
    )

    if is_dm(channel):
        deactivate_session(user)
    else:
        deactivate_channel_session(channel)
    _prompt_project_selection(channel, thread_ts, user)


def _handle_create_project_intent(
    channel: str, thread_ts: str, user: str,
) -> None:
    """Directly prompt the user for a project name (skipping the picker).

    This mirrors what happens when the user clicks the "Create New
    Project" button in the project-selection Block Kit, but triggered
    directly from natural language so the bot doesn't loop back with
    a redundant project-selection prompt.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_create_prompt_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
        is_dm,
        mark_pending_create,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        logger.error(
            "[CreateProject] No Slack client available for user=%s channel=%s",
            user, channel,
        )
        return

    # In channels, only admins may create projects
    if not is_dm(channel) and not can_manage_memory(user, channel):
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=(
                    f"<@{user}> :lock: Only workspace admins can create "
                    "a project for this channel. Please ask an admin."
                ),
            )
        except Exception as exc:
            logger.error("Failed to post admin-required notice: %s", exc)
        return

    mark_pending_create(user, channel, thread_ts)
    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=project_create_prompt_blocks(user),
            text="What would you like to name the new project? Reply in this thread.",
        )
        logger.info(
            "Prompted user=%s in channel=%s for new project name", user, channel,
        )
    except Exception as exc:
        logger.error("Failed to post create-project prompt: %s", exc)


def _handle_end_session(channel: str, thread_ts: str, user: str) -> None:
    """End the user's active session and confirm."""
    from crewai_productfeature_planner.apis.slack.blocks import session_ended_blocks
    from crewai_productfeature_planner.apis.slack.session_manager import (
        deactivate_channel_session,
        deactivate_session,
        is_dm,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    if is_dm(channel):
        deactivate_session(user)
    else:
        deactivate_channel_session(channel)
    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                blocks=session_ended_blocks(),
                text="Session ended",
            )
        except Exception as exc:
            logger.error("Failed to post session-ended: %s", exc)


def _handle_current_project(
    channel: str, thread_ts: str, user: str, session: dict | None,
) -> None:
    """Tell the user which project they're in (or that they have none)."""
    from crewai_productfeature_planner.apis.slack.blocks import active_session_blocks
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    if session and session.get("project_name"):
        blocks = active_session_blocks(
            session["project_name"],
            session.get("project_id", ""),
            user,
        )
        text = f"Current project: {session['project_name']}"
    else:
        _prompt_project_selection(channel, thread_ts, user)
        return

    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=blocks, text=text,
        )
    except Exception as exc:
        logger.error("Failed to post current-project: %s", exc)


def _handle_project_name_reply(
    channel: str, thread_ts: str, user: str, project_name: str,
) -> None:
    """Create a new project from a thread reply and enter setup wizard.

    After the project document is created in MongoDB the user is walked
    through optional setup steps (Confluence space key, Jira project
    key, Confluence parent page ID) before the session is activated.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_setup_step_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        mark_pending_setup,
    )
    from crewai_productfeature_planner.mongodb.project_config import create_project
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    project_id = create_project(name=project_name)
    if not project_id:
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=":x: Failed to create the project. Please try again.",
            )
        except Exception:
            pass
        return

    # ── Enter the project-setup wizard ──
    mark_pending_setup(user, channel, thread_ts, project_id, project_name)

    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=project_setup_step_blocks(project_name, "confluence_space_key", 1, 3),
            text="Enter the Confluence space key (or type 'skip').",
        )
        logger.info(
            "Project '%s' (id=%s) created — starting setup wizard for user=%s",
            project_name, project_id, user,
        )
    except Exception as exc:
        logger.error("Failed to post setup step prompt: %s", exc)


def _handle_project_setup_reply(
    channel: str, thread_ts: str, user: str, text: str,
) -> None:
    """Process a single setup-wizard reply and advance to the next step.

    When all steps are done, update the project config and activate the
    session.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_setup_complete_blocks,
        project_setup_step_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        _SETUP_STEPS,
        activate_channel_project,
        activate_project,
        advance_pending_setup,
        is_dm,
    )
    from crewai_productfeature_planner.mongodb.project_config import update_project
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    # "skip" / "s" / empty → store as empty string
    value = text.strip()
    if value.lower() in ("skip", "s", "-"):
        value = ""

    entry = advance_pending_setup(user, value)
    if entry is None:
        return

    step = entry["step"]
    project_id = entry["project_id"]
    project_name = entry["project_name"]

    if step == "done":
        # ── Finalise: persist keys and activate session ──
        update_fields: dict[str, str] = {}
        for key in ("confluence_space_key", "jira_project_key", "confluence_parent_id"):
            if entry.get(key):
                update_fields[key] = entry[key]
        if update_fields:
            update_project(project_id, **update_fields)
            logger.info(
                "Updated project %s with setup fields: %s",
                project_id, list(update_fields.keys()),
            )

        if is_dm(channel):
            activate_project(
                user_id=user,
                channel=channel,
                project_id=project_id,
                project_name=project_name,
            )
        else:
            activate_channel_project(
                channel_id=channel,
                project_id=project_id,
                project_name=project_name,
                activated_by=user,
            )

        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                blocks=project_setup_complete_blocks(project_name, entry),
                text=f"Project '{project_name}' created and session started!",
            )
        except Exception as exc:
            logger.error("Failed to post setup-complete: %s", exc)
        return

    # ── Post prompt for the next step ──
    step_idx = _SETUP_STEPS.index(step) + 1
    total = len(_SETUP_STEPS)
    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=project_setup_step_blocks(project_name, step, step_idx, total),
            text=f"Enter {step.replace('_', ' ')} (or type 'skip').",
        )
    except Exception as exc:
        logger.error("Failed to post setup step prompt: %s", exc)


# ---------------------------------------------------------------------------
# Memory configuration handlers
# ---------------------------------------------------------------------------


def _handle_configure_memory(
    channel: str,
    thread_ts: str,
    user: str,
    session: dict | None,
) -> None:
    """Show the project memory configuration menu."""
    from crewai_productfeature_planner.apis.slack.blocks import memory_configure_blocks
    from crewai_productfeature_planner.mongodb.project_memory import upsert_project_memory
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    if not session or not session.get("project_id"):
        _reply(channel, thread_ts, ":warning: No active project session. Please select a project first.")
        return

    project_id = session["project_id"]
    project_name = session.get("project_name", "Unknown")

    # Ensure memory scaffold exists
    upsert_project_memory(project_id)

    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=memory_configure_blocks(project_name, user),
            text=f"Configure memory for {project_name}",
        )
    except Exception as exc:
        logger.error("Failed to post memory config menu: %s", exc)


def _handle_memory_reply(
    user_id: str,
    channel: str,
    thread_ts: str,
    text: str,
    category: str,
    project_id: str,
) -> None:
    """Save memory entries typed by the user in a thread reply.

    Each non-empty line becomes a separate memory entry.
    """
    from crewai_productfeature_planner.apis.slack.blocks import memory_saved_blocks
    from crewai_productfeature_planner.mongodb.project_memory import (
        MemoryCategory,
        add_memory_entry,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    cat_enum = MemoryCategory(category)
    cat_labels = {
        MemoryCategory.IDEA_ITERATION: "Idea & Iteration",
        MemoryCategory.KNOWLEDGE: "Knowledge",
        MemoryCategory.TOOLS: "Tools",
    }
    cat_label = cat_labels.get(cat_enum, category)

    # Split multi-line reply into individual entries
    lines = [line.strip().lstrip("•-*") .strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    if not lines:
        _reply(channel, thread_ts, ":warning: No entries found. Please try again.")
        return

    saved = 0
    for line in lines:
        # Infer kind for knowledge entries
        kind = None
        if cat_enum == MemoryCategory.KNOWLEDGE:
            if line.startswith("http://") or line.startswith("https://"):
                kind = "link"
            else:
                kind = "note"

        ok = add_memory_entry(
            project_id,
            cat_enum,
            line,
            added_by=user_id,
            kind=kind,
        )
        if ok:
            saved += 1

    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=memory_saved_blocks(cat_label, saved),
            text=f"Saved {saved} {cat_label} entries",
        )
    except Exception as exc:
        logger.error("Failed to post memory-saved confirmation: %s", exc)


# ---------------------------------------------------------------------------
# Publish intent handlers
# ---------------------------------------------------------------------------


def _handle_publish_intent(channel: str, thread_ts: str, user: str, send_tool) -> None:
    """Publish all pending PRDs to Confluence and create Jira tickets."""
    ack = (
        f"<@{user}> :gear: Publishing all pending PRDs to Confluence and "
        "creating Jira tickets… I'll post the results shortly."
    )
    send_tool.run(channel=channel, text=ack, thread_ts=thread_ts)
    _append_to_thread(channel, thread_ts, "assistant", ack)

    try:
        from crewai_productfeature_planner.apis.publishing.service import (
            publish_all_and_create_tickets,
        )

        result = publish_all_and_create_tickets()

        conf = result.get("confluence", {})
        jira = result.get("jira", {})

        lines = [f"<@{user}> :white_check_mark: *Publishing complete!*\n"]

        # Confluence summary
        pub_count = conf.get("published", 0)
        pub_fail = conf.get("failed", 0)
        if pub_count or pub_fail:
            lines.append(f"*Confluence:* {pub_count} published, {pub_fail} failed")
            for r in conf.get("results", []):
                lines.append(f"  • _{r.get('title', '')}_ → <{r.get('url', '')}|View>")
        else:
            msg = conf.get("message", "No pending PRDs to publish")
            lines.append(f"*Confluence:* {msg}")

        # Jira summary
        jira_count = jira.get("completed", 0)
        jira_fail = jira.get("failed", 0)
        if jira_count or jira_fail:
            lines.append(f"*Jira:* {jira_count} completed, {jira_fail} failed")
            for r in jira.get("results", []):
                keys = r.get("ticket_keys", [])
                if keys:
                    lines.append(f"  • run `{r.get('run_id', '')[:8]}…` → {', '.join(keys)}")
        else:
            msg = jira.get("message", "No pending Jira deliveries")
            lines.append(f"*Jira:* {msg}")

        summary = "\n".join(lines)
        send_tool.run(channel=channel, text=summary, thread_ts=thread_ts)
        _append_to_thread(channel, thread_ts, "assistant", summary)

    except Exception as exc:
        err_msg = f"<@{user}> :x: Publishing failed: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        _append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Publish intent failed: %s", exc)


def _handle_check_publish_intent(channel: str, thread_ts: str, user: str, send_tool) -> None:
    """Check and report the publishing status of pending PRDs."""
    try:
        from crewai_productfeature_planner.apis.publishing.service import (
            list_pending_prds,
        )

        items = list_pending_prds()

        if not items:
            msg = (
                f"<@{user}> :white_check_mark: All clear! "
                "No PRDs pending Confluence publishing or Jira ticket creation."
            )
            send_tool.run(channel=channel, text=msg, thread_ts=thread_ts)
            _append_to_thread(channel, thread_ts, "assistant", msg)
            return

        lines = [f"<@{user}> :clipboard: *Pending PRD Deliveries* ({len(items)} total)\n"]
        for item in items:
            rid = item.get("run_id", "disk")[:8]
            title = item.get("title", "Untitled")
            conf = ":white_check_mark:" if item.get("confluence_published") else ":x:"
            jira = ":white_check_mark:" if item.get("jira_completed") else ":x:"
            lines.append(f"  • `{rid}…` _{title}_ — Confluence {conf}  Jira {jira}")

        lines.append(
            "\n_Say *publish* to publish all pending PRDs and create Jira tickets._"
        )

        msg = "\n".join(lines)
        send_tool.run(channel=channel, text=msg, thread_ts=thread_ts)
        _append_to_thread(channel, thread_ts, "assistant", msg)

    except Exception as exc:
        err_msg = f"<@{user}> :x: Failed to check publishing status: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        _append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Check publish intent failed: %s", exc)


# ---------------------------------------------------------------------------
# PRD flow kickoff
# ---------------------------------------------------------------------------


def _kick_off_prd_flow(
    *,
    channel: str,
    thread_ts: str,
    user: str,
    idea: str,
    event_ts: str,
    interactive: bool = False,
    project_id: str | None = None,
) -> None:
    """Start a PRD flow from a Slack interaction.

    When *interactive* is ``True``, the flow mirrors the CLI experience:
    refinement mode choice, idea approval, and requirements approval are
    all presented as Block Kit button prompts in the thread before
    sections are auto-generated.

    When ``False`` (the default), the flow runs with ``auto_approve=True``
    as before.

    If *project_id* is provided the working-idea document will be linked
    to the project so publishing can resolve project-level keys.
    """
    from crewai_productfeature_planner.apis.slack.router import _run_slack_prd_flow
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if client:
        try:
            client.reactions_add(channel=channel, timestamp=event_ts, name="eyes")
        except Exception:
            pass

    run_id = uuid.uuid4().hex[:12]

    if interactive:
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            run_interactive_slack_flow,
        )
        t = threading.Thread(
            target=run_interactive_slack_flow,
            args=(run_id, idea, channel, thread_ts, user),
            kwargs={"project_id": project_id},
            name=f"slack-prd-interactive-{run_id}",
            daemon=True,
        )
    else:
        t = threading.Thread(
            target=_run_slack_prd_flow,
            args=(run_id, idea, channel, thread_ts),
            kwargs={"project_id": project_id} if project_id else {},
            name=f"slack-prd-{run_id}",
            daemon=True,
        )
    t.start()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_app_mention(event: dict) -> None:
    from crewai_productfeature_planner.apis.slack.session_manager import (
        has_pending_state,
    )
    from crewai_productfeature_planner.tools.slack_tools import current_team_id

    current_team_id.set(event.get("_team_id"))

    channel = event.get("channel", "")
    text = event.get("text", "")
    user = event.get("user", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    event_ts = event.get("ts", "")
    clean_text = re.sub(r"<@[^>]+>\s*", "", text).strip()

    # If this user has a pending input state (e.g. awaiting a project
    # name after "Create New Project") and the message is in a thread,
    # route through _handle_thread_message so the pending-state logic
    # fires instead of re-interpreting via the LLM.
    if event.get("thread_ts") and has_pending_state(user):
        logger.info(
            "app_mention redirected to thread handler (pending state) "
            "user=%s channel=%s thread=%s",
            user, channel, thread_ts,
        )
        _handle_thread_message(event)
        return

    _interpret_and_act(channel, thread_ts, user, clean_text, event_ts)


def _handle_thread_message(event: dict) -> None:
    from crewai_productfeature_planner.tools.slack_tools import current_team_id

    current_team_id.set(event.get("_team_id"))

    channel = event.get("channel", "")
    text = event.get("text", "")
    user = event.get("user", "")
    thread_ts = event.get("thread_ts", "")
    event_ts = event.get("ts", "")

    bot_id = _get_bot_user_id()
    if bot_id and user == bot_id:
        return
    if event.get("subtype"):
        return

    clean_text = re.sub(r"<@[^>]+>\s*", "", text).strip()
    if not clean_text:
        return

    # Check if this is a project-name reply after "Create New Project"
    from crewai_productfeature_planner.apis.slack.session_manager import (
        get_pending_create_owner_for_thread,
        mark_pending_create,
        pop_pending_create,
        pop_pending_memory,
    )
    pending = pop_pending_create(user)
    if pending:
        # Only consume when the reply is in the SAME thread the bot asked in.
        if pending["channel"] == channel and pending["thread_ts"] == thread_ts:
            _handle_project_name_reply(
                channel=channel,
                thread_ts=thread_ts,
                user=user,
                project_name=clean_text,
            )
            return
        # Thread mismatch — restore the pending entry so the user can
        # still reply in the correct thread later.
        mark_pending_create(user, pending["channel"], pending["thread_ts"])

    # If another user owns a pending create in this thread, ignore
    # this message — only the initiating user may provide the name.
    pending_owner = get_pending_create_owner_for_thread(channel, thread_ts)
    if pending_owner and pending_owner != user:
        logger.debug(
            "Ignoring thread reply from user=%s — pending create "
            "belongs to user=%s in %s/%s",
            user, pending_owner, channel, thread_ts,
        )
        _reply(
            channel, thread_ts,
            f"<@{user}> :hourglass_flowing_sand: I'm waiting for "
            f"<@{pending_owner}> to provide the project name. "
            "Please wait until they're done.",
        )
        return

    # Check if user is in the project-setup wizard (confluence/jira keys)
    from crewai_productfeature_planner.apis.slack.session_manager import (
        get_pending_setup,
    )
    setup_entry = get_pending_setup(user)
    if setup_entry:
        if setup_entry["channel"] == channel and setup_entry["thread_ts"] == thread_ts:
            _handle_project_setup_reply(
                channel=channel,
                thread_ts=thread_ts,
                user=user,
                text=clean_text,
            )
            return

    # Check if user is typing memory entries for a category
    pending_mem = pop_pending_memory(user)
    if pending_mem:
        _handle_memory_reply(
            user_id=user,
            channel=channel,
            thread_ts=thread_ts,
            text=clean_text,
            category=pending_mem["category"],
            project_id=pending_mem["project_id"],
        )
        return

    # Check if this thread has an active manual-refinement session.
    # If so, route the message there instead of the general interpreter.
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        _interactive_runs,
        _lock as _ih_lock,
        submit_manual_refinement,
    )
    with _ih_lock:
        for run_id, info in _interactive_runs.items():
            if (
                info.get("channel") == channel
                and info.get("thread_ts") == thread_ts
                and info.get("pending_action") == "manual_refinement"
            ):
                submit_manual_refinement(run_id, clean_text)
                _append_to_thread(channel, thread_ts, "user", clean_text)
                return

    _interpret_and_act(channel, thread_ts, user, clean_text, event_ts)


# ---------------------------------------------------------------------------
# Events endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/slack/events",
    tags=["Slack Events"],
    summary="Slack Events API endpoint",
    response_description="Event acknowledged",
    description=(
        "Handles inbound event payloads from the Slack Events API.\n\n"
        "This is the **Request URL** configured in the Slack app under "
        "*Event Subscriptions*. All payloads are verified using "
        "``verify_slack_request`` (HMAC-SHA256 signing secret or "
        "deprecated verification-token fallback).\n\n"
        "**Supported event types:**\n\n"
        "| Event | Description |\n"
        "|---|---|\n"
        "| ``url_verification`` | Slack setup handshake — returns the challenge token |\n"
        "| ``member_joined_channel`` | Bot joined a channel — posts an introductory message |\n"
        "| ``app_mention`` | User @mentioned the bot — interprets the message via OpenAI and either kicks off a PRD flow or asks follow-up questions |\n"
        "| ``message`` (threaded) | Follow-up message in a thread the bot is part of — continues multi-turn conversation or routes manual-refinement input |\n\n"
        "**Interactive mode detection**: when an @mention contains keywords "
        "like *\"interactive\"*, *\"step by step\"*, or *\"guided\"*, the PRD "
        "flow starts in interactive mode with Block Kit button prompts "
        "for each decision point.\n\n"
        "**Deduplication**: Slack may retry delivery of the same event. "
        "Events are deduplicated by ``event_id`` with a 5-minute TTL "
        "to prevent duplicate processing.\n\n"
        "**Thread state**: multi-turn conversations are tracked in memory "
        "with a 10-minute TTL and a maximum of 20 messages per thread.\n\n"
        "All event callbacks receive an immediate ``{\"ok\": true}`` "
        "response; processing happens asynchronously in a thread pool."
    ),
    dependencies=[Depends(verify_slack_request)],
    responses={
        200: {
            "description": "Event acknowledged.",
            "content": {
                "application/json": {
                    "examples": {
                        "event_ack": {
                            "summary": "Standard event acknowledgement",
                            "value": {"ok": True},
                        },
                        "url_verification": {
                            "summary": "URL verification challenge response",
                            "value": {"challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"},
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid JSON payload."},
    },
)
async def slack_events(request: Request) -> JSONResponse:
    """Handle inbound events from the Slack Events API.

    Supported events: ``url_verification``, ``member_joined_channel``,
    ``app_mention``, and threaded ``message`` follow-ups.
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    event_type = payload.get("type", "")

    # ---- URL verification (Slack setup handshake) ----
    if event_type == "url_verification":
        challenge = payload.get("challenge", "")
        logger.info("Slack url_verification challenge received")
        return JSONResponse({"challenge": challenge})

    # ---- Event callbacks ----
    if event_type == "event_callback":
        event = payload.get("event", {})
        event_subtype = event.get("type", "")

        # Top-level diagnostics — log every inbound event so we can
        # confirm what Slack is (and isn't) delivering.
        logger.info(
            "Inbound Slack event: type=%s channel=%s user=%s "
            "thread_ts=%s ts=%s subtype=%s text=%s",
            event_subtype,
            event.get("channel", ""),
            event.get("user", ""),
            event.get("thread_ts", ""),
            event.get("ts", ""),
            event.get("subtype", ""),
            (event.get("text") or "")[:80],
        )

        # Inject the workspace team_id so downstream handlers can
        # resolve the correct OAuth token from MongoDB.
        event["_team_id"] = payload.get("team_id", "")

        event_id = payload.get("event_id", "")
        if _is_duplicate_event(event_id):
            logger.debug("Duplicate event_id %s — ignoring", event_id)
            return JSONResponse({"ok": True})

        if event_subtype == "member_joined_channel":
            joined_user = event.get("user", "")
            channel_id = event.get("channel", "")
            team_id = event.get("_team_id", "")
            bot_id = _get_bot_user_id()
            if bot_id and joined_user == bot_id:
                logger.info("Bot joined channel %s – posting intro", channel_id)
                loop = asyncio.get_event_loop()
                loop.run_in_executor(
                    None, _post_intro, channel_id, team_id,
                )
            return JSONResponse({"ok": True})

        if event_subtype == "app_mention":
            logger.info(
                "app_mention in %s from %s: %s",
                event.get("channel"), event.get("user"),
                event.get("text", "")[:80],
            )
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _handle_app_mention, event)
            return JSONResponse({"ok": True})

        if event_subtype == "message":
            channel = event.get("channel", "")
            thread_ts = event.get("thread_ts", "")
            user = event.get("user", "")

            # Skip bot's own messages and message subtypes (edits, etc.)
            bot_id = _get_bot_user_id()
            if bot_id and user == bot_id:
                return JSONResponse({"ok": True})
            if event.get("subtype"):
                return JSONResponse({"ok": True})

            # ── DMs: always process (users don't @mention in DMs) ──
            from crewai_productfeature_planner.apis.slack.session_manager import (
                is_dm,
            )
            if is_dm(channel):
                if thread_ts:
                    logger.info(
                        "DM thread follow-up in %s/%s from %s",
                        channel, thread_ts, user,
                    )
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(None, _handle_thread_message, event)
                else:
                    logger.info(
                        "DM message in %s from %s: %s",
                        channel, user, event.get("text", "")[:80],
                    )
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(None, _handle_app_mention, event)
                return JSONResponse({"ok": True})

            # ── Channels: only threaded messages with known context ──
            if thread_ts:
                key = (channel, thread_ts)

                # Check for active interactive flow in this thread
                from crewai_productfeature_planner.apis.slack.interactive_handlers import (
                    _interactive_runs,
                    _lock as _ih_lock,
                )
                has_interactive = False
                with _ih_lock:
                    for info in _interactive_runs.values():
                        if info.get("channel") == channel and info.get("thread_ts") == thread_ts:
                            has_interactive = True
                            break

                with _thread_lock:
                    _expire_threads()
                    has_conversation = key in _thread_conversations

                # Also check if user has pending input state (project
                # create name reply, memory entry) — ensures the reply
                # is processed even after the thread TTL expires.
                from crewai_productfeature_planner.apis.slack.session_manager import (
                    has_pending_state,
                )
                has_pending = has_pending_state(user)

                if has_conversation or has_interactive or has_pending:
                    logger.info(
                        "Thread follow-up in %s/%s from %s%s%s",
                        channel, thread_ts, user,
                        " (interactive)" if has_interactive else "",
                        " (pending)" if has_pending else "",
                    )
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(None, _handle_thread_message, event)

            return JSONResponse({"ok": True})

        logger.debug("Unhandled event subtype: %s", event_subtype)
        return JSONResponse({"ok": True})

    logger.debug("Unhandled payload type: %s", event_type)
    return JSONResponse({"ok": True})
