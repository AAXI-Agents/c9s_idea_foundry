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


def _post_intro(channel_id: str) -> None:
    """Post the bot introduction message to a channel."""
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

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
    """Interpret the message via OpenAI and respond or kick off a PRD flow."""
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

    if intent == "help":
        help_msg = (
            f"<@{user}> Here's how to use me:\n\n"
            "Mention me with a product idea and I'll generate a PRD. For example:\n"
            ">  `@crewai-prd-bot create a PRD for a fitness tracking app`\n"
            ">  `@crewai-prd-bot plan a feature for user authentication`\n\n"
            "You can also say things naturally like:\n"
            ">  _\"I need a PRD for an AI-powered chatbot\"_\n"
            ">  _\"Help me plan a real-time notification system\"_\n\n"
            "I'll ask follow-up questions if I need more info. :thread:"
        )
        send_tool.run(channel=channel, text=help_msg, thread_ts=thread_ts)
        _append_to_thread(channel, thread_ts, "assistant", help_msg)
        tracked_response = help_msg

    elif intent == "greeting":
        greeting = reply_text or (
            f"<@{user}> Hey there! :wave: I'm ready to help you create "
            "a Product Requirements Document. Just give me a product idea "
            "and I'll get started!"
        )
        if not greeting.startswith(f"<@{user}>"):
            greeting = f"<@{user}> {greeting}"
        send_tool.run(channel=channel, text=greeting, thread_ts=thread_ts)
        _append_to_thread(channel, thread_ts, "assistant", greeting)
        tracked_response = greeting

    elif intent == "create_prd":
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
            _kick_off_prd_flow(
                channel=channel,
                thread_ts=thread_ts,
                user=user,
                idea=idea,
                event_ts=event_ts,
                interactive=interactive,
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
    try:
        log_interaction(
            source="slack",
            user_message=clean_text,
            intent=intent,
            agent_response=tracked_response,
            idea=idea,
            run_id=tracked_run_id,
            channel=channel,
            thread_ts=thread_ts,
            user_id=user,
            conversation_history=history or None,
            metadata=tracked_metadata,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log agent interaction", exc_info=True)


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
) -> None:
    """Start a PRD flow from a Slack interaction.

    When *interactive* is ``True``, the flow mirrors the CLI experience:
    refinement mode choice, idea approval, and requirements approval are
    all presented as Block Kit button prompts in the thread before
    sections are auto-generated.

    When ``False`` (the default), the flow runs with ``auto_approve=True``
    as before.
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
            name=f"slack-prd-interactive-{run_id}",
            daemon=True,
        )
    else:
        t = threading.Thread(
            target=_run_slack_prd_flow,
            args=(run_id, idea, channel, thread_ts),
            name=f"slack-prd-{run_id}",
            daemon=True,
        )
    t.start()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_app_mention(event: dict) -> None:
    channel = event.get("channel", "")
    text = event.get("text", "")
    user = event.get("user", "")
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    event_ts = event.get("ts", "")
    clean_text = re.sub(r"<@[^>]+>\s*", "", text).strip()
    _interpret_and_act(channel, thread_ts, user, clean_text, event_ts)


def _handle_thread_message(event: dict) -> None:
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

        event_id = payload.get("event_id", "")
        if _is_duplicate_event(event_id):
            logger.debug("Duplicate event_id %s — ignoring", event_id)
            return JSONResponse({"ok": True})

        if event_subtype == "member_joined_channel":
            joined_user = event.get("user", "")
            channel_id = event.get("channel", "")
            bot_id = _get_bot_user_id()
            if bot_id and joined_user == bot_id:
                logger.info("Bot joined channel %s – posting intro", channel_id)
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, _post_intro, channel_id)
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

        if event_subtype == "message" and event.get("thread_ts"):
            channel = event.get("channel", "")
            thread_ts = event.get("thread_ts", "")
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

            if has_conversation or has_interactive:
                logger.info(
                    "Thread follow-up in %s/%s from %s%s",
                    channel, thread_ts, event.get("user"),
                    " (interactive)" if has_interactive else "",
                )
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, _handle_thread_message, event)
            return JSONResponse({"ok": True})

        logger.debug("Unhandled event subtype: %s", event_subtype)
        return JSONResponse({"ok": True})

    logger.debug("Unhandled payload type: %s", event_type)
    return JSONResponse({"ok": True})
