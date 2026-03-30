"""Event handler functions for Slack Events API.

Extracted from ``events_router`` for modularity. Contains:

* ``_safe_error_reply`` -- best-effort error reply to the user
* ``_handle_app_mention`` -- handles @mentions of the bot
* ``_handle_thread_message`` -- handles threaded follow-up messages
* ``_handle_thread_message_inner`` -- core thread-message routing logic

**Patchability contract**: All calls to functions that ``events_router``
exposes as aliases (e.g. ``_handle_thread_message``, ``_interpret_and_act``,
``get_bot_user_id``, ``touch_thread``, ``append_to_thread``, etc.) are
resolved through ``sys.modules["...events_router"]`` at call-time so that
``@patch("...events_router.<name>")`` in tests intercepts them.
"""

from __future__ import annotations

import re
import sys

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

_ER_MODULE = "crewai_productfeature_planner.apis.slack.events_router"


def _er():
    """Return the events_router module for patchable call-through."""
    return sys.modules[_ER_MODULE]


def _safe_error_reply(
    channel: str, thread_ts: str, user: str, text: str,
) -> None:
    """Best-effort error reply to the user — never raises."""
    try:
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client
        client = _get_slack_client()
        if client:
            msg = f"<@{user}> :warning: {text}"
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=msg,
            )
            # Keep the conversation alive so the bot keeps listening
            _er().append_to_thread(channel, thread_ts, "assistant", msg)
    except Exception:
        logger.debug("_safe_error_reply itself failed", exc_info=True)


def _safe_ack_reply(
    channel: str, thread_ts: str, user: str, text: str,
) -> None:
    """Best-effort acknowledgement reply to the user — never raises."""
    try:
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client
        client = _get_slack_client()
        if client:
            msg = f"<@{user}> {text}"
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=msg,
            )
            _er().append_to_thread(channel, thread_ts, "assistant", msg)
    except Exception:
        logger.debug("_safe_ack_reply itself failed", exc_info=True)


def _handle_app_mention(event: dict) -> None:
    from crewai_productfeature_planner.apis.slack.session_manager import (
        has_pending_state,
    )
    from crewai_productfeature_planner.tools.slack_tools import (
        current_team_id,
        _get_slack_client,
    )

    current_team_id.set(event.get("_team_id"))

    channel = event.get("channel", "")
    text = event.get("text", "")
    user = event.get("user", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    event_ts = event.get("ts", "")
    clean_text = re.sub(r"<@[^>]+>\s*", "", text).strip()

    # ── Circuit breaker: skip processing if no usable Slack token ──
    client = _get_slack_client()
    if client is None:
        logger.error(
            "[EventHandler] Cannot process app_mention — no usable Slack "
            "token. Set SLACK_BOT_TOKEN in .env or re-install the Slack "
            "app. channel=%s user=%s text=%r",
            channel, user, clean_text[:80],
        )
        return

    er = _er()
    try:
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
            er._handle_thread_message(event)
            return

        er._interpret_and_act(channel, thread_ts, user, clean_text, event_ts)
    except Exception:
        logger.exception(
            "Unhandled error in _handle_app_mention "
            "(channel=%s thread=%s user=%s)", channel, thread_ts, user,
        )
        _safe_error_reply(
            channel, thread_ts, user,
            "Something went wrong while processing your message. "
            "Please try again.",
        )


def _handle_thread_message(event: dict) -> None:
    from crewai_productfeature_planner.tools.slack_tools import (
        current_team_id,
        _get_slack_client,
    )

    current_team_id.set(event.get("_team_id"))

    channel = event.get("channel", "")
    text = event.get("text", "")
    user = event.get("user", "")
    thread_ts = event.get("thread_ts", "")
    event_ts = event.get("ts", "")

    # ── Circuit breaker: skip processing if no usable Slack token ──
    client = _get_slack_client()
    if client is None:
        logger.error(
            "[EventHandler] Cannot process thread message — no usable "
            "Slack token. channel=%s user=%s",
            channel, user,
        )
        return

    er = _er()
    bot_id = er.get_bot_user_id()
    if bot_id and user == bot_id:
        return
    # Allow thread_broadcast (reply posted to channel) through;
    # ignore other subtypes like message_changed, bot_message, etc.
    msg_subtype = event.get("subtype", "")
    if msg_subtype and msg_subtype != "thread_broadcast":
        return

    # Ignore messages that are directed at another user (e.g.
    # "<@U0OTHER> you should try …").  These are human-to-human
    # conversations that the bot should not respond to.
    bot_mention_id = bot_id or ""
    directed_match = re.match(r"<@([^>]+)>", text)
    if directed_match and directed_match.group(1) != bot_mention_id:
        logger.debug(
            "Ignoring thread message directed at another user (%s) "
            "in %s/%s from %s",
            directed_match.group(1), channel, thread_ts, user,
        )
        return

    clean_text = re.sub(r"<@[^>]+>\s*", "", text).strip()
    if not clean_text:
        return

    try:
        er._handle_thread_message_inner(channel, thread_ts, user, clean_text, event_ts)
    except Exception:
        logger.exception(
            "Unhandled error in _handle_thread_message "
            "(channel=%s thread=%s user=%s text=%r)",
            channel, thread_ts, user, clean_text[:80],
        )
        _safe_error_reply(
            channel, thread_ts, user,
            "Something went wrong while processing your message. "
            "Please try again.",
        )


def _handle_thread_message_inner(
    channel: str,
    thread_ts: str,
    user: str,
    clean_text: str,
    event_ts: str,
) -> None:
    """Core thread-message logic, separated for top-level error handling."""
    er = _er()

    # Refresh the conversation cache FIRST so the TTL stays alive
    # regardless of which handler processes this message.
    er.touch_thread(channel, thread_ts)

    # Check if this is a project-name reply after "Create New Project"
    from crewai_productfeature_planner.apis.slack.session_manager import (
        get_pending_create_owner_for_thread,
        mark_pending_create,
        pop_pending_create,
        pop_pending_memory,
    )
    pending = pop_pending_create(user)
    if pending:
        if pending["channel"] == channel and pending["thread_ts"] == thread_ts:
            er._handle_project_name_reply(
                channel=channel,
                thread_ts=thread_ts,
                user=user,
                project_name=clean_text,
            )
            return
        mark_pending_create(user, pending["channel"], pending["thread_ts"])

    # If another user owns a pending create in this thread, ignore
    pending_owner = get_pending_create_owner_for_thread(channel, thread_ts)
    if pending_owner and pending_owner != user:
        logger.debug(
            "Ignoring thread reply from user=%s — pending create "
            "belongs to user=%s in %s/%s",
            user, pending_owner, channel, thread_ts,
        )
        er._reply(
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
            er._handle_project_setup_reply(
                channel=channel,
                thread_ts=thread_ts,
                user=user,
                text=clean_text,
            )
            return

    # Check if user is typing memory entries for a category
    pending_mem = pop_pending_memory(user)
    if pending_mem:
        # Before consuming as memory, check if the user is giving a
        # command (e.g. "create idea", "iterate an idea").  If a known
        # command phrase is detected, cancel memory mode and fall
        # through to the LLM-based intent classifier.
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )
        fb = _phrase_fallback(clean_text)
        if fb["intent"] not in ("unknown", "configure_memory"):
            logger.info(
                "Pending-memory cancelled — user command detected "
                "(phrase_intent=%s text=%r)",
                fb["intent"], clean_text[:80],
            )
            # Fall through to _interpret_and_act below
        else:
            er.handle_memory_reply(
                user_id=user,
                channel=channel,
                thread_ts=thread_ts,
                text=clean_text,
                category=pending_mem["category"],
                project_id=pending_mem["project_id"],
            )
            return

    # Check if this thread has an active manual-refinement or exec
    # summary feedback session — both accept thread replies as input.
    _THREAD_REPLY_ACTIONS = {
        "manual_refinement",
        "exec_summary_pre_feedback",
        "exec_summary_feedback",
    }
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        _interactive_runs,
        _lock as _ih_lock,
        queue_feedback,
        submit_manual_refinement,
    )
    _matched_run_id: str | None = None
    _matched_pending: str | None = None
    with _ih_lock:
        for run_id, info in _interactive_runs.items():
            if (
                info.get("channel") == channel
                and info.get("thread_ts") == thread_ts
            ):
                _matched_run_id = run_id
                _matched_pending = info.get("pending_action")
                break

    if _matched_run_id is not None:
        if _matched_pending in _THREAD_REPLY_ACTIONS:
            # Flow is blocking on a gate — deliver feedback directly
            submit_manual_refinement(_matched_run_id, clean_text)
            er.append_to_thread(channel, thread_ts, "user", clean_text)
            return
        # Flow is running but not at a gate (e.g. section drafting).
        # Queue the feedback for the section loop to pick up and
        # acknowledge so the user isn't left with silence.
        queue_feedback(_matched_run_id, clean_text)
        er.append_to_thread(channel, thread_ts, "user", clean_text)
        _safe_ack_reply(
            channel, thread_ts, user,
            ":memo: Got it! I'll incorporate your feedback "
            "into the next section iteration\u2026",
        )
        return

    # Check non-interactive exec summary feedback gate — thread replies
    # are treated as user critique / iteration feedback.
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        _exec_feedback_lock as _ef_lock,
        _pending_exec_feedback,
        resolve_exec_feedback,
    )
    _matched_ef_run_id: str | None = None
    with _ef_lock:
        for run_id, info in _pending_exec_feedback.items():
            if info.get("channel") == channel and info.get("thread_ts") == thread_ts:
                _matched_ef_run_id = run_id
                break
    if _matched_ef_run_id:
        resolve_exec_feedback(_matched_ef_run_id, "feedback", clean_text)
        er.append_to_thread(channel, thread_ts, "user", clean_text)
        return

    er._interpret_and_act(channel, thread_ts, user, clean_text, event_ts)
