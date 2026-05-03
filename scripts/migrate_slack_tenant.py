#!/usr/bin/env python3
"""One-time migration: assign enterprise/org IDs to Slack OAuth installs.

For existing ``slackOAuth`` documents that have a ``team_id`` but lack
``enterprise_id`` / ``organization_id``, this script links them to an
enterprise/org based on the SSO mapping or CLI input.

Usage::

    # Dry run (default) — shows Slack teams needing assignment
    .venv/bin/python scripts/migrate_slack_tenant.py

    # Assign all unmapped teams to the default enterprise/org
    .venv/bin/python scripts/migrate_slack_tenant.py --apply

    # Interactive mode — prompt for each team
    .venv/bin/python scripts/migrate_slack_tenant.py --interactive --apply

Environment variables:

    DEFAULT_ENTERPRISE_ID   — fallback enterprise for unmapped teams
    DEFAULT_ORGANIZATION_ID — fallback org for unmapped teams
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

SLACK_OAUTH_COLLECTION = "slackOAuth"


def _find_unmapped_teams(db) -> list[dict]:
    """Return Slack OAuth docs missing tenant fields."""
    coll = db[SLACK_OAUTH_COLLECTION]
    query = {
        "$or": [
            {"enterprise_id": {"$exists": False}},
            {"organization_id": {"$exists": False}},
            {"enterprise_id": ""},
            {"organization_id": ""},
        ],
    }
    return list(coll.find(query, {"team_id": 1, "team_name": 1, "_id": 0}))


def _assign_tenant(
    db,
    team_id: str,
    enterprise_id: str,
    organization_id: str,
    *,
    apply: bool = False,
) -> bool:
    """Assign tenant fields to a Slack OAuth document."""
    if not apply:
        return True

    coll = db[SLACK_OAUTH_COLLECTION]
    result = coll.update_one(
        {"team_id": team_id},
        {"$set": {"enterprise_id": enterprise_id, "organization_id": organization_id}},
    )
    return result.modified_count > 0


def main() -> None:
    apply = "--apply" in sys.argv
    interactive = "--interactive" in sys.argv

    default_ent = os.environ.get("DEFAULT_ENTERPRISE_ID", "")
    default_org = os.environ.get("DEFAULT_ORGANIZATION_ID", "")

    mode = "APPLYING" if apply else "DRY RUN"
    print(f"\n=== Slack OAuth Tenant Assignment ({mode}) ===")
    print(f"  default enterprise_id:    '{default_ent}'")
    print(f"  default organization_id:  '{default_org}'")
    print()

    try:
        db = get_db()
    except PyMongoError as exc:
        print(f"ERROR: Failed to connect to MongoDB: {exc}")
        sys.exit(1)

    teams = _find_unmapped_teams(db)

    if not teams:
        print("  All Slack OAuth installs already have tenant fields.")
        return

    print(f"  Found {len(teams)} team(s) needing tenant assignment:\n")

    updated = 0
    for team in teams:
        team_id = team.get("team_id", "?")
        team_name = team.get("team_name", "(unknown)")
        print(f"    Team: {team_name} ({team_id})")

        ent_id = default_ent
        org_id = default_org

        if interactive and apply:
            user_ent = input(f"      enterprise_id [{default_ent}]: ").strip()
            if user_ent:
                ent_id = user_ent
            user_org = input(f"      organization_id [{default_org}]: ").strip()
            if user_org:
                org_id = user_org

        if _assign_tenant(db, team_id, ent_id, org_id, apply=apply):
            updated += 1
            if apply:
                print(f"      → assigned: ent={ent_id}, org={org_id}")
        else:
            print(f"      → FAILED to update")

    print(f"\n  Total: {updated} team(s) {'updated' if apply else 'need assignment'}")
    if not apply and updated > 0:
        print("\n  Run with --apply to execute assignment.")
        print("  Run with --interactive --apply for per-team input.")


if __name__ == "__main__":
    main()
