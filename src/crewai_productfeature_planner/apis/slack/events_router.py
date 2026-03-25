"""Slack Events API router.

Handles inbound events from the Slack Events API:

* **url_verification** -- Responds with the ``challenge`` token so Slack can
  verify the endpoint during setup.
* **member_joined_channel** -- When the bot joins a channel, posts an
  introductory message explaining how users can interact with it.
* **app_mention** -- When a user @mentions the bot, the message is
  interpreted via LLM and either kicks off a PRD flow or asks
  follow-up questions in a thread.
* **message** (in threads the bot is part of) -- Continues a multi-turn
  conversation.

The heavy lifting is delegated to sub-modules:

* ``_thread_state`` -- thread conversation cache, deduplication, bot identity
* ``_event_handlers`` -- app_mention, thread-message routing, error reply
* ``_message_handler`` -- intent classification and action dispatch
* ``_session_handlers`` -- project/setup/memory session handlers
* ``_flow_handlers`` -- PRD flow kickoff, publishing
* ``_next_step`` -- LLM-based proactive next-step prediction

All event payloads are verified using ``verify_slack_request`` (HMAC-SHA256
signing secret or deprecated verification-token fallback).
"""

from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from crewai_productfeature_planner.apis.slack._event_handlers import (
    _handle_app_mention,
    _handle_thread_message,
    _handle_thread_message_inner,
    _safe_error_reply,
)
from crewai_productfeature_planner.apis.slack._message_handler import (
    interpret_and_act,
)
from crewai_productfeature_planner.apis.slack._session_handlers import (
    handle_configure_memory,
    handle_create_project_intent,
    handle_current_project,
    handle_end_session,
    handle_list_ideas,
    handle_list_products,
    handle_memory_reply,
    handle_project_name_reply,
    handle_project_setup_reply,
    handle_switch_project,
    handle_update_config,
    post_intro,
    prompt_project_selection,
    reply as _reply,
)
from crewai_productfeature_planner.apis.slack._flow_handlers import (
    handle_check_publish_intent,
    handle_create_jira_intent,
    handle_publish_intent,
    handle_restart_prd,
    handle_resume_prd,
    kick_off_prd_flow,
)
from crewai_productfeature_planner.apis.slack._thread_state import (
    append_to_thread,
    get_bot_user_id,
    get_thread_history,
    has_thread_conversation,
    is_duplicate_event,
    touch_thread,
)
import crewai_productfeature_planner.apis.slack._thread_state as _ts
from crewai_productfeature_planner.apis.slack.verify import verify_slack_request

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Slack Events"])


# -- Backward-compatibility aliases --
# Some test files and interactive_handlers import these names from
# events_router.  Keep thin aliases so they keep working.
_get_bot_user_id = get_bot_user_id
_post_intro = post_intro
_interpret_and_act = interpret_and_act
_append_to_thread = append_to_thread
_get_thread_history = get_thread_history
_is_duplicate_event = is_duplicate_event
_reply = _reply
_handle_project_name_reply = handle_project_name_reply
_handle_project_setup_reply = handle_project_setup_reply
_handle_configure_memory = handle_configure_memory
_handle_create_project_intent = handle_create_project_intent
_handle_current_project = handle_current_project
_handle_end_session = handle_end_session
_handle_switch_project = handle_switch_project
_handle_update_config = handle_update_config
_handle_list_ideas = handle_list_ideas
_handle_list_products = handle_list_products
_handle_publish_intent = handle_publish_intent
_handle_create_jira_intent = handle_create_jira_intent
_handle_check_publish_intent = handle_check_publish_intent
_handle_resume_prd = handle_resume_prd
_handle_restart_prd = handle_restart_prd
_kick_off_prd_flow = kick_off_prd_flow
_prompt_project_selection = prompt_project_selection

# Expose internal state from _thread_state for tests that reference
# er._thread_lock, er._thread_conversations, etc.
_thread_lock = _ts._thread_lock
_thread_conversations = _ts._thread_conversations
_thread_last_active = _ts._thread_last_active
_seen_events_lock = _ts._seen_events_lock
_seen_events = _ts._seen_events


def __getattr__(name: str):
    """Proxy mutable scalar state (_bot_user_id) to _thread_state."""
    if name == "_bot_user_id":
        return _ts._bot_user_id
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Allow tests to assign  ``er._bot_user_id = ...``
import sys as _sys  # noqa: E402


class _ModuleProxy(type(_sys.modules[__name__])):
    """Thin module wrapper that proxies _bot_user_id writes to _thread_state."""

    def __setattr__(self, name: str, value):
        if name == "_bot_user_id":
            _ts._bot_user_id = value
            return
        super().__setattr__(name, value)

    def __getattr__(self, name: str):
        if name == "_bot_user_id":
            return _ts._bot_user_id
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_sys.modules[__name__].__class__ = _ModuleProxy


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
        "| ``url_verification`` | Slack setup handshake -- returns the challenge token |\n"
        "| ``member_joined_channel`` | Bot joined a channel -- posts an introductory message |\n"
        "| ``app_mention`` | User @mentioned the bot -- interprets the message via LLM and either kicks off a PRD flow or asks follow-up questions |\n"
        "| ``message`` (threaded) | Follow-up message in a thread the bot is part of -- continues multi-turn conversation or routes manual-refinement input |\n\n"
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

        # Inject the workspace team_id
        event["_team_id"] = payload.get("team_id", "")

        event_id = payload.get("event_id", "")
        if is_duplicate_event(event_id):
            logger.debug("Duplicate event_id %s -- ignoring", event_id)
            return JSONResponse({"ok": True})

        if event_subtype == "member_joined_channel":
            joined_user = event.get("user", "")
            channel_id = event.get("channel", "")
            team_id = event.get("_team_id", "")
            bot_id = get_bot_user_id()
            if bot_id and joined_user == bot_id:
                logger.info("Bot joined channel %s -- posting intro", channel_id)
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

            bot_id = get_bot_user_id()
            if bot_id and user == bot_id:
                return JSONResponse({"ok": True})
            # Allow thread_broadcast (reply posted to channel) through;
            # ignore other subtypes like message_changed, bot_message, etc.
            msg_subtype = event.get("subtype", "")
            if msg_subtype and msg_subtype != "thread_broadcast":
                return JSONResponse({"ok": True})

            # -- DMs: always process --
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

            # -- Channels: only threaded messages with known context --
            if thread_ts:
                key = (channel, thread_ts)

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

                has_conversation = has_thread_conversation(channel, thread_ts)

                from crewai_productfeature_planner.apis.slack.session_manager import (
                    has_pending_state,
                )
                has_pending = has_pending_state(user)

                # Check if the bot is @mentioned in this message.
                # Fallback conditions (active_session, thread_history)
                # require a mention — the bot should not respond to
                # threads where it wasn't tagged for that message.
                # When bot_id is unknown, skip the mention gate
                # (can't check what we don't know).
                _bot_mentioned = (
                    not bot_id  # unknown → can't gate
                    or f"<@{bot_id}>" in event.get("text", "")
                )

                # Fallback: if the channel has an active project
                # session (persisted in MongoDB), keep listening —
                # but only when the bot is @mentioned.
                has_active_session = False
                if not (has_conversation or has_interactive or has_pending):
                    from crewai_productfeature_planner.apis.slack.session_manager import (
                        get_channel_project_id,
                    )
                    if _bot_mentioned and get_channel_project_id(channel):
                        has_active_session = True

                # Last resort: check if the bot has ever replied in
                # this thread (persisted in agentInteraction) — but
                # only when the bot is @mentioned.
                has_thread_history = False
                if not (has_conversation or has_interactive
                        or has_pending or has_active_session):
                    if _bot_mentioned:
                        from crewai_productfeature_planner.mongodb.agent_interactions import (
                            has_bot_thread_history,
                        )
                        has_thread_history = has_bot_thread_history(
                            channel, thread_ts,
                        )
                        if has_thread_history:
                            # Re-register in the in-memory cache so
                            # subsequent messages skip the DB lookup.
                            touch_thread(channel, thread_ts)

                # Final fallback: check if a working-idea flow document
                # is linked to this thread (via slack_channel +
                # slack_thread_ts).  This catches auto-mode flows and
                # threads where the in-memory cache has expired.
                # No @mention required — the thread is already an
                # established flow conversation.
                has_flow_thread = False
                if not (has_conversation or has_interactive
                        or has_pending or has_active_session
                        or has_thread_history):
                    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                        find_idea_by_thread,
                    )
                    doc = find_idea_by_thread(channel, thread_ts)
                    if doc:
                        has_flow_thread = True
                        # Re-register so subsequent messages skip DB.
                        touch_thread(channel, thread_ts)

                should_process = (
                    has_conversation
                    or has_interactive
                    or has_pending
                    or has_active_session
                    or has_thread_history
                    or has_flow_thread
                )

                if should_process:
                    reason_parts = []
                    if has_interactive:
                        reason_parts.append("interactive")
                    if has_pending:
                        reason_parts.append("pending")
                    if has_active_session and not (has_conversation or has_interactive or has_pending):
                        reason_parts.append("active_session")
                    if has_thread_history and not (
                        has_conversation or has_interactive
                        or has_pending or has_active_session
                    ):
                        reason_parts.append("thread_history")
                    if has_flow_thread and not (
                        has_conversation or has_interactive
                        or has_pending or has_active_session
                        or has_thread_history
                    ):
                        reason_parts.append("flow_thread")
                    reason = f" ({', '.join(reason_parts)})" if reason_parts else ""
                    logger.info(
                        "Thread follow-up in %s/%s from %s%s",
                        channel, thread_ts, user, reason,
                    )
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(None, _handle_thread_message, event)
                else:
                    logger.debug(
                        "Ignoring thread message in %s/%s from %s "
                        "(no conversation, no interactive, no pending, "
                        "no active session, no thread history, "
                        "no flow thread)",
                        channel, thread_ts, user,
                    )

            return JSONResponse({"ok": True})

        logger.debug("Unhandled event subtype: %s", event_subtype)
        return JSONResponse({"ok": True})

    logger.debug("Unhandled payload type: %s", event_type)
    return JSONResponse({"ok": True})
