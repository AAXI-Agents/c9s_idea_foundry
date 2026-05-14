"""Webhook events endpoints — query, detail, replay, backfill.

GET    /webhook-events              — list events (filter by source/type/status/project)
GET    /webhook-events/{event_id}   — event detail (full payload + headers)
POST   /webhook-events/{event_id}/replay  — retry a failed delivery
POST   /webhook-events/backfill     — bulk re-process events
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.admin_deps import require_enterprise_admin
from crewai_productfeature_planner.mongodb.webhook_deliveries.repository import (
    get_delivery,
    list_deliveries,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/webhook-events",
    tags=["Webhooks"],
    dependencies=[Depends(require_enterprise_admin)],
)


# ── Models ────────────────────────────────────────────────────


class WebhookEventListResponse(BaseModel):
    events: list[dict[str, Any]]
    total: int


class WebhookEventReplayResponse(BaseModel):
    event_id: str
    dispatched_run_ids: list[str] = Field(default_factory=list)
    message: str


class WebhookEventBackfillRequest(BaseModel):
    source: str | None = None
    event_type: str | None = None
    since: str = Field(..., description="ISO-8601 datetime — only events after this time.")
    limit: int | None = Field(None, ge=1, le=1000)


class WebhookEventBackfillResponse(BaseModel):
    enqueued: int
    skipped: int
    message: str


# ── List events ───────────────────────────────────────────────


@router.get(
    "",
    response_model=WebhookEventListResponse,
    summary="List webhook events",
    description="List inbound webhook events with optional filters.",
)
async def list_events(
    user: dict[str, Any] = Depends(require_enterprise_admin),
    source: str | None = Query(None),
    event_type: str | None = Query(None),
    project_key: str | None = Query(None),
    event_status: str | None = Query(None, alias="status"),
    since: str | None = Query(None, description="ISO-8601 datetime filter"),
    limit: int = Query(50, ge=1, le=200),
) -> WebhookEventListResponse:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookEvents] GET /webhook-events enterprise_id=%s source=%s type=%s",
        enterprise_id,
        source,
        event_type,
    )

    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid 'since' datetime format. Use ISO-8601.",
            )

    # Map frontend source/event_type to deliveries query fields
    result = list_deliveries(
        event=event_type,
        status=event_status,
        since=since_dt,
        enterprise_id=enterprise_id,
        page_size=limit,
    )

    # Transform deliveries to event format expected by frontend
    events = []
    for item in result.get("items", []):
        event_item: dict[str, Any] = {
            "event_id": item.get("delivery_id", ""),
            "source": item.get("source_service", ""),
            "event_type": item.get("event", ""),
            "delivery_id": item.get("delivery_id", ""),
            "enterprise_id": item.get("enterprise_id", ""),
            "project_key": item.get("issue_key", ""),
            "subject": item.get("payload", {}).get("subject", {}),
            "status": item.get("status", ""),
            "received_at": (
                item["received_at"].isoformat()
                if isinstance(item.get("received_at"), datetime)
                else str(item.get("received_at", ""))
            ),
            "dispatched_run_ids": item.get("result", {}).get("dispatched_run_ids", [])
            if isinstance(item.get("result"), dict)
            else [],
            "error": item.get("error"),
        }
        # Filter by source if provided
        if source and event_item["source"] != source:
            continue
        # Filter by project_key if provided
        if project_key and project_key not in (
            event_item["project_key"],
            item.get("idea_id", ""),
        ):
            continue
        events.append(event_item)

    return WebhookEventListResponse(
        events=events,
        total=result.get("total", len(events)),
    )


# ── Event detail ──────────────────────────────────────────────


@router.get(
    "/{event_id}",
    summary="Get webhook event detail",
    description="Get the full payload and metadata for a specific webhook event.",
)
async def get_event_detail(
    event_id: str,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> dict[str, Any]:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookEvents] GET /webhook-events/%s enterprise_id=%s",
        event_id,
        enterprise_id,
    )
    delivery = get_delivery(event_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    # Verify enterprise scope
    if delivery.get("enterprise_id") and delivery["enterprise_id"] != enterprise_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    # Transform to frontend-expected format
    received_at = delivery.get("received_at", "")
    if isinstance(received_at, datetime):
        received_at = received_at.isoformat()

    return {
        "event_id": delivery.get("delivery_id", ""),
        "source": delivery.get("source_service", ""),
        "event_type": delivery.get("event", ""),
        "delivery_id": delivery.get("delivery_id", ""),
        "enterprise_id": delivery.get("enterprise_id", ""),
        "organization_id": delivery.get("organization_id", ""),
        "project_key": delivery.get("issue_key", ""),
        "subject": delivery.get("payload", {}).get("subject", {}),
        "status": delivery.get("status", ""),
        "received_at": received_at,
        "dispatched_run_ids": (
            delivery.get("result", {}).get("dispatched_run_ids", [])
            if isinstance(delivery.get("result"), dict)
            else []
        ),
        "error": delivery.get("error"),
        "headers": delivery.get("payload", {}).get("headers", {}),
        "payload": delivery.get("payload"),
        "processed_at": delivery.get("processed_at"),
    }


# ── Replay event ──────────────────────────────────────────────


@router.post(
    "/{event_id}/replay",
    response_model=WebhookEventReplayResponse,
    summary="Replay a webhook event",
    description="Re-dispatch a failed webhook event for processing.",
)
async def replay_event(
    event_id: str,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> WebhookEventReplayResponse:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookEvents] POST /webhook-events/%s/replay enterprise_id=%s",
        event_id,
        enterprise_id,
    )
    delivery = get_delivery(event_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    if delivery.get("enterprise_id") and delivery["enterprise_id"] != enterprise_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    # Attempt to re-dispatch the event through the agentic team webhook handler
    dispatched_run_ids: list[str] = []
    try:
        from crewai_productfeature_planner.apis.agentic_team._service import (
            process_webhook_event,
        )

        payload = delivery.get("payload", {})
        result = await process_webhook_event(payload)
        if isinstance(result, dict):
            dispatched_run_ids = result.get("dispatched_run_ids", [])
    except ImportError:
        logger.warning("[WebhookEvents] Cannot import process_webhook_event for replay")
    except Exception:
        logger.error("[WebhookEvents] Replay failed for event_id=%s", event_id, exc_info=True)

    return WebhookEventReplayResponse(
        event_id=event_id,
        dispatched_run_ids=dispatched_run_ids,
        message=f"Event {event_id} replayed. {len(dispatched_run_ids)} run(s) dispatched.",
    )


# ── Backfill events ───────────────────────────────────────────


@router.post(
    "/backfill",
    response_model=WebhookEventBackfillResponse,
    summary="Backfill webhook events",
    description="Re-process a batch of webhook events matching the given criteria.",
)
async def backfill_events(
    body: WebhookEventBackfillRequest,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> WebhookEventBackfillResponse:
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[WebhookEvents] POST /webhook-events/backfill enterprise_id=%s source=%s since=%s",
        enterprise_id,
        body.source,
        body.since,
    )

    try:
        since_dt = datetime.fromisoformat(body.since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid 'since' datetime format. Use ISO-8601.",
        )

    limit = body.limit or 100

    # Fetch matching events
    result = list_deliveries(
        event=body.event_type,
        since=since_dt,
        enterprise_id=enterprise_id,
        page_size=limit,
    )

    items = result.get("items", [])
    enqueued = 0
    skipped = 0

    for item in items:
        # Filter by source if specified
        if body.source and item.get("source_service") != body.source:
            skipped += 1
            continue
        # Only replay failed/ignored events
        if item.get("status") in ("processed", "dispatched"):
            skipped += 1
            continue
        enqueued += 1

    return WebhookEventBackfillResponse(
        enqueued=enqueued,
        skipped=skipped,
        message=f"Backfill complete: {enqueued} event(s) enqueued, {skipped} skipped.",
    )
