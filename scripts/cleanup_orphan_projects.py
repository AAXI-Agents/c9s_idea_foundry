#!/usr/bin/env python3
"""One-time cleanup script for orphaned project references in MongoDB.

Scans ``workingIdeas`` for ``project_id`` values that don't exist in
``projectConfig``, prints a summary, and offers to **archive** (R1)
or **delete** (R2) the orphaned documents and their related records
across ``crewJobs``, ``agentInteraction``, and ``productRequirements``.

Usage::

    # Dry-run — show summary only (default)
    .venv/bin/python scripts/cleanup_orphan_projects.py

    # Archive all orphaned ideas (R1)
    .venv/bin/python scripts/cleanup_orphan_projects.py --archive

    # Delete all orphaned ideas and related documents (R2)
    .venv/bin/python scripts/cleanup_orphan_projects.py --delete

    # Target a specific project_id only
    .venv/bin/python scripts/cleanup_orphan_projects.py --delete --project proj-1
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone


# ── collection names ───────────────────────────────────────────────────────

_WORKING = "workingIdeas"
_CREW_JOBS = "crewJobs"
_AGENT_INTERACTIONS = "agentInteraction"
_PRODUCT_REQUIREMENTS = "productRequirements"
_PROJECT_CONFIG = "projectConfig"


# ── helpers ────────────────────────────────────────────────────────────────


def _get_valid_project_ids(db) -> set[str]:
    """Return the set of project_ids that exist in ``projectConfig``."""
    docs = db[_PROJECT_CONFIG].find({}, {"project_id": 1})
    return {d["project_id"] for d in docs if d.get("project_id")}


def _find_orphaned_projects(db, valid_ids: set[str]) -> dict[str, list[dict]]:
    """Return orphaned project_id → list of working-idea docs."""
    # Find all distinct project_ids in workingIdeas
    all_pids = db[_WORKING].distinct("project_id")
    orphan_pids = [
        pid for pid in all_pids
        if pid and pid not in valid_ids
    ]
    if not orphan_pids:
        return {}

    result: dict[str, list[dict]] = {}
    for pid in sorted(orphan_pids):
        docs = list(db[_WORKING].find(
            {"project_id": pid},
            {"run_id": 1, "idea": 1, "status": 1, "created_at": 1},
        ))
        if docs:
            result[pid] = docs
    return result


def _print_summary(orphans: dict[str, list[dict]]) -> None:
    """Print a human-readable summary table."""
    if not orphans:
        print("\n✅  No orphaned project references found.")
        return

    total = sum(len(docs) for docs in orphans.values())
    print(f"\n🔍  Found {total} orphaned idea(s) across "
          f"{len(orphans)} invalid project(s):\n")
    print(f"{'project_id':<30} {'count':>6}   status breakdown")
    print("-" * 72)
    for pid, docs in orphans.items():
        statuses = Counter(d.get("status", "unknown") for d in docs)
        breakdown = ", ".join(f"{s}={c}" for s, c in sorted(statuses.items()))
        print(f"{pid:<30} {len(docs):>6}   {breakdown}")
    print("-" * 72)
    print(f"{'TOTAL':<30} {total:>6}")
    print()


def _get_run_ids(docs: list[dict]) -> list[str]:
    """Extract run_ids from idea docs."""
    return [d["run_id"] for d in docs if d.get("run_id")]


def _archive_orphans(db, orphans: dict[str, list[dict]]) -> dict[str, int]:
    """Archive orphaned ideas — sets status to 'archived'."""
    now = datetime.now(timezone.utc).isoformat()
    counts: dict[str, int] = {"workingIdeas": 0, "crewJobs": 0}

    for pid, docs in orphans.items():
        run_ids = _get_run_ids(docs)

        # Archive working ideas
        result = db[_WORKING].update_many(
            {"project_id": pid},
            {"$set": {"status": "archived", "archived_at": now, "update_date": now}},
        )
        counts["workingIdeas"] += result.modified_count

        # Archive corresponding crew jobs
        if run_ids:
            result = db[_CREW_JOBS].update_many(
                {"job_id": {"$in": run_ids}},
                {"$set": {"status": "archived", "updated_at": now}},
            )
            counts["crewJobs"] += result.modified_count

    return counts


def _delete_orphans(db, orphans: dict[str, list[dict]]) -> dict[str, int]:
    """Delete orphaned ideas and all related documents."""
    counts: dict[str, int] = {
        "workingIdeas": 0,
        "crewJobs": 0,
        "agentInteraction": 0,
        "productRequirements": 0,
    }

    for pid, docs in orphans.items():
        run_ids = _get_run_ids(docs)

        # Delete working ideas
        result = db[_WORKING].delete_many({"project_id": pid})
        counts["workingIdeas"] += result.deleted_count

        if run_ids:
            # Delete crew jobs
            result = db[_CREW_JOBS].delete_many({"job_id": {"$in": run_ids}})
            counts["crewJobs"] += result.deleted_count

            # Delete agent interactions
            result = db[_AGENT_INTERACTIONS].delete_many(
                {"run_id": {"$in": run_ids}},
            )
            counts["agentInteraction"] += result.deleted_count

            # Delete product requirements
            result = db[_PRODUCT_REQUIREMENTS].delete_many(
                {"run_id": {"$in": run_ids}},
            )
            counts["productRequirements"] += result.deleted_count

    return counts


def _confirm(action: str) -> bool:
    """Prompt the user for confirmation."""
    answer = input(f"⚠️  Proceed to {action} the above documents? [y/N] ")
    return answer.strip().lower() in ("y", "yes")


# ── main ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find and clean up orphaned project references in MongoDB.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--archive", action="store_true",
        help="Archive orphaned ideas (set status='archived'). Reversible.",
    )
    group.add_argument(
        "--delete", action="store_true",
        help="Permanently delete orphaned ideas and related documents.",
    )
    parser.add_argument(
        "--project", type=str, default=None,
        help="Target a specific project_id only (e.g. --project proj-1).",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt.",
    )
    args = parser.parse_args()

    # Lazy import — only needed at runtime, not during test collection.
    sys.path.insert(0, "src")
    from crewai_productfeature_planner.mongodb.client import get_db

    db = get_db()
    valid_ids = _get_valid_project_ids(db)
    orphans = _find_orphaned_projects(db, valid_ids)

    # Filter to a single project if requested
    if args.project:
        if args.project in orphans:
            orphans = {args.project: orphans[args.project]}
        else:
            print(f"\n✅  Project '{args.project}' is either valid or has "
                  "no ideas in workingIdeas.")
            return

    _print_summary(orphans)

    if not orphans:
        return

    if args.archive:
        if not args.yes and not _confirm("ARCHIVE"):
            print("Aborted.")
            return
        counts = _archive_orphans(db, orphans)
        print("✅  Archived:")
        for coll, n in counts.items():
            print(f"   {coll}: {n} document(s)")

    elif args.delete:
        if not args.yes and not _confirm("DELETE"):
            print("Aborted.")
            return
        counts = _delete_orphans(db, orphans)
        print("✅  Deleted:")
        for coll, n in counts.items():
            print(f"   {coll}: {n} document(s)")

    else:
        print("ℹ️  Dry-run complete. Use --archive or --delete to take action.")


if __name__ == "__main__":
    main()
