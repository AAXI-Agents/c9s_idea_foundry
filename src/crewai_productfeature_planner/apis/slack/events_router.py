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
        else:
            ack_text = (
                f"<@{user}> Got it! :rocket: I'm starting a PRD generation "
                f"flow for:\n> _{idea}_\n\n"
                "I'll post the results here when done."
            )
            send_tool.run(channel=channel, text=ack_text, thread_ts=thread_ts)
            _append_to_thread(channel, thread_ts, "assistant", ack_text)
            _kick_off_prd_flow(
                channel=channel,
                thread_ts=thread_ts,
                user=user,
                idea=idea,
                event_ts=event_ts,
            )

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
) -> None:
    """Start a PRD flow from a Slack interaction."""
    from crewai_productfeature_planner.apis.slack.router import _run_slack_prd_flow
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if client:
        try:
            client.reactions_add(channel=channel, timestamp=event_ts, name="eyes")
        except Exception:
            pass

    run_id = uuid.uuid4().hex[:12]
    import threading
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

    _interpret_and_act(channel, thread_ts, user, clean_text, event_ts)


# ---------------------------------------------------------------------------
# Events endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/slack/events",
    tags=["Slack Events"],
    summary="Slack Events API endpoint",
    response_description="Event acknowledged",
    dependencies=[Depends(verify_slack_request)],
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
            with _thread_lock:
                _expire_threads()
                has_conversation = key in _thread_conversations
            if has_conversation:
                logger.info(
                    "Thread follow-up in %s/%s from %s",
                    channel, thread_ts, event.get("user"),
                )
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, _handle_thread_message, event)
            return JSONResponse({"ok": True})

        logger.debug("Unhandled event subtype: %s", event_subtype)
        return JSONResponse({"ok": True})

    logger.debug("Unhandled payload type: %s", event_type)
    return JSONResponse({"ok": True})
