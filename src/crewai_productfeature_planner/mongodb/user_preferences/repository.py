"""CRUD operations for the ``userPreferences`` collection."""

from __future__ import annotations

from datetime import datetime, timezone

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

USER_PREFERENCES_COLLECTION = "userPreferences"

# Fields that can be set/updated by the user.
_EDITABLE_FIELDS = frozenset({
    "display_name",
    "default_project_id",
    "timezone",
    "notification_preferences",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_preferences(user_id: str) -> dict | None:
    """Return the preferences document for *user_id*, or ``None``."""
    try:
        doc = get_db()[USER_PREFERENCES_COLLECTION].find_one(
            {"user_id": user_id}, {"_id": 0},
        )
        return doc
    except PyMongoError:
        logger.exception("[UserPrefs] Failed to read prefs for user_id=%s", user_id)
        return None


def upsert_preferences(user_id: str, updates: dict) -> dict | None:
    """Create or update preferences for *user_id*.

    Only fields in ``_EDITABLE_FIELDS`` are accepted — unknown keys
    are silently dropped.

    Returns the updated document, or ``None`` on error.
    """
    filtered = {k: v for k, v in updates.items() if k in _EDITABLE_FIELDS}
    if not filtered:
        return get_preferences(user_id)

    now = _now_iso()
    filtered["updated_at"] = now

    try:
        result = get_db()[USER_PREFERENCES_COLLECTION].find_one_and_update(
            {"user_id": user_id},
            {
                "$set": filtered,
                "$setOnInsert": {"user_id": user_id, "created_at": now},
            },
            upsert=True,
            return_document=True,
            projection={"_id": 0},
        )
        logger.info(
            "[UserPrefs] Upserted prefs for user_id=%s fields=%s",
            user_id, list(filtered.keys()),
        )
        return result
    except PyMongoError:
        logger.exception("[UserPrefs] Failed to upsert prefs for user_id=%s", user_id)
        return None
