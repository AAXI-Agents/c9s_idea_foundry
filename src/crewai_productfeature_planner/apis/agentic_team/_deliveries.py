"""REST endpoint for querying received webhook delivery audit trail.

GET /api/agentic-team/deliveries — List received deliveries with filters.
GET /api/agentic-team/deliveries/{delivery_id} — Get a single delivery.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis.agentic_team._config import (
    AGENTIC_TEAM_ENABLED,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.webhook_deliveries import (
    get_delivery,
    list_deliveries,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agentic-team", tags=["Agentic Team"])


@router.get(
    "/deliveries",
    summary="List received webhook deliveries",
    description=(
        "Returns a paginated list of received webhook deliveries from "
        "Agentic Team, with optional filters by event type, idea, and status. "
        "Results are scoped to the caller's tenant."
    ),
    response_model=dict[str, Any],
)
async def list_webhook_deliveries(
    user: dict = Depends(require_sso_user),
    event: str | None = Query(default=None, description="Filter by event type"),
    idea_id: str | None = Query(default=None, description="Filter by idea_id"),
    delivery_status: str | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    since: datetime | None = Query(default=None, description="Filter since datetime"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
) -> dict[str, Any]:
    """List received webhook deliveries with optional filters."""
    if not AGENTIC_TEAM_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agentic Team integration is not enabled",
        )

    logger.debug(
        "[AgenticTeamDeliveries] Listing deliveries: event=%s idea=%s status=%s user=%s",
        event, idea_id, delivery_status, user.get("user_id"),
    )

    result = list_deliveries(
        event=event,
        idea_id=idea_id,
        status=delivery_status,
        since=since,
        organization_id=user.get("organization_id"),
        enterprise_id=user.get("enterprise_id"),
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/deliveries/{delivery_id}",
    summary="Get a single webhook delivery record",
    description=(
        "Returns the full record of a received webhook delivery, "
        "including the original payload and processing result."
    ),
    response_model=dict[str, Any],
)
async def get_webhook_delivery(
    delivery_id: str,
    user: dict = Depends(require_sso_user),
) -> dict[str, Any]:
    """Retrieve a single delivery record by delivery_id."""
    if not AGENTIC_TEAM_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agentic Team integration is not enabled",
        )

    doc = get_delivery(delivery_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delivery not found: {delivery_id}",
        )

    # Tenant check — ensure the delivery belongs to the caller's org
    org_id = user.get("organization_id")
    if org_id and doc.get("organization_id") and doc["organization_id"] != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delivery not found: {delivery_id}",
        )

    return doc
