"""One-time migration: copy Atlassian credentials from env vars to MongoDB.

Run once per tenant to seed ``integrationCredentials`` from the existing
environment-variable-based configuration.  After running, per-tenant
credentials stored in MongoDB take precedence over env vars.

Usage::

    .venv/bin/python -m crewai_productfeature_planner.scripts.migrate_credentials

The script reads the current env vars, encrypts them, and stores them
under the organisation ID passed as ``--org-id`` (or from
``DEV_ORGANIZATION_ID``).  Idempotent — re-running overwrites.
"""

from __future__ import annotations

import argparse
import os
import sys

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.integration_credentials import (
    get_credentials,
    upsert_credentials,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def migrate(org_id: str, enterprise_id: str) -> bool:
    """Migrate env-var Atlassian credentials into MongoDB.

    Returns ``True`` if credentials were saved, ``False`` if skipped.
    """
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "")
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    if not all([base_url, username, api_token]):
        logger.info(
            "[Migration] No Atlassian env vars set — nothing to migrate",
        )
        return False

    tenant = TenantContext(
        enterprise_id=enterprise_id,
        organization_id=org_id,
    )

    # Check if already migrated.
    existing = get_credentials(org_id, "atlassian", tenant=tenant)
    if existing and existing.get("credentials", {}).get("base_url"):
        logger.info(
            "[Migration] Credentials already exist in MongoDB for org_id=%s — skipping",
            org_id,
        )
        return False

    jira_project_key = os.environ.get("JIRA_PROJECT_KEY", "")
    confluence_base_url = os.environ.get("CONFLUENCE_URL", "")

    result = upsert_credentials(
        organization_id=org_id,
        provider="atlassian",
        credentials={
            "base_url": base_url,
            "username": username,
            "api_token": api_token,
        },
        user_id="migration-script",
        confluence_base_url=confluence_base_url or None,
        jira_project_key=jira_project_key or None,
        synced_to_agent_worker=False,
        tenant=tenant,
    )

    if result:
        logger.info(
            "[Migration] Migrated Atlassian credentials to MongoDB for org_id=%s",
            org_id,
        )
        return True

    logger.error(
        "[Migration] Failed to save credentials for org_id=%s", org_id,
    )
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate Atlassian env-var credentials to MongoDB",
    )
    parser.add_argument(
        "--org-id",
        default=os.environ.get("DEV_ORGANIZATION_ID", "dev-org"),
        help="Organization ID to store credentials under",
    )
    parser.add_argument(
        "--enterprise-id",
        default=os.environ.get("DEV_ENTERPRISE_ID", "dev-enterprise"),
        help="Enterprise ID for tenant scoping",
    )
    args = parser.parse_args()

    success = migrate(args.org_id, args.enterprise_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
