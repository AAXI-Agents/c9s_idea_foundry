"""Slack project-session state manager.

Provides the bridge between Slack interactions and the ``userSession``
MongoDB collection.  The manager enforces the "one active session per
user" invariant and supplies helpers consumed by the events router and
interactive handlers.

Session scoping
---------------

* **DM channels** (channel ID starts with ``D``) — each user has a
  private session.  The user can freely switch projects or configure
  memory.
* **Public / private channels** (channel ID starts with ``C`` or ``G``)
  — the *channel* has one shared session.  Only workspace **admins**
  (``is_admin`` / ``is_owner``) may select a project or configure
  memory for the channel.  All users in the channel use the
  channel-level project memory.

Typical lifecycle
-----------------

1. User @mentions the bot → events router calls
   :func:`ensure_project_context`.
2. If there is **no** active session → the orchestrator posts a project-
   selection prompt (create new / choose existing).
3. If there **is** an active session → the orchestrator reminds the user
   and offers to continue or switch projects.
4. Once a project is selected, :func:`activate_project` creates the
   ``userSession`` document and stores the ``project_id`` in an
   in-memory cache for fast lookups.
5. When the user explicitly ends/switches the session,
   :func:`deactivate_session` closes the MongoDB document and clears
   the cache.
"""

from __future__ import annotations

import threading
from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()

# Fast in-memory lookup: user_id → active session dict
# (mirrors MongoDB for the current process lifetime)
_active_sessions: dict[str, dict[str, Any]] = {}

# Channel-level sessions (used for public/private channels, not DMs).
# Maps channel_id → active session dict
_channel_sessions: dict[str, dict[str, Any]] = {}

# Users awaiting project-name reply after clicking "Create New Project"
# Maps user_id → {"channel": ..., "thread_ts": ...}
_pending_project_creates: dict[str, dict[str, str]] = {}

# Users in the multi-step project-setup wizard (confluence / jira keys).
# Maps user_id → {"channel": ..., "thread_ts": ..., "project_id": ...,
#                  "project_name": ..., "step": "confluence_space_key" | ...,
#                  "confluence_space_key": ..., "jira_project_key": ...,
#                  "confluence_parent_id": ...}
_pending_project_setup: dict[str, dict[str, str]] = {}

# Users awaiting a memory-category reply after clicking a memory button.
# Maps user_id → {"channel": ..., "thread_ts": ...,
#                  "category": "idea_iteration"|"knowledge"|"tools",
#                  "project_id": ...}
_pending_memory_entries: dict[str, dict[str, str]] = {}

# Cache for Slack admin status checks (user_id → (is_admin, timestamp)).
# TTL-based: entries expire after _ADMIN_CACHE_TTL_SECONDS so role
# changes are picked up without a server restart.
_ADMIN_CACHE_TTL_SECONDS = 300  # 5 minutes
_admin_cache: dict[str, tuple[bool, float]] = {}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_cached_session(user_id: str) -> dict[str, Any] | None:
    """Return the in-memory active session for *user_id*, or ``None``."""
    with _lock:
        return _active_sessions.get(user_id)


def activate_project(
    *,
    user_id: str,
    channel: str,
    project_id: str,
    project_name: str,
) -> str | None:
    """Create a new ``userSession`` document and cache it.

    Any previously active session for the user is ended first.

    Returns:
        The new ``session_id``, or ``None`` on failure.
    """
    from crewai_productfeature_planner.mongodb.user_session import start_session

    session_id = start_session(
        user_id=user_id,
        channel=channel,
        project_id=project_id,
        project_name=project_name,
    )
    if session_id:
        with _lock:
            _active_sessions[user_id] = {
                "session_id": session_id,
                "user_id": user_id,
                "channel": channel,
                "project_id": project_id,
                "project_name": project_name,
                "active": True,
            }
        logger.info(
            "[SessionManager] Activated project '%s' for user %s",
            project_name,
            user_id,
        )
    return session_id


def deactivate_session(user_id: str) -> int:
    """End the user's active session in MongoDB and clear the cache.

    Returns:
        Number of sessions ended (0 or 1).
    """
    from crewai_productfeature_planner.mongodb.user_session import end_active_session

    count = end_active_session(user_id=user_id)
    with _lock:
        _active_sessions.pop(user_id, None)
    if count:
        logger.info("[SessionManager] Deactivated session for user %s", user_id)
    return count


def ensure_session_loaded(user_id: str) -> dict[str, Any] | None:
    """Ensure the in-memory cache reflects the database.

    If the cache is empty but the user has an active session in Mongo,
    load it.  Returns the active session dict or ``None``.
    """
    with _lock:
        cached = _active_sessions.get(user_id)
    if cached:
        return cached

    from crewai_productfeature_planner.mongodb.user_session import get_active_session

    session = get_active_session(user_id)
    if session and session.get("active"):
        with _lock:
            _active_sessions[user_id] = session
        return session
    return None


def get_project_id_for_user(user_id: str) -> str | None:
    """Return the ``project_id`` from the user's active session, or ``None``."""
    session = ensure_session_loaded(user_id)
    return session.get("project_id") if session else None


# ---------------------------------------------------------------------------
# DM / channel context helpers
# ---------------------------------------------------------------------------


def is_dm(channel_id: str) -> bool:
    """Return ``True`` when *channel_id* represents a direct message.

    Slack DM channel IDs start with ``D``.
    """
    return bool(channel_id) and channel_id.startswith("D")


def is_channel_admin(user_id: str) -> bool:
    """Check whether *user_id* is a Slack workspace admin or owner.

    Results are cached for the lifetime of the process so subsequent
    calls avoid hitting the Slack API.
    """
    import time as _time

    with _lock:
        cached = _admin_cache.get(user_id)
    if cached is not None:
        is_admin_cached, cached_at = cached
        if _time.time() - cached_at < _ADMIN_CACHE_TTL_SECONDS:
            return is_admin_cached
        # TTL expired — fall through to re-check
        logger.debug("[SessionManager] Admin cache expired for %s — re-checking", user_id)

    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        logger.warning("[SessionManager] No Slack client — cannot verify admin for %s", user_id)
        return False

    try:
        resp = client.users_info(user=user_id)
        if resp.get("ok"):
            user_data = resp.get("user", {})
            result = bool(user_data.get("is_admin") or user_data.get("is_owner"))
            with _lock:
                _admin_cache[user_id] = (result, _time.time())
            logger.debug("[SessionManager] Admin check user=%s → %s", user_id, result)
            return result
    except Exception as exc:
        logger.warning("[SessionManager] Admin check failed for %s: %s", user_id, exc)

    return False


# ---------------------------------------------------------------------------
# Channel-level sessions (for public / private channels)
# ---------------------------------------------------------------------------


def activate_channel_project(
    *,
    channel_id: str,
    project_id: str,
    project_name: str,
    activated_by: str,
) -> str | None:
    """Activate a project for a channel.

    Only one project can be active per channel at a time.  The
    ``activated_by`` field records which admin selected the project.

    Returns the new ``session_id``, or ``None`` on failure.
    """
    from crewai_productfeature_planner.mongodb.user_session import (
        start_channel_session,
    )

    session_id = start_channel_session(
        channel_id=channel_id,
        project_id=project_id,
        project_name=project_name,
        activated_by=activated_by,
    )
    if session_id:
        with _lock:
            _channel_sessions[channel_id] = {
                "session_id": session_id,
                "channel": channel_id,
                "project_id": project_id,
                "project_name": project_name,
                "activated_by": activated_by,
                "active": True,
            }
        logger.info(
            "[SessionManager] Activated channel project '%s' for %s (by %s)",
            project_name, channel_id, activated_by,
        )
    return session_id


def deactivate_channel_session(channel_id: str) -> int:
    """End the active channel session and clear the cache.

    Returns the number of sessions ended (0 or 1).
    """
    from crewai_productfeature_planner.mongodb.user_session import (
        end_channel_session,
    )

    count = end_channel_session(channel_id=channel_id)
    with _lock:
        _channel_sessions.pop(channel_id, None)
    if count:
        logger.info("[SessionManager] Deactivated channel session for %s", channel_id)
    return count


def get_channel_session(channel_id: str) -> dict[str, Any] | None:
    """Return the cached channel session, or ``None``."""
    with _lock:
        return _channel_sessions.get(channel_id)


def ensure_channel_session_loaded(channel_id: str) -> dict[str, Any] | None:
    """Cache-through load: return cached channel session or fetch from MongoDB."""
    with _lock:
        cached = _channel_sessions.get(channel_id)
    if cached:
        return cached

    from crewai_productfeature_planner.mongodb.user_session import (
        get_active_channel_session,
    )

    session = get_active_channel_session(channel_id)
    if session and session.get("active"):
        with _lock:
            _channel_sessions[channel_id] = session
        return session
    return None


def get_channel_project_id(channel_id: str) -> str | None:
    """Return the ``project_id`` from the channel's active session, or ``None``."""
    session = ensure_channel_session_loaded(channel_id)
    return session.get("project_id") if session else None


# ---------------------------------------------------------------------------
# Context-aware helpers (auto-dispatch DM vs channel)
# ---------------------------------------------------------------------------


def get_context_session(user_id: str, channel_id: str) -> dict[str, Any] | None:
    """Return the active session for the appropriate context.

    * DM → user session
    * Channel → channel session
    """
    if is_dm(channel_id):
        return ensure_session_loaded(user_id)
    return ensure_channel_session_loaded(channel_id)


def get_context_project_id(user_id: str, channel_id: str) -> str | None:
    """Return the ``project_id`` for the appropriate context."""
    session = get_context_session(user_id, channel_id)
    return session.get("project_id") if session else None


def can_manage_memory(user_id: str, channel_id: str) -> bool:
    """Return ``True`` if the user is allowed to configure memory.

    * In DMs every user can manage their own memory.
    * In channels only workspace admins / owners may do so.
    """
    if is_dm(channel_id):
        return True
    return is_channel_admin(user_id)


# ---------------------------------------------------------------------------
# Pending "Create New Project" tracking
# ---------------------------------------------------------------------------


def mark_pending_create(user_id: str, channel: str, thread_ts: str) -> None:
    """Record that *user_id* has been asked to type a new project name."""
    with _lock:
        _pending_project_creates[user_id] = {
            "channel": channel,
            "thread_ts": thread_ts,
        }


def pop_pending_create(user_id: str) -> dict[str, str] | None:
    """Return and remove the pending-create entry for *user_id*.

    Returns ``None`` if the user has no pending create request.
    """
    with _lock:
        return _pending_project_creates.pop(user_id, None)


def get_pending_create_owner_for_thread(
    channel: str, thread_ts: str,
) -> str | None:
    """Return the user_id that owns a pending create in this thread.

    Returns ``None`` if no user has a pending create for the given
    channel + thread.  Used to reject replies from other users in a
    thread that is waiting for a specific user's project-name input.
    """
    with _lock:
        for uid, entry in _pending_project_creates.items():
            if entry["channel"] == channel and entry["thread_ts"] == thread_ts:
                return uid
    return None


# ---------------------------------------------------------------------------
# Pending "Memory Category Reply" tracking
# ---------------------------------------------------------------------------


def mark_pending_memory(
    user_id: str,
    channel: str,
    thread_ts: str,
    category: str,
    project_id: str,
) -> None:
    """Record that *user_id* is typing memory entries for *category*."""
    with _lock:
        _pending_memory_entries[user_id] = {
            "channel": channel,
            "thread_ts": thread_ts,
            "category": category,
            "project_id": project_id,
        }


def pop_pending_memory(user_id: str) -> dict[str, str] | None:
    """Return and remove the pending-memory entry for *user_id*.

    Returns ``None`` if the user has no pending memory request.
    """
    with _lock:
        return _pending_memory_entries.pop(user_id, None)


# ---------------------------------------------------------------------------
# Pending "Project Setup" wizard tracking
# ---------------------------------------------------------------------------

# The setup steps in order.  After the last step the project is
# finalised and the session starts.
_SETUP_STEPS = (
    "project_name",
    "confluence_space_key",
    "jira_project_key",
)

# Steps used for new project creation (name already collected)
_NEW_PROJECT_START_STEP = "confluence_space_key"


def mark_pending_setup(
    user_id: str,
    channel: str,
    thread_ts: str,
    project_id: str,
    project_name: str,
) -> None:
    """Begin the project-setup wizard for *user_id* (new project).

    Starts at the *second* step (confluence_space_key) because the
    project name was already collected during creation.
    """
    with _lock:
        _pending_project_setup[user_id] = {
            "channel": channel,
            "thread_ts": thread_ts,
            "project_id": project_id,
            "project_name": project_name,
            "step": _NEW_PROJECT_START_STEP,
            "confluence_space_key": "",
            "jira_project_key": "",
        }


def mark_pending_reconfig(
    user_id: str,
    channel: str,
    thread_ts: str,
    project_id: str,
    project_config: dict,
) -> None:
    """Begin a reconfigure wizard for an existing project.

    Starts at ``project_name`` (the first step) and pre-populates
    current values so the user sees them in the prompt.
    """
    with _lock:
        _pending_project_setup[user_id] = {
            "channel": channel,
            "thread_ts": thread_ts,
            "project_id": project_id,
            "project_name": project_config.get("name", ""),
            "step": _SETUP_STEPS[0],
            "confluence_space_key": project_config.get("confluence_space_key", ""),
            "jira_project_key": project_config.get("jira_project_key", ""),
        }


def get_pending_setup(user_id: str) -> dict[str, str] | None:
    """Return the pending setup entry without removing it."""
    with _lock:
        return _pending_project_setup.get(user_id)


def advance_pending_setup(user_id: str, value: str) -> dict[str, str] | None:
    """Store *value* for the current step and advance to the next.

    Returns the updated entry, or ``None`` if the user has no pending
    setup.  When all steps are completed the entry is removed and
    the returned dict will have ``step`` set to ``"done"``.
    """
    with _lock:
        entry = _pending_project_setup.get(user_id)
        if entry is None:
            return None

        current_step = entry["step"]
        entry[current_step] = value

        idx = _SETUP_STEPS.index(current_step)
        if idx + 1 < len(_SETUP_STEPS):
            entry["step"] = _SETUP_STEPS[idx + 1]
        else:
            entry["step"] = "done"
            _pending_project_setup.pop(user_id, None)

        return dict(entry)  # return a snapshot


def pop_pending_setup(user_id: str) -> dict[str, str] | None:
    """Return and remove the pending-setup entry for *user_id*."""
    with _lock:
        return _pending_project_setup.pop(user_id, None)


def has_pending_state(user_id: str) -> bool:
    """Return ``True`` if *user_id* has any pending input state.

    Checks pending project creates, project setup wizard, and pending
    memory entries.  Used by the event router to ensure thread messages
    from users with outstanding prompts are always processed, even
    when the thread conversation cache has expired.
    """
    with _lock:
        return (
            user_id in _pending_project_creates
            or user_id in _pending_project_setup
            or user_id in _pending_memory_entries
        )
