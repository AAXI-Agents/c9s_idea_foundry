#!/usr/bin/env python
"""Compound Index Coverage Analysis — Recommendation 3.

Runs ``explain("executionStats")`` on every query path used by paginated
API endpoints and reports whether each uses an index scan (IXSCAN) or
falls back to a collection scan (COLLSCAN).

Usage::

    .venv/bin/python -m crewai_productfeature_planner.scripts.explain_queries

Requires a live MongoDB connection (MONGODB_ATLAS_URI env var).
"""

from __future__ import annotations

import sys

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.mongodb.working_ideas._common import WORKING_COLLECTION
from crewai_productfeature_planner.mongodb.project_config.repository import (
    PROJECT_CONFIG_COLLECTION,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Query definitions ─────────────────────────────────────────

_QUERIES: list[dict] = [
    {
        "label": "GET /ideas (no filter, sort created_at DESC)",
        "collection": WORKING_COLLECTION,
        "filter": {},
        "sort": [("created_at", -1)],
    },
    {
        "label": "GET /ideas (project_id filter)",
        "collection": WORKING_COLLECTION,
        "filter": {"project_id": "proj-1"},
        "sort": [("created_at", -1)],
    },
    {
        "label": "GET /ideas (status filter)",
        "collection": WORKING_COLLECTION,
        "filter": {"status": "completed"},
        "sort": [("created_at", -1)],
    },
    {
        "label": "GET /ideas (project_id + status filter)",
        "collection": WORKING_COLLECTION,
        "filter": {"project_id": "proj-1", "status": "inprogress"},
        "sort": [("created_at", -1)],
    },
    {
        "label": "GET /projects (no filter, sort created_at DESC)",
        "collection": PROJECT_CONFIG_COLLECTION,
        "filter": {},
        "sort": [("created_at", -1)],
    },
]


def _get_plan_stage(plan: dict) -> str:
    """Recursively find the leaf stage type in an explain plan."""
    if "inputStage" in plan:
        return _get_plan_stage(plan["inputStage"])
    return plan.get("stage", "UNKNOWN")


def _run_explain(db, query_def: dict) -> dict:
    """Run explain on a single query and return a summary."""
    coll = db[query_def["collection"]]
    cursor = coll.find(query_def["filter"]).sort(query_def["sort"]).limit(10)
    plan = cursor.explain()

    exec_stats = plan.get("executionStats", {})
    winning = plan.get("queryPlanner", {}).get("winningPlan", {})
    stage = _get_plan_stage(winning)

    return {
        "label": query_def["label"],
        "collection": query_def["collection"],
        "stage": stage,
        "docs_examined": exec_stats.get("totalDocsExamined", "?"),
        "keys_examined": exec_stats.get("totalKeysExamined", "?"),
        "docs_returned": exec_stats.get("nReturned", "?"),
        "exec_ms": exec_stats.get("executionTimeMillis", "?"),
    }


def main() -> None:
    """Run explain on all defined query paths and print results."""
    db = get_db()
    print("\n=== Compound Index Coverage Analysis ===\n")

    all_ok = True
    for qdef in _QUERIES:
        try:
            result = _run_explain(db, qdef)
        except Exception as exc:
            print(f"  ERROR: {qdef['label']}: {exc}")
            all_ok = False
            continue

        is_scan = result["stage"] == "COLLSCAN"
        marker = "WARN" if is_scan else " OK "
        if is_scan:
            all_ok = False

        print(f"  [{marker}] {result['label']}")
        print(f"         collection: {result['collection']}")
        print(f"         stage:      {result['stage']}")
        print(f"         keys:       {result['keys_examined']}")
        print(f"         docs:       {result['docs_examined']} examined, "
              f"{result['docs_returned']} returned")
        print(f"         time:       {result['exec_ms']} ms")
        print()

    if all_ok:
        print("All query paths use index scans. No action needed.")
    else:
        print("WARNING: Some queries fall back to COLLSCAN. "
              "Consider adding indexes for those paths.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
