"""Repository for the ``companyActivity`` collection.

Tracks real-time agent activity events for the Company Dashboard:
run starts/completions, token usage, approvals, errors, etc.

Standard document schema
------------------------
::

    {
        "event_id":         str,              # unique identifier (UUID hex)
        "event_type":       str,              # run_started | run_completed | run_failed |
                                              # approval_requested | approval_given |
                                              # budget_warning | error | status_change
        "agent_id":         str,              # FK → agentRegistry
        "run_id":           str | None,       # FK → crewJobs
        "session_id":       str | None,       # FK → ideationSessions
        "department":       str,              # product | engineering | operations | ideation
        "description":      str,              # human-readable event summary
        "metadata":         dict,             # event-type-specific payload
        "cost_usd":         float | None,     # cost for this event (if applicable)
        "tokens_used":      int | None,       # tokens for this event (if applicable)
        "enterprise_id":    str | None,       # tenant isolation
        "organization_id":  str | None,       # tenant isolation
        "created_at":       str,              # ISO UTC
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

COMPANY_ACTIVITY_COLLECTION = "companyActivity"


# ── helpers ──────────────────────────────────────────────────────────


def _col():
    return get_db()[COMPANY_ACTIVITY_COLLECTION]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── write ────────────────────────────────────────────────────────────


def log_event(
    event_type: str,
    agent_id: str,
    department: str,
    description: str,
    *,
    run_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    cost_usd: float | None = None,
    tokens_used: int | None = None,
    enterprise_id: str | None = None,
    organization_id: str | None = None,
) -> str | None:
    """Log a new company activity event.

    Returns the event_id on success, None on failure.
    """
    event_id = uuid.uuid4().hex

    doc = {
        "event_id": event_id,
        "event_type": event_type,
        "agent_id": agent_id,
        "run_id": run_id,
        "session_id": session_id,
        "department": department,
        "description": description,
        "metadata": metadata or {},
        "cost_usd": cost_usd,
        "tokens_used": tokens_used,
        "enterprise_id": enterprise_id,
        "organization_id": organization_id,
        "created_at": _now(),
    }

    try:
        _col().insert_one(doc)
        return event_id
    except PyMongoError:
        logger.exception(
            "[CompanyActivity] Failed to log event type=%s agent=%s",
            event_type, agent_id,
        )
        return None


# ── read ─────────────────────────────────────────────────────────────


def list_events(
    *,
    event_type: str | None = None,
    agent_id: str | None = None,
    department: str | None = None,
    organization_id: str | None = None,
    limit: int = 50,
    skip: int = 0,
) -> list[dict[str, Any]]:
    """List activity events with optional filtering.

    Results are sorted by created_at descending (most recent first).
    """
    query: dict[str, Any] = {}
    if event_type:
        query["event_type"] = event_type
    if agent_id:
        query["agent_id"] = agent_id
    if department:
        query["department"] = department
    if organization_id:
        query["organization_id"] = organization_id

    try:
        cursor = (
            _col()
            .find(query, {"_id": 0})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError:
        logger.exception("[CompanyActivity] Failed to list events")
        return []


def count_events(
    *,
    event_type: str | None = None,
    agent_id: str | None = None,
    department: str | None = None,
    organization_id: str | None = None,
) -> int:
    """Count events matching the given filters."""
    query: dict[str, Any] = {}
    if event_type:
        query["event_type"] = event_type
    if agent_id:
        query["agent_id"] = agent_id
    if department:
        query["department"] = department
    if organization_id:
        query["organization_id"] = organization_id

    try:
        return _col().count_documents(query)
    except PyMongoError:
        logger.exception("[CompanyActivity] Failed to count events")
        return 0


def get_agent_activity(
    agent_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get recent activity for a specific agent."""
    try:
        cursor = (
            _col()
            .find({"agent_id": agent_id}, {"_id": 0})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError:
        logger.exception(
            "[CompanyActivity] Failed to get agent activity agent=%s", agent_id,
        )
        return []


def get_recent_events(
    organization_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get the most recent events (for real-time feed)."""
    query: dict[str, Any] = {}
    if organization_id:
        query["organization_id"] = organization_id

    try:
        cursor = (
            _col()
            .find(query, {"_id": 0})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError:
        logger.exception("[CompanyActivity] Failed to get recent events")
        return []


def get_department_stats(
    organization_id: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate event counts and costs by department."""
    match_stage: dict[str, Any] = {}
    if organization_id:
        match_stage["organization_id"] = organization_id

    pipeline: list[dict[str, Any]] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$group": {
                "_id": "$department",
                "event_count": {"$sum": 1},
                "total_cost_usd": {
                    "$sum": {"$ifNull": ["$cost_usd", 0]}
                },
                "total_tokens": {
                    "$sum": {"$ifNull": ["$tokens_used", 0]}
                },
                "last_event_at": {"$max": "$created_at"},
            }
        },
        {"$sort": {"event_count": -1}},
    ])

    try:
        results = list(_col().aggregate(pipeline))
        return [
            {
                "department": r["_id"],
                "event_count": r["event_count"],
                "cost_usd": round(r["total_cost_usd"], 4),
                "tokens": r["total_tokens"],
                "last_event_at": r["last_event_at"],
            }
            for r in results
        ]
    except PyMongoError:
        logger.exception("[CompanyActivity] Failed to get department stats")
        return []
