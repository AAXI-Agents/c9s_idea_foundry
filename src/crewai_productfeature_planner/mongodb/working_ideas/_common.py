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


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
