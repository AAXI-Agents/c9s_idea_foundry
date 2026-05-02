"""Repository for the ``adminAuditLog`` collection.

Stores audit entries for admin actions such as project tenant
reassignment.  Each entry captures who did what, when, and which
entities were affected.

Document schema::

    {
        "audit_id":                  str,   # UUID hex (primary key)
        "action":                    str,   # e.g. "project_reassignment"
        "actor_id":                  str,   # user_id of the admin
        "actor_email":               str,   # email of the admin
        "project_id":                str,   # affected project
        "project_name":              str,   # project name at time of action
        "from_organization_id":      str,   # source org
        "from_organization_name":    str,   # source org name
        "to_organization_id":        str,   # target org
        "to_organization_name":      str,   # target org name
        "cascaded_documents":        int,   # number of docs updated
        "enterprise_id":             str,   # tenant scoping
        "timestamp":                 datetime,
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

ADMIN_AUDIT_LOG_COLLECTION = "adminAuditLog"


def _get_collection():
    from crewai_productfeature_planner.mongodb.client import get_db

    return get_db()[ADMIN_AUDIT_LOG_COLLECTION]


def create_audit_entry(
    *,
    action: str,
    actor_id: str,
    actor_email: str,
    project_id: str,
    project_name: str,
    from_organization_id: str,
    from_organization_name: str,
    to_organization_id: str,
    to_organization_name: str,
    cascaded_documents: int,
    enterprise_id: str,
) -> dict[str, Any]:
    """Insert a new audit log entry.

    Returns:
        The inserted document dict.
    """
    doc = {
        "audit_id": uuid.uuid4().hex,
        "action": action,
        "actor_id": actor_id,
        "actor_email": actor_email,
        "project_id": project_id,
        "project_name": project_name,
        "from_organization_id": from_organization_id,
        "from_organization_name": from_organization_name,
        "to_organization_id": to_organization_id,
        "to_organization_name": to_organization_name,
        "cascaded_documents": cascaded_documents,
        "enterprise_id": enterprise_id,
        "timestamp": datetime.now(timezone.utc),
    }
    try:
        coll = _get_collection()
        coll.insert_one(doc)
        logger.info(
            "[AuditLog] Created entry audit_id=%s action=%s actor=%s project=%s",
            doc["audit_id"],
            action,
            actor_id,
            project_id,
        )
    except PyMongoError as exc:
        logger.error("[AuditLog] Failed to insert: %s", exc, exc_info=True)
        raise
    return doc


def list_audit_entries(
    *,
    tenant: TenantContext,
    action: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """List audit entries scoped to an enterprise, with pagination.

    Args:
        tenant: Must be enterprise_admin context.
        action: Optional filter by action type.
        page: 1-based page number.
        page_size: Items per page.

    Returns:
        Tuple of (items, total_count).
    """
    query: dict[str, Any] = {"enterprise_id": tenant.enterprise_id}
    if action:
        query["action"] = action

    try:
        coll = _get_collection()
        total = coll.count_documents(query)
        skip = (page - 1) * page_size
        cursor = (
            coll.find(query, {"_id": 0})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(page_size)
        )
        items = list(cursor)
        return items, total
    except PyMongoError as exc:
        logger.error("[AuditLog] Failed to query: %s", exc, exc_info=True)
        raise
