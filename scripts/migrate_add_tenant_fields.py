#!/usr/bin/env python3
"""One-time migration: backfill ``enterprise_id`` and ``organization_id``.

Adds default tenant fields to all documents in all nine MongoDB
collections that are missing them.  Uses the configured default
enterprise/org from environment variables.

Usage::

    # Dry run (default) — shows what would be updated
    .venv/bin/python scripts/migrate_add_tenant_fields.py

    # Apply changes
    .venv/bin/python scripts/migrate_add_tenant_fields.py --apply

Environment variables (set in .env):

    DEFAULT_ENTERPRISE_ID   — default enterprise ID for backfill
    DEFAULT_ORGANIZATION_ID — default organization ID for backfill

If neither is set, documents are tagged with empty strings (safe —
``tenant_filter()`` returns ``{}`` for empty tenant contexts).
"""

from __future__ import annotations

import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pymongo.errors import PyMongoError  # noqa: E402

from crewai_productfeature_planner.mongodb.client import get_db  # noqa: E402
from crewai_productfeature_planner.scripts.logging_config import get_logger  # noqa: E402

logger = get_logger(__name__)

# All collections that need tenant fields
COLLECTIONS = [
    "projectConfig",
    "workingIdeas",
    "crewJobs",
    "productRequirements",
    "agentInteractions",
    "userSessions",
    "slackOAuth",
    "projectMemory",
    "userSuggestions",
]


def _backfill_collection(
    db,
    collection_name: str,
    enterprise_id: str,
    organization_id: str,
    *,
    apply: bool = False,
) -> int:
    """Backfill tenant fields on documents missing them.

    Returns the number of documents that need (or were) updated.
    """
    coll = db[collection_name]

    # Find documents missing either tenant field
    query = {
        "$or": [
            {"enterprise_id": {"$exists": False}},
            {"organization_id": {"$exists": False}},
        ],
    }

    count = coll.count_documents(query)
    if count == 0:
        print(f"  {collection_name}: 0 documents need backfill")
        return 0

    if apply:
        result = coll.update_many(
            query,
            {
                "$set": {
                    "enterprise_id": enterprise_id,
                    "organization_id": organization_id,
                },
            },
        )
        print(
            f"  {collection_name}: updated {result.modified_count} "
            f"of {count} documents"
        )
        return result.modified_count
    else:
        print(f"  {collection_name}: {count} documents need backfill")
        return count


def main() -> None:
    apply = "--apply" in sys.argv

    enterprise_id = os.environ.get("DEFAULT_ENTERPRISE_ID", "")
    organization_id = os.environ.get("DEFAULT_ORGANIZATION_ID", "")

    if not enterprise_id and not organization_id:
        print(
            "WARNING: DEFAULT_ENTERPRISE_ID and DEFAULT_ORGANIZATION_ID "
            "are not set. Documents will be tagged with empty strings."
        )

    mode = "APPLYING" if apply else "DRY RUN"
    print(f"\n=== Tenant Field Backfill ({mode}) ===")
    print(f"  enterprise_id:    '{enterprise_id}'")
    print(f"  organization_id:  '{organization_id}'")
    print()

    try:
        db = get_db()
    except PyMongoError as exc:
        print(f"ERROR: Failed to connect to MongoDB: {exc}")
        sys.exit(1)

    total = 0
    for coll_name in COLLECTIONS:
        total += _backfill_collection(
            db, coll_name, enterprise_id, organization_id, apply=apply,
        )

    print(f"\nTotal: {total} documents {'updated' if apply else 'need backfill'}")
    if not apply and total > 0:
        print("\nRun with --apply to execute the backfill.")


if __name__ == "__main__":
    main()
