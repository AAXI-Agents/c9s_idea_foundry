"""Thread conversation state and event deduplication for Slack events.

Manages in-memory caches for:
* Per-thread conversation history (10-minute TTL, max 20 messages)
* Event deduplication (5-minute TTL to handle Slack retries)
* Bot user-ID resolution (cached after first call)
"""

from __future__ import annotations

import threading
import time

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Bot identity cache
# ---------------------------------------------------------------------------

_bot_user_id: str | None = None


def get_bot_user_id() -> str | None:
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


def get_thread_history(channel: str, thread_ts: str) -> list[dict]:
    """Return a copy of the conversation history for a thread."""
    with _thread_lock:
        _expire_threads()
        return list(_thread_conversations.get((channel, thread_ts), []))


def append_to_thread(channel: str, thread_ts: str, role: str, content: str) -> None:
    """Append a message to the thread history (max 20 messages kept)."""
    with _thread_lock:
        key = (channel, thread_ts)
        if key not in _thread_conversations:
            _thread_conversations[key] = []
        _thread_conversations[key].append({"role": role, "content": content})
        _thread_last_active[key] = time.time()
        if len(_thread_conversations[key]) > 20:
            _thread_conversations[key] = _thread_conversations[key][-20:]


def touch_thread(channel: str, thread_ts: str) -> None:
    """Refresh the TTL for a thread without appending a message.

    Ensures the thread stays in the conversation cache so the bot
    keeps processing messages even if no ``append_to_thread`` call
    has occurred yet for this message (e.g. pending-state handlers
    that don't go through ``interpret_and_act``).
    """
    with _thread_lock:
        key = (channel, thread_ts)
        if key not in _thread_conversations:
            _thread_conversations[key] = []
        _thread_last_active[key] = time.time()


def has_thread_conversation(channel: str, thread_ts: str) -> bool:
    """Return ``True`` if there is an active conversation for the thread."""
    with _thread_lock:
        _expire_threads()
        return (channel, thread_ts) in _thread_conversations


def _expire_threads() -> None:
    """Remove threads older than the TTL.  Must be called under ``_thread_lock``."""
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


def is_duplicate_event(event_id: str) -> bool:
    """Return ``True`` if this event ID was already processed recently."""
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
