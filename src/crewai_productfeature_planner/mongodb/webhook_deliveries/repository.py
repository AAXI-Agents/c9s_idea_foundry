"""Repository for the ``webhookDeliveries`` collection.

Tracks received inbound webhook deliveries from external services
(primarily Agentic Team) for idempotency deduplication and audit trail.

Document schema::

    {
        "delivery_id":    str,              # UUIDv7 from sender (primary key)
        "event_id":       str | None,       # monotonic event ID from sender
        "event":          str,              # event type (task.completed, etc.)
        "source_service": str,              # sender identity (c9s_agentic_team)
        "schema_version": str,              # envelope schema version (1.0)
        "status":         str,              # "processed" | "ignored" | "failed"
        "idea_id":        str | None,       # extracted idea linkage
        "feature_id":     str | None,       # extracted feature linkage
        "issue_key":      str | None,       # Jira issue key from payload
        "payload":        dict,             # full envelope for audit
        "result":         dict | None,      # handler response
        "error":          str | None,       # error message if processing failed
        "received_at":    datetime (UTC),   # when we received it
        "organization_id": str | None,      # tenant isolation
        "enterprise_id":  str | None,       # tenant isolation
    }

Indexes:
    - unique on ``delivery_id`` (idempotency key)
    - ``(event, received_at desc)`` for filtered queries
    - ``idea_id`` for idea-scoped lookups
    - ``received_at desc`` for chronological listing
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

WEBHOOK_DELIVERIES_COLLECTION = "webhookDeliveries"


# ── Write ─────────────────────────────────────────────────────


def record_delivery(
    *,
    delivery_id: str,
    event: str,
    source_service: str = "c9s_agentic_team",
    schema_version: str = "1.0",
    event_id: str | None = None,
    status: str = "processed",
    idea_id: str | None = None,
    feature_id: str | None = None,
    issue_key: str | None = None,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    organization_id: str | None = None,
    enterprise_id: str | None = None,
) -> bool:
    """Persist a received webhook delivery for audit and deduplication.

    Returns True if the delivery was inserted, False if it was a duplicate.
    """
    db = get_db()
    doc = {
        "delivery_id": delivery_id,
        "event_id": event_id,
        "event": event,
        "source_service": source_service,
        "schema_version": schema_version,
        "status": status,
        "idea_id": idea_id,
        "feature_id": feature_id,
        "issue_key": issue_key,
        "payload": payload or {},
        "result": result,
        "error": error,
        "received_at": datetime.now(timezone.utc),
        "organization_id": organization_id,
        "enterprise_id": enterprise_id,
    }

    try:
        db[WEBHOOK_DELIVERIES_COLLECTION].insert_one(doc)
        logger.debug(
            "[WebhookDeliveries] Recorded delivery_id=%s event=%s",
            delivery_id, event,
        )
        return True
    except DuplicateKeyError:
        logger.info(
            "[WebhookDeliveries] Duplicate delivery_id=%s — already processed",
            delivery_id,
        )
        return False
    except PyMongoError:
        logger.error(
            "[WebhookDeliveries] Failed to record delivery_id=%s",
            delivery_id, exc_info=True,
        )
        return False


# ── Read ──────────────────────────────────────────────────────


def has_delivery(delivery_id: str) -> bool:
    """Check if a delivery_id has already been processed (idempotency)."""
    db = get_db()
    try:
        return (
            db[WEBHOOK_DELIVERIES_COLLECTION].count_documents(
                {"delivery_id": delivery_id}, limit=1,
            )
            > 0
        )
    except PyMongoError:
        logger.error(
            "[WebhookDeliveries] Failed to check delivery_id=%s",
            delivery_id, exc_info=True,
        )
        return False


def get_delivery(delivery_id: str) -> dict[str, Any] | None:
    """Retrieve a single delivery record by delivery_id."""
    db = get_db()
    try:
        doc = db[WEBHOOK_DELIVERIES_COLLECTION].find_one(
            {"delivery_id": delivery_id}, {"_id": 0},
        )
        return doc
    except PyMongoError:
        logger.error(
            "[WebhookDeliveries] Failed to get delivery_id=%s",
            delivery_id, exc_info=True,
        )
        return None


def list_deliveries(
    *,
    event: str | None = None,
    idea_id: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
    organization_id: str | None = None,
    enterprise_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """List deliveries with optional filters, newest first.

    Returns::
        {
            "items": [delivery_doc, ...],
            "total": int,
            "page": int,
            "page_size": int,
        }
    """
    db = get_db()
    query: dict[str, Any] = {}

    if event:
        query["event"] = event
    if idea_id:
        query["idea_id"] = idea_id
    if status:
        query["status"] = status
    if since:
        query["received_at"] = {"$gte": since}
    if organization_id:
        query["organization_id"] = organization_id
    if enterprise_id:
        query["enterprise_id"] = enterprise_id

    try:
        total = db[WEBHOOK_DELIVERIES_COLLECTION].count_documents(query)
        skip = (max(1, page) - 1) * page_size
        cursor = (
            db[WEBHOOK_DELIVERIES_COLLECTION]
            .find(query, {"_id": 0})
            .sort("received_at", DESCENDING)
            .skip(skip)
            .limit(page_size)
        )
        items = list(cursor)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except PyMongoError:
        logger.error("[WebhookDeliveries] Failed to list deliveries", exc_info=True)
        return {"items": [], "total": 0, "page": page, "page_size": page_size}


# ── Index setup ───────────────────────────────────────────────


def ensure_indexes() -> None:
    """Create required indexes for the webhookDeliveries collection."""
    db = get_db()
    coll = db[WEBHOOK_DELIVERIES_COLLECTION]
    try:
        coll.create_index("delivery_id", unique=True, name="idx_delivery_id_unique")
        coll.create_index(
            [("event", 1), ("received_at", DESCENDING)],
            name="idx_event_received",
        )
        coll.create_index("idea_id", sparse=True, name="idx_idea_id")
        coll.create_index(
            [("received_at", DESCENDING)],
            name="idx_received_at_desc",
        )
        logger.info("[WebhookDeliveries] Indexes ensured")
    except PyMongoError:
        logger.error("[WebhookDeliveries] Failed to create indexes", exc_info=True)
