"""Repository for the ``productRequirements`` MongoDB collection.

Each document tracks whether a completed PRD run has been published to
Confluence and whether Jira tickets have been created.  The startup
orchestrator uses this to resume delivery where it left off.

Document schema::

    {
        "run_id":                str,       # links to workingIdeas.run_id
        "confluence_published":  bool,      # True once Confluence page exists
        "confluence_url":        str | "",   # URL of the published page
        "confluence_page_id":    str | "",   # Confluence page ID
        "jira_completed":        bool,      # True once Jira tickets exist
        "jira_output":           str | "",   # Agent summary of created tickets
        "status":                str,       # "pending" | "partial" | "completed"
        "created_at":            str,       # ISO-8601
        "updated_at":            str,       # ISO-8601
        "error":                 str | None # last error message (if any)
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

PRODUCT_REQUIREMENTS_COLLECTION = "productRequirements"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_status(confluence_published: bool, jira_completed: bool) -> str:
    """Derive overall status from the two delivery flags."""
    if confluence_published and jira_completed:
        return "completed"
    if confluence_published or jira_completed:
        return "partial"
    return "pending"


# ── Queries ───────────────────────────────────────────────────────────


def get_delivery_record(run_id: str) -> dict[str, Any] | None:
    """Fetch the delivery record for *run_id*, or ``None`` if absent."""
    try:
        db = get_db()
        doc = db[PRODUCT_REQUIREMENTS_COLLECTION].find_one({"run_id": run_id})
        return doc
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to fetch delivery record for run_id=%s: %s",
            run_id, exc,
        )
        return None


def find_pending_delivery() -> list[dict[str, Any]]:
    """Find delivery records that are not yet fully completed.

    Returns records whose ``status`` is ``"pending"`` or ``"partial"``
    — i.e. Confluence publish or Jira ticketing is still outstanding.
    """
    try:
        db = get_db()
        docs = list(
            db[PRODUCT_REQUIREMENTS_COLLECTION]
            .find({"status": {"$in": ["pending", "partial"]}})
            .sort("created_at", 1)
        )
        logger.info(
            "[MongoDB] Found %d pending delivery record(s)", len(docs),
        )
        return docs
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to query pending delivery records: %s", exc,
        )
        return []


# ── Mutations ─────────────────────────────────────────────────────────


def upsert_delivery_record(
    run_id: str,
    *,
    confluence_published: bool | None = None,
    confluence_url: str | None = None,
    confluence_page_id: str | None = None,
    jira_completed: bool | None = None,
    jira_output: str | None = None,
    error: str | None = None,
) -> bool:
    """Create or update the delivery record for *run_id*.

    Only the fields explicitly passed (not ``None``) are updated.
    The ``status`` field is recomputed from the current values of
    ``confluence_published`` and ``jira_completed``.

    Returns:
        ``True`` if the document was upserted, ``False`` on error.
    """
    now = _now_iso()
    try:
        db = get_db()
        col = db[PRODUCT_REQUIREMENTS_COLLECTION]

        # Fetch current state for recomputation
        existing = col.find_one({"run_id": run_id}) or {}
        conf_pub = (
            confluence_published
            if confluence_published is not None
            else existing.get("confluence_published", False)
        )
        jira_done = (
            jira_completed
            if jira_completed is not None
            else existing.get("jira_completed", False)
        )

        set_fields: dict[str, Any] = {
            "updated_at": now,
            "status": _compute_status(conf_pub, jira_done),
        }
        if confluence_published is not None:
            set_fields["confluence_published"] = confluence_published
        if confluence_url is not None:
            set_fields["confluence_url"] = confluence_url
        if confluence_page_id is not None:
            set_fields["confluence_page_id"] = confluence_page_id
        if jira_completed is not None:
            set_fields["jira_completed"] = jira_completed
        if jira_output is not None:
            set_fields["jira_output"] = jira_output
        if error is not None:
            set_fields["error"] = error

        result = col.update_one(
            {"run_id": run_id},
            {
                "$set": set_fields,
                "$setOnInsert": {"run_id": run_id, "created_at": now},
            },
            upsert=True,
        )
        modified = result.upserted_id is not None or result.modified_count > 0
        logger.info(
            "[MongoDB] Upserted delivery record run_id=%s (status=%s, upserted=%s)",
            run_id, set_fields["status"], result.upserted_id is not None,
        )
        return modified
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to upsert delivery record for run_id=%s: %s",
            run_id, exc,
        )
        return False
