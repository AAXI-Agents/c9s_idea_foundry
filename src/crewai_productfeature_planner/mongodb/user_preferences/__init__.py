"""Repository for the ``userPreferences`` collection.

Stores user-local preferences separate from SSO-managed identity data.
Each user has at most one document keyed by ``user_id``.

Standard document schema
------------------------
::

    {
        "user_id":                   str,              # SSO user_id (unique)
        "display_name":              str | None,       # local override for SSO name
        "default_project_id":        str | None,       # default project for new ideas
        "timezone":                  str | None,       # IANA timezone (e.g. "Asia/Singapore")
        "notification_preferences":  dict | None,      # {"web": bool, "slack": bool}
        "created_at":                str (ISO-8601),
        "updated_at":                str (ISO-8601),
    }
"""

from .repository import (
    USER_PREFERENCES_COLLECTION,
    get_preferences,
    upsert_preferences,
)

__all__ = [
    "USER_PREFERENCES_COLLECTION",
    "get_preferences",
    "upsert_preferences",
]
