"""CRUD operations for the ``ideas`` collection.

The ``ideas`` collection stores Idea entities with embedded features,
completion tracking, and links to ``workingIdeas`` (PRD flow runs)
and ``ideationSessions``.

Document schema::

    {
        "idea_id": str (UUID hex, primary key),
        "project_id": str (UUID hex, indexed),
        "title": str,
        "description": str,
        "status": "draft" | "active" | "in_progress" | "completed" | "archived",
        "features": [
            {
                "id": str (UUID hex),
                "name": str,
                "description": str,
                "jira_epic_key": str | None,
                "completion_pct": float (0-100),
            },
            ...
        ],
        "overall_completion": float (0-100),
        "active_run_id": str | None (→ workingIdeas.run_id),
        "run_ids": [str] (history of all run_ids),
        "ideation_session_id": str | None (→ ideationSessions.session_id),
        "design_url": str | None,
        "design_url_type": "figma" | "url" | None,
        "created_by": str (user_id),
        "organization_id": str (tenant isolation),
        "enterprise_id": str (tenant isolation),
        "created_at": str (ISO-8601),
        "updated_at": str (ISO-8601),
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    tenant_fields,
    tenant_filter,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

IDEAS_COLLECTION = "ideas"

VALID_STATUSES = frozenset({"draft", "active", "in_progress", "completed", "archived"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col():
    return get_db()[IDEAS_COLLECTION]


# ── write ─────────────────────────────────────────────────────


def create_idea(
    *,
    project_id: str,
    title: str,
    description: str = "",
    created_by: str,
    ideation_session_id: str | None = None,
    features: list[dict[str, Any]] | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Create a new Idea document in ``draft`` status.

    Returns:
        The inserted document (without ``_id``), or ``None`` on failure.
    """
    idea_id = uuid.uuid4().hex
    now = _now_iso()

    doc: dict[str, Any] = {
        "idea_id": idea_id,
        "project_id": project_id,
        "title": title,
        "description": description,
        "status": "draft",
        "features": features or [],
        "overall_completion": 0.0,
        "active_run_id": None,
        "run_ids": [],
        "ideation_session_id": ideation_session_id,
        "design_url": None,
        "design_url_type": None,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        **(tenant_fields(tenant) if tenant else {}),
    }

    try:
        _col().insert_one(doc)
        logger.info(
            "[Ideas] Created idea=%s project=%s user=%s title=%r",
            idea_id,
            project_id,
            created_by,
            title,
        )
        doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to create idea project=%s user=%s: %s",
            project_id,
            created_by,
            exc,
            exc_info=True,
        )
        return None


def update_idea(
    *,
    idea_id: str,
    title: str | None = None,
    description: str | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Update mutable idea metadata (title, description).

    Returns:
        The updated document, or ``None`` on failure.
    """
    now = _now_iso()
    update: dict[str, Any] = {"updated_at": now}
    if title is not None:
        update["title"] = title
    if description is not None:
        update["description"] = description

    if len(update) == 1:
        return get_idea(idea_id=idea_id, tenant=tenant)

    try:
        _col().update_one(
            {"idea_id": idea_id, **tenant_filter(tenant)},
            {"$set": update},
        )
        logger.info(
            "[Ideas] Updated metadata idea=%s title=%r",
            idea_id,
            title,
        )
        return get_idea(idea_id=idea_id, tenant=tenant)
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to update idea=%s: %s",
            idea_id,
            exc,
            exc_info=True,
        )
        return None


def update_idea_status(
    *,
    idea_id: str,
    status: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Transition the idea to a new status.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    if status not in VALID_STATUSES:
        logger.warning("[Ideas] Invalid status=%r for idea=%s", status, idea_id)
        return False

    now = _now_iso()
    try:
        result = _col().update_one(
            {"idea_id": idea_id, **tenant_filter(tenant)},
            {"$set": {"status": status, "updated_at": now}},
        )
        if result.modified_count:
            logger.info("[Ideas] Status updated idea=%s status=%s", idea_id, status)
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to update status idea=%s: %s",
            idea_id,
            exc,
            exc_info=True,
        )
        return False


def set_active_run(
    *,
    idea_id: str,
    run_id: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Link a new PRD flow run to this idea.

    Sets ``active_run_id`` and appends ``run_id`` to the ``run_ids`` history.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    now = _now_iso()
    try:
        result = _col().update_one(
            {"idea_id": idea_id, **tenant_filter(tenant)},
            {
                "$set": {"active_run_id": run_id, "updated_at": now},
                "$addToSet": {"run_ids": run_id},
            },
        )
        if result.modified_count:
            logger.info(
                "[Ideas] Set active run idea=%s run_id=%s",
                idea_id,
                run_id,
            )
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to set run idea=%s run_id=%s: %s",
            idea_id,
            run_id,
            exc,
            exc_info=True,
        )
        return False


def update_features(
    *,
    idea_id: str,
    features: list[dict[str, Any]],
    tenant: TenantContext | None = None,
) -> bool:
    """Replace the features array on an idea.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    now = _now_iso()
    try:
        result = _col().update_one(
            {"idea_id": idea_id, **tenant_filter(tenant)},
            {"$set": {"features": features, "updated_at": now}},
        )
        if result.modified_count:
            logger.info("[Ideas] Updated features idea=%s count=%d", idea_id, len(features))
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to update features idea=%s: %s",
            idea_id,
            exc,
            exc_info=True,
        )
        return False


def update_overall_completion(
    *,
    idea_id: str,
    overall_completion: float,
    tenant: TenantContext | None = None,
) -> bool:
    """Update the overall completion percentage.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    now = _now_iso()
    pct = max(0.0, min(100.0, overall_completion))
    try:
        result = _col().update_one(
            {"idea_id": idea_id, **tenant_filter(tenant)},
            {"$set": {"overall_completion": pct, "updated_at": now}},
        )
        if result.modified_count:
            logger.info("[Ideas] Updated completion idea=%s pct=%.1f", idea_id, pct)
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to update completion idea=%s: %s",
            idea_id,
            exc,
            exc_info=True,
        )
        return False


def save_design_url(
    *,
    idea_id: str,
    design_url: str,
    design_url_type: str = "url",
    tenant: TenantContext | None = None,
) -> bool:
    """Set the design URL on an idea.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    now = _now_iso()
    try:
        result = _col().update_one(
            {"idea_id": idea_id, **tenant_filter(tenant)},
            {"$set": {
                "design_url": design_url,
                "design_url_type": design_url_type,
                "updated_at": now,
            }},
        )
        if result.modified_count:
            logger.info("[Ideas] Saved design URL idea=%s type=%s", idea_id, design_url_type)
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to save design URL idea=%s: %s",
            idea_id,
            exc,
            exc_info=True,
        )
        return False


def delete_idea(
    *,
    idea_id: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Soft-delete an idea (set status to 'archived').

    Only ideas in ``draft`` status can be deleted.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    doc = get_idea(idea_id=idea_id, tenant=tenant)
    if not doc:
        return False
    if doc.get("status") != "draft":
        logger.warning(
            "[Ideas] Cannot delete non-draft idea=%s status=%s",
            idea_id,
            doc.get("status"),
        )
        return False

    return update_idea_status(idea_id=idea_id, status="archived", tenant=tenant)


# ── queries ───────────────────────────────────────────────────


def find_idea_by_session(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Find an existing idea linked to an ideation session.

    Used as an idempotency guard to prevent duplicate idea creation
    when session completion is triggered multiple times.

    Returns:
        The idea document (without ``_id``), or ``None``.
    """
    try:
        doc = _col().find_one(
            {"ideation_session_id": session_id, **tenant_filter(tenant)},
            {"_id": 0},
        )
        return doc
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to find idea by session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return None


def get_idea(
    *,
    idea_id: str,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Fetch a single idea by ID.

    Returns:
        The idea document (without ``_id``), or ``None``.
    """
    try:
        doc = _col().find_one(
            {"idea_id": idea_id, **tenant_filter(tenant)},
            {"_id": 0},
        )
        return doc
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to get idea=%s: %s",
            idea_id,
            exc,
            exc_info=True,
        )
        return None


def list_ideas(
    *,
    project_id: str,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    tenant: TenantContext | None = None,
) -> list[dict[str, Any]]:
    """List ideas for a project, newest first.

    Excludes ``archived`` ideas unless filtered by status explicitly.
    Deduplicates by ``idea_id`` defensively (keeps the most recent).

    Returns:
        List of idea documents (without ``_id``).
    """
    query: dict[str, Any] = {"project_id": project_id, **tenant_filter(tenant)}
    if status:
        query["status"] = status
    else:
        query["status"] = {"$ne": "archived"}

    offset = (page - 1) * page_size
    try:
        cursor = (
            _col()
            .find(query, {"_id": 0})
            .sort("created_at", DESCENDING)
            .skip(offset)
            .limit(page_size)
        )
        docs = list(cursor)
        # Defensive dedup: keep first occurrence per idea_id (most recent
        # due to descending sort). Guards against duplicate documents that
        # may exist if the unique index was applied after data insertion.
        seen: set[str] = set()
        unique_docs: list[dict[str, Any]] = []
        for doc in docs:
            iid = doc.get("idea_id", "")
            if iid and iid in seen:
                logger.warning(
                    "[Ideas] Duplicate idea_id=%s in project=%s — skipping",
                    iid,
                    project_id,
                )
                continue
            if iid:
                seen.add(iid)
            unique_docs.append(doc)
        return unique_docs
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to list ideas project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return []


def count_ideas(
    *,
    project_id: str,
    status: str | None = None,
    tenant: TenantContext | None = None,
) -> int:
    """Count ideas matching filters (for pagination)."""
    query: dict[str, Any] = {"project_id": project_id, **tenant_filter(tenant)}
    if status:
        query["status"] = status
    else:
        query["status"] = {"$ne": "archived"}
    try:
        return _col().count_documents(query)
    except PyMongoError as exc:
        logger.error(
            "[Ideas] Failed to count ideas project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return 0
