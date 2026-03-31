"""One-time script: Clear stale confluence_url from workingIdeas documents.

After a reset script cleared ``confluence_published`` in the
``productRequirements`` delivery records, the ``confluence_url`` field
on ``workingIdeas`` documents remained stale, causing the Slack product
list to incorrectly show checkmarks for Confluence publishing.

This script:
1. Finds all ``workingIdeas`` documents that have a ``confluence_url``
2. Cross-checks the ``productRequirements`` delivery record
3. If the delivery record does NOT have ``confluence_published: True``,
   clears the stale ``confluence_url`` from the ``workingIdeas`` doc

Usage:
    .venv/bin/python scripts/clear_stale_confluence_urls.py

Dry-run (default):
    Shows what would be cleared without making changes.

Apply changes:
    .venv/bin/python scripts/clear_stale_confluence_urls.py --apply
"""

from __future__ import annotations

import os
import sys

# Add project to path
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "src"),
)

# Minimal env for MongoDB
os.environ.setdefault("GOOGLE_API_KEY", "unused")
os.environ.setdefault("OPENAI_API_KEY", "unused")


def main() -> None:
    apply = "--apply" in sys.argv

    from crewai_productfeature_planner.mongodb.client import get_db

    db = get_db()
    wi_col = db["workingIdeas"]
    pr_col = db["productRequirements"]

    # Find all workingIdeas with a non-empty confluence_url
    docs = list(wi_col.find(
        {"confluence_url": {"$exists": True, "$ne": "", "$ne": None}},
        {"run_id": 1, "idea": 1, "confluence_url": 1, "status": 1},
    ))

    print(f"Found {len(docs)} workingIdea(s) with confluence_url set\n")

    cleared = 0
    kept = 0

    for doc in docs:
        run_id = doc.get("run_id", "")
        idea = (doc.get("idea") or "Untitled")[:60]
        url = doc.get("confluence_url", "")
        status = doc.get("status", "")

        if not run_id:
            print(f"  SKIP (no run_id): {idea}")
            continue

        # Check delivery record
        record = pr_col.find_one(
            {"run_id": run_id},
            {"confluence_published": 1, "confluence_url": 1},
        )

        if record and record.get("confluence_published"):
            print(f"  KEEP {run_id[:8]}… [{status}] {idea}")
            print(f"       URL: {url}")
            print(f"       Delivery record confirms published ✓")
            kept += 1
        else:
            print(f"  CLEAR {run_id[:8]}… [{status}] {idea}")
            print(f"        Stale URL: {url}")
            if record:
                print(f"        Delivery record: confluence_published={record.get('confluence_published', 'missing')}")
            else:
                print(f"        No delivery record found")

            if apply:
                result = wi_col.update_one(
                    {"run_id": run_id},
                    {"$unset": {"confluence_url": ""}},
                )
                if result.modified_count:
                    print(f"        → Cleared ✓")
                else:
                    print(f"        → No change (already cleared?)")
            else:
                print(f"        → Would clear (dry run)")
            cleared += 1

    print(f"\n{'='*50}")
    print(f"Summary: {kept} kept, {cleared} {'cleared' if apply else 'would clear'}")
    if not apply and cleared:
        print(f"\nRe-run with --apply to make changes:")
        print(f"  .venv/bin/python scripts/clear_stale_confluence_urls.py --apply")


if __name__ == "__main__":
    main()
