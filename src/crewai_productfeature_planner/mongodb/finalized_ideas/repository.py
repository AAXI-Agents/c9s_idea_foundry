"""Repository for the ``finalizeIdeas`` collection.

Stores the approved final PRD documents (Markdown + Confluence XHTML).
"""

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.mongodb.client import get_db

logger = get_logger(__name__)

FINALIZED_COLLECTION = "finalizeIdeas"


def save_finalized(
    run_id: str,
    idea: str,
    iteration: int,
    final_prd: str,
    confluence_xhtml: str = "",
    **extra: Any,
) -> str | None:
    """Persist the approved final PRD to ``finalizeIdeas``.

    Args:
        run_id: Unique flow run identifier.
        idea: The original feature idea.
        iteration: Total number of iterations.
        final_prd: Final PRD in Markdown.
        confluence_xhtml: XHTML version ready for Confluence API.
        **extra: Additional fields to store.

    Returns:
        The inserted document ``_id`` as a string, or ``None`` on failure.
    """
    doc = {
        "run_id": run_id,
        "idea": idea,
        "total_iterations": iteration,
        "final_prd": final_prd,
        "confluence_xhtml": confluence_xhtml,
        "finalized_at": datetime.now(timezone.utc),
        **extra,
    }
    try:
        result = get_db()[FINALIZED_COLLECTION].insert_one(doc)
        logger.info(
            "[MongoDB] Finalized PRD for run_id=%s (doc_id=%s)",
            run_id,
            result.inserted_id,
        )
        return str(result.inserted_id)
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to finalize PRD for run_id=%s: %s",
            run_id,
            exc,
        )
        return None
