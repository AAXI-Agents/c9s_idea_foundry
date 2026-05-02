"""Shared constants and helpers for the ``workingIdeas`` sub-modules.

Centralises ``get_db``, the collection name, logger, and ``_now_iso()``
so every sub-module can import them from one place.  Crucially, tests
only need to patch ``_common.get_db`` — sub-modules that access it via
``_common.get_db()`` (attribute lookup on the module object) will see
the patched version at call time.
"""

from __future__ import annotations

from datetime import datetime, timezone

from crewai_productfeature_planner.mongodb.client import get_db  # noqa: F401
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

WORKING_COLLECTION = "workingIdeas"

#: Terminal statuses that release the dedup key.
_TERMINAL_STATUSES = frozenset({"archived", "completed", "failed", "deleted"})


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def build_active_idea_key(
    organization_id: str | None,
    project_id: str | None,
    idea_normalized: str | None,
) -> str | None:
    """Compute the sparse unique dedup key for active ideas.

    Returns a composite string ``"{org}:{project}:{idea_normalized}"``
    when all components are present, or ``None`` otherwise (documents
    with ``None`` are excluded from the sparse unique index).
    """
    if not project_id or not idea_normalized:
        return None
    org = organization_id or ""
    return f"{org}:{project_id}:{idea_normalized}"
