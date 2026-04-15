#!/usr/bin/env python3
"""One-time script: backfill idea_normalized and archive duplicate ideas.

Run with:
    .venv/bin/python scripts/dedup_working_ideas.py [--dry-run]

Steps:
  1. Backfill ``idea_normalized`` on all documents missing it.
  2. Group non-archived ideas by (idea_normalized, project_id/channel).
  3. For each group with > 1 document, keep the NEWEST and archive the rest.
  4. For inprogress duplicates, mark them ``failed`` so they won't resume.

Flags:
  --dry-run    Print what would be changed without writing to MongoDB.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import datetime, timezone


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    # Lazy import to avoid circular imports and pick up .env
    import os
    from pathlib import Path
    # Load .env if present
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)

    from crewai_productfeature_planner.mongodb.client import get_database
    db = get_database()
    coll = db["workingIdeas"]

    # ── Step 1: Backfill idea_normalized ───────────────────────
    missing = list(coll.find({
        "$or": [
            {"idea_normalized": {"$exists": False}},
            {"idea_normalized": None},
            {"idea_normalized": ""},
        ],
    }))
    print(f"\n[Step 1] Backfilling idea_normalized on {len(missing)} document(s)")
    backfilled = 0
    for doc in missing:
        raw = doc.get("idea") or doc.get("finalized_idea") or ""
        if not raw:
            continue
        normalized = _normalize(raw)
        if not dry_run:
            coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {"idea_normalized": normalized}},
            )
        run_id = doc.get("run_id", "?")
        print(f"  Backfilled run_id={run_id}: {normalized[:60]}")
        backfilled += 1
    print(f"  → Backfilled {backfilled} document(s)")

    # ── Step 2: Find duplicates ────────────────────────────────
    # Refresh documents after backfill
    all_docs = list(coll.find({"status": {"$ne": "archived"}}))
    print(f"\n[Step 2] Scanning {len(all_docs)} non-archived document(s) for duplicates")

    # Group by (normalized_idea, scope_key)
    groups: dict[str, list[dict]] = defaultdict(list)
    for doc in all_docs:
        raw = doc.get("idea") or doc.get("finalized_idea") or ""
        if not raw:
            continue
        norm = _normalize(raw)
        # Scope: prefer project_id, fall back to channel
        scope = doc.get("project_id") or doc.get("slack_channel") or "global"
        key = f"{norm}|||{scope}"
        groups[key].append(doc)

    # ── Step 3: Archive duplicates ─────────────────────────────
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"\n[Step 3] Found {len(dup_groups)} duplicate group(s)")

    archived_count = 0
    failed_count = 0
    for key, docs in dup_groups.items():
        idea_text = key.split("|||")[0][:60]
        # Sort by created_at descending — keep the newest
        docs.sort(
            key=lambda d: d.get("created_at", ""),
            reverse=True,
        )
        keep = docs[0]
        victims = docs[1:]
        print(f"\n  Idea: {idea_text}...")
        print(f"  Keeping: run_id={keep.get('run_id')} status={keep.get('status')} "
              f"created={keep.get('created_at', '?')[:19]}")
        for victim in victims:
            run_id = victim.get("run_id", "?")
            status = victim.get("status", "?")
            action = "archive"
            # In-progress flows should be marked failed, not archived,
            # so the startup recovery doesn't try to resume them.
            if status in ("inprogress", "paused"):
                action = "fail"
                if not dry_run:
                    coll.update_one(
                        {"_id": victim["_id"]},
                        {"$set": {
                            "status": "failed",
                            "error": (
                                "Duplicate flow detected — "
                                f"superseded by run_id={keep.get('run_id')}"
                            ),
                            "update_date": _now_iso(),
                        }},
                    )
                failed_count += 1
            else:
                if not dry_run:
                    coll.update_one(
                        {"_id": victim["_id"]},
                        {"$set": {
                            "status": "archived",
                            "update_date": _now_iso(),
                        }},
                    )
                archived_count += 1
            prefix = "[DRY-RUN] " if dry_run else ""
            print(f"  {prefix}{action}: run_id={run_id} status={status} "
                  f"created={victim.get('created_at', '?')[:19]}")

    print(f"\n[Summary]")
    print(f"  Backfilled: {backfilled}")
    print(f"  Archived:   {archived_count}")
    print(f"  Failed:     {failed_count}")
    if dry_run:
        print("  (dry run — no changes written)")
    else:
        print("  Changes applied to MongoDB.")


if __name__ == "__main__":
    main()
