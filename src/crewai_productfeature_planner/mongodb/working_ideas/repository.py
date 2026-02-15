"""Repository for the ``workingIdeas`` collection.

Stores iteration drafts, critiques, and failure records produced during
the PRD refinement flow.
"""

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.mongodb.client import get_db

logger = get_logger(__name__)

WORKING_COLLECTION = "workingIdeas"


def find_unfinalized() -> list[dict[str, Any]]:
    """Find working ideas that have not been finalized.

    Queries ``workingIdeas`` for distinct ``run_id`` values that do NOT
    appear in ``finalizeIdeas``, then returns the latest document per
    run_id with the idea text and section progress.

    Returns:
        A list of dicts, each containing:
        ``run_id``, ``idea``, ``iteration``, ``created_at``, and ``sections``
        (list of section keys that have drafts).
        Returns an empty list on failure.
    """
    try:
        db = get_db()
        finalized_run_ids = db["finalizeIdeas"].distinct("run_id")

        pipeline = [
            {"$match": {"run_id": {"$nin": finalized_run_ids}, "status": {"$ne": "failed"}}},
            {"$sort": {"created_at": -1}},
            {"$group": {
                "_id": "$run_id",
                "idea": {"$first": "$idea"},
                "iteration": {"$max": "$iteration"},
                "created_at": {"$first": "$created_at"},
                "sections": {"$addToSet": "$section_key"},
            }},
            {"$sort": {"created_at": -1}},
        ]
        results = list(db[WORKING_COLLECTION].aggregate(pipeline))
        runs = []
        for doc in results:
            sections = [s for s in (doc.get("sections") or []) if s]
            runs.append({
                "run_id": doc["_id"],
                "idea": doc.get("idea", ""),
                "iteration": doc.get("iteration", 0),
                "created_at": doc.get("created_at"),
                "sections": sections,
            })
        logger.info("[MongoDB] Found %d unfinalized working idea(s)", len(runs))
        return runs
    except PyMongoError as exc:
        logger.error("[MongoDB] Failed to query unfinalized ideas: %s", exc)
        return []


def get_run_documents(run_id: str) -> list[dict[str, Any]]:
    """Fetch all working documents for a given run_id, sorted by creation time.

    Returns:
        A list of documents sorted by ``created_at`` ascending.
        Returns an empty list on failure.
    """
    try:
        db = get_db()
        docs = list(
            db[WORKING_COLLECTION]
            .find({"run_id": run_id, "status": {"$ne": "failed"}})
            .sort("created_at", 1)
        )
        logger.info("[MongoDB] Fetched %d documents for run_id=%s", len(docs), run_id)
        return docs
    except PyMongoError as exc:
        logger.error("[MongoDB] Failed to fetch documents for run_id=%s: %s", run_id, exc)
        return []


def save_iteration(
    run_id: str,
    idea: str,
    iteration: int,
    draft: str,
    critique: str = "",
    step: str = "",
    **extra: Any,
) -> str | None:
    """Persist a single iteration to ``workingIdeas``.

    Returns:
        The inserted document ``_id`` as a string, or ``None`` on failure.

    Note:
        MongoDB errors are caught and logged so the agent flow is never
        interrupted by a database issue.
    """
    doc = {
        "run_id": run_id,
        "idea": idea,
        "iteration": iteration,
        "step": step,
        "draft": draft,
        "critique": critique,
        "created_at": datetime.now(timezone.utc),
        **extra,
    }
    try:
        result = get_db()[WORKING_COLLECTION].insert_one(doc)
        logger.info(
            "[MongoDB] Saved iteration %d (step=%s) for run_id=%s (doc_id=%s)",
            iteration,
            step or "draft",
            run_id,
            result.inserted_id,
        )
        return str(result.inserted_id)
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save iteration %d for run_id=%s: %s",
            iteration,
            run_id,
            exc,
        )
        return None


def save_failed(
    run_id: str,
    idea: str,
    iteration: int,
    error: str,
    draft: str = "",
    step: str = "",
) -> str | None:
    """Mark a run as failed in ``workingIdeas``.

    Persists a failure record so orphaned working documents can be
    identified and the error is auditable.

    Returns:
        The inserted document ``_id`` as a string, or ``None`` on failure.
    """
    doc = {
        "run_id": run_id,
        "idea": idea,
        "iteration": iteration,
        "step": step,
        "status": "failed",
        "error": error,
        "draft": draft,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = get_db()[WORKING_COLLECTION].insert_one(doc)
        logger.info(
            "[MongoDB] Saved failure record for run_id=%s (doc_id=%s)",
            run_id,
            result.inserted_id,
        )
        return str(result.inserted_id)
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save failure record for run_id=%s: %s",
            run_id,
            exc,
        )
        return None
