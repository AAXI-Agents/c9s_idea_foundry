"""Repository for the ``userSession`` collection.

Tracks Slack user project sessions.  A user can have at most **one**
active session at a time.  Sessions are scoped by ``(user_id, channel)``
so the same user in different channels gets separate sessions.

Standard document schema
------------------------
::

    {
        "session_id":       str,              # unique identifier (UUID hex)
        "user_id":          str,              # Slack user ID
        "channel":          str,              # Slack channel where the session lives
        "project_id":       str,              # FK → projectConfig.project_id
        "project_name":     str,              # denormalised for display
        "active":           bool,             # True while the session is open
        "started_at":       str (ISO-8601),   # when the session was created
        "ended_at":         str | None,       # when the session was explicitly ended
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    tenant_fields,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

USER_SESSION_COLLECTION = "userSession"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── write ─────────────────────────────────────────────────────


def start_session(
    *,
    user_id: str,
    channel: str,
    project_id: str,
    project_name: str,
    tenant: TenantContext | None = None,
) -> str | None:
    """Start a new project session for a Slack user.

    If the user already has an active session (in **any** channel),
    it is ended first so that only one session is active at a time.

    Returns:
        The new ``session_id`` on success, or ``None`` on failure.
    """
    # Close any existing active session for this user
    end_active_session(user_id=user_id)

    session_id = uuid.uuid4().hex
    now = _now_iso()

    doc: dict[str, Any] = {
        "session_id": session_id,
        "user_id": user_id,
        "channel": channel,
        "project_id": project_id,
        "project_name": project_name,
        "active": True,
        "started_at": now,
        "ended_at": None,
        **(tenant_fields(tenant) if tenant else {}),
    }

    try:
        get_db()[USER_SESSION_COLLECTION].insert_one(doc)
        logger.info(
            "[UserSession] Started session %s for user=%s project=%s (%s)",
            session_id,
            user_id,
            project_id,
            project_name,
        )
        return session_id
    except PyMongoError as exc:
        logger.error(
            "[UserSession] Failed to start session for user=%s: %s",
            user_id,
            exc,
        )
        return None


def end_active_session(*, user_id: str) -> int:
    """End the user's currently active session (if any).

    Sets ``active=False`` and ``ended_at`` to the current time.

    Returns:
        Number of sessions ended (0 or 1).
    """
    now = _now_iso()
    try:
        result = get_db()[USER_SESSION_COLLECTION].update_one(
            {"user_id": user_id, "active": True},
            {"$set": {"active": False, "ended_at": now}},
        )
        if result.modified_count:
            logger.info(
                "[UserSession] Ended active session for user=%s",
                user_id,
            )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[UserSession] Failed to end session for user=%s: %s",
            user_id,
            exc,
        )
        return 0


def switch_session(
    *,
    user_id: str,
    channel: str,
    project_id: str,
    project_name: str,
) -> str | None:
    """End the current session and start a new one atomically.

    This is a convenience wrapper around :func:`end_active_session` +
    :func:`start_session`.

    Returns:
        The new ``session_id`` on success, or ``None`` on failure.
    """
    return start_session(
        user_id=user_id,
        channel=channel,
        project_id=project_id,
        project_name=project_name,
    )


# ── queries ───────────────────────────────────────────────────


def get_active_session(user_id: str) -> dict[str, Any] | None:
    """Return the user's currently active session, or ``None``.

    There should be at most one active session per user at any time.
    """
    try:
        return get_db()[USER_SESSION_COLLECTION].find_one(
            {"user_id": user_id, "active": True},
            {"_id": 0},
        )
    except PyMongoError as exc:
        logger.error(
            "[UserSession] Failed to get active session for user=%s: %s",
            user_id,
            exc,
        )
        return None


def get_session(session_id: str) -> dict[str, Any] | None:
    """Return a session by its ``session_id``."""
    try:
        return get_db()[USER_SESSION_COLLECTION].find_one(
            {"session_id": session_id},
            {"_id": 0},
        )
    except PyMongoError as exc:
        logger.error(
            "[UserSession] Failed to get session %s: %s",
            session_id,
            exc,
        )
        return None


def list_sessions(
    user_id: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return the user's recent sessions (newest first)."""
    try:
        cursor = (
            get_db()[USER_SESSION_COLLECTION]
            .find({"user_id": user_id}, {"_id": 0})
            .sort("started_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error(
            "[UserSession] Failed to list sessions for user=%s: %s",
            user_id,
            exc,
        )
        return []


# ── Channel sessions ─────────────────────────────────────────
# Channel sessions share the same MongoDB collection but are
# distinguished by ``context_type: "channel"`` and keyed by
# ``channel`` rather than ``user_id``.


def start_channel_session(
    *,
    channel_id: str,
    project_id: str,
    project_name: str,
    activated_by: str,
) -> str | None:
    """Start a project session for a Slack **channel**.

    Any previously active channel session is ended first.

    Returns:
        The new ``session_id``, or ``None`` on failure.
    """
    end_channel_session(channel_id=channel_id)

    session_id = uuid.uuid4().hex
    now = _now_iso()

    doc: dict[str, Any] = {
        "session_id": session_id,
        "context_type": "channel",
        "channel": channel_id,
        "project_id": project_id,
        "project_name": project_name,
        "activated_by": activated_by,
        "active": True,
        "started_at": now,
        "ended_at": None,
    }

    try:
        get_db()[USER_SESSION_COLLECTION].insert_one(doc)
        logger.info(
            "[UserSession] Started channel session %s for channel=%s project=%s (%s) by=%s",
            session_id, channel_id, project_id, project_name, activated_by,
        )
        return session_id
    except PyMongoError as exc:
        logger.error(
            "[UserSession] Failed to start channel session for channel=%s: %s",
            channel_id, exc,
        )
        return None


def end_channel_session(*, channel_id: str) -> int:
    """End the active channel session (if any).

    Returns the number of sessions ended (0 or 1).
    """
    now = _now_iso()
    try:
        result = get_db()[USER_SESSION_COLLECTION].update_one(
            {"channel": channel_id, "context_type": "channel", "active": True},
            {"$set": {"active": False, "ended_at": now}},
        )
        if result.modified_count:
            logger.info(
                "[UserSession] Ended active channel session for channel=%s",
                channel_id,
            )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[UserSession] Failed to end channel session for channel=%s: %s",
            channel_id, exc,
        )
        return 0


def get_active_channel_session(channel_id: str) -> dict[str, Any] | None:
    """Return the channel's currently active session, or ``None``."""
    try:
        return get_db()[USER_SESSION_COLLECTION].find_one(
            {"channel": channel_id, "context_type": "channel", "active": True},
            {"_id": 0},
        )
    except PyMongoError as exc:
        logger.error(
            "[UserSession] Failed to get active channel session for channel=%s: %s",
            channel_id, exc,
        )
        return None
