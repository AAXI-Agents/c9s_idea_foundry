"""Ensure all MongoDB collections and indexes exist.

Called during server startup (step 0 in ``_lifespan``) so any missing
collections or indexes are created before the application begins
processing requests.

Can also be run standalone::

    python -m crewai_productfeature_planner.scripts.setup_mongodb
"""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
    AGENT_INTERACTIONS_COLLECTION,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
    CREW_JOBS_COLLECTION,
)
from crewai_productfeature_planner.mongodb.product_requirements.repository import (
    PRODUCT_REQUIREMENTS_COLLECTION,
)
from crewai_productfeature_planner.mongodb.project_config.repository import (
    PROJECT_CONFIG_COLLECTION,
)
from crewai_productfeature_planner.mongodb.project_memory.repository import (
    PROJECT_MEMORY_COLLECTION,
)
from crewai_productfeature_planner.mongodb.slack_oauth.repository import (
    SLACK_OAUTH_COLLECTION,
)
from crewai_productfeature_planner.mongodb.user_session import (
    USER_SESSION_COLLECTION,
)
from crewai_productfeature_planner.mongodb.user_suggestions import (
    USER_SUGGESTIONS_COLLECTION,
)
from crewai_productfeature_planner.mongodb.user_preferences import (
    USER_PREFERENCES_COLLECTION,
)
from crewai_productfeature_planner.mongodb.working_ideas._common import (
    WORKING_COLLECTION,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Collection → Index definitions ───────────────────────────────────
#
# Each entry maps a collection name to a list of ``IndexModel`` objects.
# ``create_indexes()`` is idempotent — MongoDB silently skips indexes
# that already exist with the same spec.

_COLLECTION_INDEXES: dict[str, list[IndexModel]] = {
    AGENT_INTERACTIONS_COLLECTION: [
        IndexModel([("interaction_id", ASCENDING)], unique=True),
        IndexModel([("created_at", DESCENDING)]),
        IndexModel([("source", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("intent", ASCENDING), ("created_at", DESCENDING)]),
    ],
    CREW_JOBS_COLLECTION: [
        IndexModel([("job_id", ASCENDING)], unique=True),
        IndexModel([("status", ASCENDING), ("queued_at", DESCENDING)]),
    ],
    WORKING_COLLECTION: [
        IndexModel([("run_id", ASCENDING)], unique=True),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("project_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("slack_channel", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
    ],
    PRODUCT_REQUIREMENTS_COLLECTION: [
        IndexModel([("run_id", ASCENDING)], unique=True),
        IndexModel([("status", ASCENDING), ("created_at", ASCENDING)]),
    ],
    PROJECT_CONFIG_COLLECTION: [
        IndexModel([("project_id", ASCENDING)], unique=True),
        IndexModel([("name", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
    ],
    PROJECT_MEMORY_COLLECTION: [
        IndexModel([("project_id", ASCENDING)], unique=True),
    ],
    USER_SESSION_COLLECTION: [
        IndexModel([("session_id", ASCENDING)], unique=True),
        IndexModel([("user_id", ASCENDING), ("active", ASCENDING)]),
        IndexModel([("channel", ASCENDING), ("context_type", ASCENDING), ("active", ASCENDING)]),
    ],
    SLACK_OAUTH_COLLECTION: [
        IndexModel([("team_id", ASCENDING)], unique=True),
    ],
    USER_SUGGESTIONS_COLLECTION: [
        IndexModel([("suggestion_id", ASCENDING)], unique=True),
        IndexModel([("project_id", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
    ],
    USER_PREFERENCES_COLLECTION: [
        IndexModel([("user_id", ASCENDING)], unique=True),
    ],
}

# Flat list of collection names for easy iteration.
ALL_COLLECTIONS: list[str] = list(_COLLECTION_INDEXES.keys())


def ensure_collections() -> int:
    """Create any missing collections and ensure indexes exist.

    Returns the number of collections that were newly created.
    """
    db = get_db()
    existing = set(db.list_collection_names())

    created = 0
    for name, indexes in _COLLECTION_INDEXES.items():
        if name not in existing:
            try:
                db.create_collection(name)
                logger.info("[MongoDB] Created collection: %s", name)
                created += 1
            except PyMongoError:
                logger.exception("[MongoDB] Failed to create collection: %s", name)
                continue

        # Ensure indexes (idempotent — skips existing).
        if indexes:
            try:
                db[name].create_indexes(indexes)
            except PyMongoError:
                logger.exception("[MongoDB] Failed to create indexes on %s", name)

    if created:
        logger.info("[MongoDB] Created %d new collection(s)", created)
    else:
        logger.info("[MongoDB] All %d collections already exist", len(ALL_COLLECTIONS))

    return created


if __name__ == "__main__":
    ensure_collections()
