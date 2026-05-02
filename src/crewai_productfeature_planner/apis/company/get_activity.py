"""GET /company/activity — Paginated activity feed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from crewai_productfeature_planner.apis.company.models import ActivityEvent, ActivityListResponse
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.company_activity import count_events, list_events
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/activity",
    response_model=ActivityListResponse,
    summary="List company activity events",
)
async def list_activity(
    event_type: str | None = Query(default=None, description="Filter by event type"),
    agent_id: str | None = Query(default=None, description="Filter by agent ID"),
    department: str | None = Query(default=None, description="Filter by department"),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    skip: int = Query(default=0, ge=0, description="Offset"),
    user: dict = Depends(require_sso_user),
) -> ActivityListResponse:
    """Return paginated activity events for the company dashboard."""
    tenant = TenantContext.from_user(user)
    org_id = tenant.organization_id if tenant else None

    events_raw = list_events(
        event_type=event_type,
        agent_id=agent_id,
        department=department,
        organization_id=org_id,
        limit=limit,
        skip=skip,
    )
    total = count_events(
        event_type=event_type,
        agent_id=agent_id,
        department=department,
        organization_id=org_id,
    )

    events = [ActivityEvent(**e) for e in events_raw]
    return ActivityListResponse(events=events, total=total)
