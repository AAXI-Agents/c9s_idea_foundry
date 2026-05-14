"""Repository for the ``enterpriseSettings`` collection.

Stores enterprise-wide configuration settings. One document per
enterprise. Supports dynamic updates without server restart.

Document schema::

    {
        "enterprise_id":            str,    # primary key — one per enterprise
        "workspace_name":           str,    # enterprise display name
        "log_level":                str,    # DEBUG/INFO/WARNING/ERROR
        "agent_toggles":            dict,   # {agent_slug: bool}
        "agent_concurrency":        int,    # max parallel agent executions
        "agent_recommendations":    int,    # recommendations per ideation cycle
        "agent_suggestions":        int,    # suggestions per ideation cycle
        "agent_flow_iteration":     int,    # max flow iterations
        "enterprise_seat_capacity": int,    # max seats
        "github_repo_enabled":      bool,   # global GitHub repo feature toggle
        "agent_label_mappings":     list,   # [{jira_label, agent_slug, display_name, description}]
        "created_at":               str,    # ISO-8601
        "updated_at":               str,    # ISO-8601
    }

Indexes:
    - unique on ``enterprise_id``
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

ENTERPRISE_SETTINGS_COLLECTION = "enterpriseSettings"

# Default settings for newly-created enterprise records.
_DEFAULTS: dict[str, Any] = {
    "workspace_name": "",
    "log_level": "INFO",
    "agent_toggles": {},
    "agent_concurrency": 3,
    "agent_recommendations": 3,
    "agent_suggestions": 3,
    "agent_flow_iteration": 2,
    "enterprise_seat_capacity": 10,
    "github_repo_enabled": False,
    "agent_label_mappings": [],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_enterprise_settings(enterprise_id: str) -> dict[str, Any]:
    """Get settings for an enterprise. Creates with defaults if not exists."""
    db = get_db()
    coll = db[ENTERPRISE_SETTINGS_COLLECTION]

    try:
        doc = coll.find_one({"enterprise_id": enterprise_id}, {"_id": 0})
        if doc:
            return doc

        # First access — initialise with defaults
        now = _now_iso()
        doc = {
            "enterprise_id": enterprise_id,
            **_DEFAULTS,
            "created_at": now,
            "updated_at": now,
        }
        coll.insert_one(doc)
        doc.pop("_id", None)
        logger.info(
            "[EnterpriseSettings] Created default settings for enterprise_id=%s",
            enterprise_id,
        )
        return doc
    except PyMongoError:
        logger.error(
            "[EnterpriseSettings] Failed to get settings for enterprise_id=%s",
            enterprise_id,
            exc_info=True,
        )
        # Return defaults in-memory if DB is unreachable
        return {"enterprise_id": enterprise_id, **_DEFAULTS}


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_enterprise_settings(
    enterprise_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Patch enterprise settings. Only provided fields are updated.

    Returns the full updated document.
    """
    db = get_db()
    coll = db[ENTERPRISE_SETTINGS_COLLECTION]

    # Ensure the document exists (upsert on first write).
    now = _now_iso()
    updates["updated_at"] = now

    # Strip fields that shouldn't be user-writable.
    updates.pop("enterprise_id", None)
    updates.pop("created_at", None)
    updates.pop("_id", None)

    try:
        result = coll.find_one_and_update(
            {"enterprise_id": enterprise_id},
            {
                "$set": updates,
                "$setOnInsert": {
                    "enterprise_id": enterprise_id,
                    "created_at": now,
                    **{k: v for k, v in _DEFAULTS.items() if k not in updates},
                },
            },
            upsert=True,
            return_document=True,
        )
        if result:
            result.pop("_id", None)
        logger.info(
            "[EnterpriseSettings] Updated settings for enterprise_id=%s fields=%s",
            enterprise_id,
            list(updates.keys()),
        )
        return result or {"enterprise_id": enterprise_id, **_DEFAULTS}
    except PyMongoError:
        logger.error(
            "[EnterpriseSettings] Failed to update settings for enterprise_id=%s",
            enterprise_id,
            exc_info=True,
        )
        raise


# ---------------------------------------------------------------------------
# Index setup (called from setup_mongodb.py)
# ---------------------------------------------------------------------------


def ensure_indexes() -> None:
    """Create indexes for the enterpriseSettings collection."""
    db = get_db()
    coll = db[ENTERPRISE_SETTINGS_COLLECTION]
    coll.create_index("enterprise_id", unique=True, name="ix_enterprise_id_unique")
    logger.debug("[EnterpriseSettings] Indexes ensured")
