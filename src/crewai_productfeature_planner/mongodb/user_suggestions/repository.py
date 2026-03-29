"""Repository for the ``userSuggestions`` collection.

Tracks ambiguous user intents and clarification requests so the system
can learn from unrecognised patterns over time.

Standard document schema
------------------------
::

    {
        "suggestion_id":          str,              # unique identifier (UUID hex)
        "user_id":                str | None,       # Slack user ID
        "project_id":             str | None,       # FK → projectConfig.project_id
        "channel":                str | None,       # Slack channel
        "thread_ts":              str | None,       # Slack thread timestamp
        "user_message":           str,              # the raw user message
        "agent_interpretation":   str,              # how the agent understood it
        "suggestion_type":        str,              # "clarification_needed" | "unknown_intent"
        "resolved":               bool,             # whether the user clarified
        "resolved_intent":        str | None,       # final resolved intent (after clarification)
        "created_at":             datetime (UTC),   # when the suggestion was logged
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

USER_SUGGESTIONS_COLLECTION = "userSuggestions"


def log_suggestion(
    *,
    user_message: str,
    agent_interpretation: str,
    suggestion_type: str = "clarification_needed",
    user_id: str | None = None,
    project_id: str | None = None,
    channel: str | None = None,
    thread_ts: str | None = None,
) -> str | None:
    """Insert a new user suggestion document.

    Returns the ``suggestion_id`` on success, or ``None`` on failure.
    """
    suggestion_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)

    doc: dict[str, Any] = {
        "suggestion_id": suggestion_id,
        "user_id": user_id,
        "project_id": project_id,
        "channel": channel,
        "thread_ts": thread_ts,
        "user_message": user_message,
        "agent_interpretation": agent_interpretation,
        "suggestion_type": suggestion_type,
        "resolved": False,
        "resolved_intent": None,
        "created_at": now,
    }

    try:
        db = get_db()
        db[USER_SUGGESTIONS_COLLECTION].insert_one(doc)
        logger.info(
            "[UserSuggestions] Logged suggestion %s (type=%s, user=%s)",
            suggestion_id, suggestion_type, user_id,
        )
        return suggestion_id
    except PyMongoError:
        logger.warning(
            "[UserSuggestions] Failed to log suggestion for user=%s",
            user_id, exc_info=True,
        )
        return None


def find_suggestions_by_project(
    project_id: str,
    *,
    resolved: bool | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return recent suggestions for a project.

    Args:
        project_id: The project to query.
        resolved: If set, filter by resolved status.
        limit: Max documents to return.
    """
    query: dict[str, Any] = {"project_id": project_id}
    if resolved is not None:
        query["resolved"] = resolved
    try:
        db = get_db()
        cursor = (
            db[USER_SUGGESTIONS_COLLECTION]
            .find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError:
        logger.warning(
            "[UserSuggestions] Failed to query suggestions for project=%s",
            project_id, exc_info=True,
        )
        return []
