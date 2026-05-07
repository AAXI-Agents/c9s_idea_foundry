"""Project stats helpers — compute idea counts from workingIdeas.

Provides batch and single-project lookups for ideas_in_progress
and features_completed counts used by GET /projects endpoints.
"""

from __future__ import annotations

from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

#: Statuses considered "in progress" for the ideas count.
_IN_PROGRESS_STATUSES = ["inprogress", "paused"]


async def compute_project_stats_batch(
    project_ids: list[str],
    tenant_filter: dict[str, Any],
) -> dict[str, tuple[int, int]]:
    """Batch-compute (ideas_in_progress, features_completed) per project.

    Uses a single aggregation pipeline on the ``workingIdeas`` collection
    to avoid N+1 queries.

    Args:
        project_ids: List of project_id strings to compute stats for.
        tenant_filter: Pre-built tenant filter dict for data isolation.

    Returns:
        Mapping of ``project_id`` → ``(ideas_in_progress, features_completed)``.
        Projects with no matching ideas are absent from the dict.
    """
    if not project_ids:
        return {}

    from crewai_productfeature_planner.mongodb.async_client import get_async_db

    db = get_async_db()
    coll = db["workingIdeas"]

    pipeline: list[dict[str, Any]] = [
        {
            "$match": {
                "project_id": {"$in": project_ids},
                "status": {"$in": _IN_PROGRESS_STATUSES + ["completed"]},
                **tenant_filter,
            },
        },
        {
            "$group": {
                "_id": "$project_id",
                "in_progress": {
                    "$sum": {
                        "$cond": [
                            {"$in": ["$status", _IN_PROGRESS_STATUSES]},
                            1,
                            0,
                        ],
                    },
                },
                "completed": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "completed"]}, 1, 0],
                    },
                },
            },
        },
    ]

    results: dict[str, tuple[int, int]] = {}
    try:
        async for doc in coll.aggregate(pipeline):
            results[doc["_id"]] = (doc["in_progress"], doc["completed"])
    except Exception as exc:
        logger.error(
            "[Projects] Failed to compute batch stats for %d projects: %s",
            len(project_ids),
            exc,
            exc_info=True,
        )
    return results


async def compute_single_project_stats(
    project_id: str,
    tenant_filter: dict[str, Any],
) -> tuple[int, int]:
    """Compute (ideas_in_progress, features_completed) for one project.

    Args:
        project_id: The project to query.
        tenant_filter: Pre-built tenant filter dict for data isolation.

    Returns:
        Tuple of ``(ideas_in_progress, features_completed)``.
    """
    from crewai_productfeature_planner.mongodb.async_client import get_async_db

    db = get_async_db()
    coll = db["workingIdeas"]

    base_query: dict[str, Any] = {"project_id": project_id, **tenant_filter}

    try:
        in_progress = await coll.count_documents(
            {**base_query, "status": {"$in": _IN_PROGRESS_STATUSES}},
        )
        completed = await coll.count_documents(
            {**base_query, "status": "completed"},
        )
        return (in_progress, completed)
    except Exception as exc:
        logger.error(
            "[Projects] Failed to compute stats for project_id=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return (0, 0)
