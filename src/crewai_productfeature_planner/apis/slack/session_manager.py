"""Slack project-session state manager.

Provides the bridge between Slack interactions and the ``userSession``
MongoDB collection.  The manager enforces the "one active session per
user" invariant and supplies helpers consumed by the events router and
interactive handlers.

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

# Users awaiting project-name reply after clicking "Create New Project"
# Maps user_id → {"channel": ..., "thread_ts": ...}
_pending_project_creates: dict[str, dict[str, str]] = {}


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
