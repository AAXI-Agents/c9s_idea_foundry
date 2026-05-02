"""Repository for the ``agentRegistry`` collection.

Tracks all CrewAI agents as a Paperclip-inspired organization with
departments, reporting lines, budgets, and real-time status.

Standard document schema
------------------------
::

    {
        "agent_id":         str,              # unique identifier (e.g. "product_manager")
        "display_name":     str,              # human-readable name
        "department":       str,              # product | engineering | operations | ideation
        "role":             str,              # org chart role (e.g. "Head of Product")
        "title":            str,              # job title
        "reports_to":       str | None,       # parent agent_id in org chart
        "avatar":           str,              # emoji or icon key for UI
        "llm_tier":         str,              # gemini_research | gemini_fast | basic
        "capabilities":     list[str],        # skills/tools available
        "budget": {
            "monthly_token_limit":  int,
            "monthly_cost_limit_usd": float,
            "warning_threshold_pct": int,
            "hard_stop":            bool,
        },
        "status":           str,              # idle | active | paused | error
        "current_task":     dict | None,      # {run_id, step, description, started_at}
        "last_active_at":   str | None,       # ISO UTC timestamp
        "stats": {
            "total_runs":       int,
            "total_tokens":     int,
            "total_cost_usd":   float,
            "month_tokens":     int,
            "month_cost_usd":   float,
            "month_reset_at":   str,          # ISO UTC — first day of current month
        },
        "created_at":       str,              # ISO UTC
        "updated_at":       str,              # ISO UTC
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

AGENT_REGISTRY_COLLECTION = "agentRegistry"


# ── helpers ──────────────────────────────────────────────────────────


def _col():
    return get_db()[AGENT_REGISTRY_COLLECTION]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_month_start() -> str:
    """First instant of the current UTC month."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


# ── write ────────────────────────────────────────────────────────────


def upsert_agent(agent: dict[str, Any]) -> bool:
    """Insert or update an agent by ``agent_id``.

    Returns True on success, False on failure.
    """
    agent_id = agent.get("agent_id")
    if not agent_id:
        return False

    now = _now()
    agent.setdefault("created_at", now)
    agent["updated_at"] = now

    # Ensure stats exist
    agent.setdefault("stats", {
        "total_runs": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "month_tokens": 0,
        "month_cost_usd": 0.0,
        "month_reset_at": _current_month_start(),
    })
    agent.setdefault("status", "idle")
    agent.setdefault("current_task", None)
    agent.setdefault("last_active_at", None)

    try:
        _col().update_one(
            {"agent_id": agent_id},
            {"$set": agent, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return True
    except PyMongoError:
        logger.exception("[AgentRegistry] Failed to upsert agent=%s", agent_id)
        return False


def set_agent_status(
    agent_id: str,
    status: str,
    current_task: dict[str, Any] | None = None,
) -> bool:
    """Update an agent's status and optional current task."""
    update: dict[str, Any] = {
        "status": status,
        "updated_at": _now(),
    }
    if status == "active":
        update["last_active_at"] = _now()
    if current_task is not None:
        update["current_task"] = current_task
    elif status in ("idle", "paused", "error"):
        update["current_task"] = None

    try:
        result = _col().update_one({"agent_id": agent_id}, {"$set": update})
        return result.modified_count > 0 or result.matched_count > 0
    except PyMongoError:
        logger.exception("[AgentRegistry] Failed to set status agent=%s", agent_id)
        return False


def record_usage(
    agent_id: str,
    tokens: int,
    cost_usd: float,
) -> bool:
    """Increment token/cost counters after an agent execution.

    Also resets monthly counters if the month has rolled over.
    """
    now = _now()
    month_start = _current_month_start()

    try:
        # Check if month rolled over
        doc = _col().find_one({"agent_id": agent_id}, {"stats.month_reset_at": 1})
        if doc:
            stored_reset = doc.get("stats", {}).get("month_reset_at", "")
            if stored_reset != month_start:
                # New month — reset monthly counters
                _col().update_one(
                    {"agent_id": agent_id},
                    {"$set": {
                        "stats.month_tokens": 0,
                        "stats.month_cost_usd": 0.0,
                        "stats.month_reset_at": month_start,
                    }},
                )

        result = _col().update_one(
            {"agent_id": agent_id},
            {
                "$inc": {
                    "stats.total_tokens": tokens,
                    "stats.total_cost_usd": cost_usd,
                    "stats.total_runs": 1,
                    "stats.month_tokens": tokens,
                    "stats.month_cost_usd": cost_usd,
                },
                "$set": {
                    "last_active_at": now,
                    "updated_at": now,
                },
            },
        )
        return result.modified_count > 0
    except PyMongoError:
        logger.exception("[AgentRegistry] Failed to record usage agent=%s", agent_id)
        return False


def update_budget(
    agent_id: str,
    monthly_token_limit: int | None = None,
    monthly_cost_limit_usd: float | None = None,
    warning_threshold_pct: int | None = None,
    hard_stop: bool | None = None,
) -> bool:
    """Update budget configuration for an agent."""
    updates: dict[str, Any] = {}
    if monthly_token_limit is not None:
        updates["budget.monthly_token_limit"] = monthly_token_limit
    if monthly_cost_limit_usd is not None:
        updates["budget.monthly_cost_limit_usd"] = monthly_cost_limit_usd
    if warning_threshold_pct is not None:
        updates["budget.warning_threshold_pct"] = warning_threshold_pct
    if hard_stop is not None:
        updates["budget.hard_stop"] = hard_stop

    if not updates:
        return False

    updates["updated_at"] = _now()

    try:
        result = _col().update_one({"agent_id": agent_id}, {"$set": updates})
        return result.modified_count > 0
    except PyMongoError:
        logger.exception("[AgentRegistry] Failed to update budget agent=%s", agent_id)
        return False


# ── read ─────────────────────────────────────────────────────────────


def get_agent(agent_id: str) -> dict[str, Any] | None:
    """Get a single agent by ID."""
    try:
        doc = _col().find_one({"agent_id": agent_id}, {"_id": 0})
        return doc
    except PyMongoError:
        logger.exception("[AgentRegistry] Failed to get agent=%s", agent_id)
        return None


def list_agents(
    department: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List all agents, optionally filtered by department or status."""
    query: dict[str, Any] = {}
    if department:
        query["department"] = department
    if status:
        query["status"] = status

    try:
        return list(_col().find(query, {"_id": 0}).sort("department", 1))
    except PyMongoError:
        logger.exception("[AgentRegistry] Failed to list agents")
        return []


def get_org_chart() -> list[dict[str, Any]]:
    """Get all agents with hierarchy fields for building the org chart."""
    try:
        return list(
            _col().find(
                {},
                {
                    "_id": 0,
                    "agent_id": 1,
                    "display_name": 1,
                    "department": 1,
                    "role": 1,
                    "title": 1,
                    "reports_to": 1,
                    "avatar": 1,
                    "status": 1,
                    "last_active_at": 1,
                },
            )
        )
    except PyMongoError:
        logger.exception("[AgentRegistry] Failed to get org chart")
        return []


def get_budget_summary() -> dict[str, Any]:
    """Aggregate budget/cost data across all agents."""
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$department",
                    "total_cost_usd": {"$sum": "$stats.month_cost_usd"},
                    "total_tokens": {"$sum": "$stats.month_tokens"},
                    "agent_count": {"$sum": 1},
                }
            },
            {"$sort": {"total_cost_usd": -1}},
        ]
        by_dept = list(_col().aggregate(pipeline))

        # Also get top agents by cost
        top_agents = list(
            _col()
            .find(
                {"stats.month_cost_usd": {"$gt": 0}},
                {"_id": 0, "agent_id": 1, "display_name": 1, "department": 1,
                 "stats.month_cost_usd": 1, "stats.month_tokens": 1},
            )
            .sort("stats.month_cost_usd", -1)
            .limit(5)
        )

        return {
            "by_department": [
                {
                    "department": d["_id"],
                    "cost_usd": round(d["total_cost_usd"], 4),
                    "tokens": d["total_tokens"],
                    "agent_count": d["agent_count"],
                }
                for d in by_dept
            ],
            "top_agents": [
                {
                    "agent_id": a["agent_id"],
                    "display_name": a["display_name"],
                    "department": a["department"],
                    "cost_usd": round(a["stats"]["month_cost_usd"], 4),
                    "tokens": a["stats"]["month_tokens"],
                }
                for a in top_agents
            ],
        }
    except PyMongoError:
        logger.exception("[AgentRegistry] Failed to get budget summary")
        return {"by_department": [], "top_agents": []}


def check_budget(agent_id: str) -> dict[str, Any]:
    """Check if an agent is within budget.

    Returns:
        {
            "within_budget": bool,
            "at_warning": bool,
            "remaining_usd": float,
            "utilization_pct": float,
        }
    """
    agent = get_agent(agent_id)
    if not agent:
        return {"within_budget": True, "at_warning": False, "remaining_usd": 999.0, "utilization_pct": 0}

    budget = agent.get("budget", {})
    limit = budget.get("monthly_cost_limit_usd", 999.0)
    warning_pct = budget.get("warning_threshold_pct", 80)
    current = agent.get("stats", {}).get("month_cost_usd", 0.0)

    utilization = (current / limit * 100) if limit > 0 else 0
    remaining = max(0, limit - current)

    return {
        "within_budget": current < limit,
        "at_warning": utilization >= warning_pct,
        "remaining_usd": round(remaining, 4),
        "utilization_pct": round(utilization, 1),
        "hard_stop": budget.get("hard_stop", False),
    }
