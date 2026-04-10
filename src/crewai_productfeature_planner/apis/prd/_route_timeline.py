"""GET /flow/runs/{run_id}/timeline — unified PRD journey timeline.

Stitches data from ``workingIdeas``, ``crewJobs``, and ``agentInteraction``
collections into a single chronological timeline suitable for the
ChatGPT-style conversation view in the web app.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Response models ───────────────────────────────────────────────────


class TimelineEvent(BaseModel):
    """A single event in the PRD journey timeline."""

    timestamp: str = Field(..., description="ISO-8601 timestamp.")
    event_type: str = Field(
        ...,
        description=(
            "Event category: 'idea_submitted', 'idea_refined', "
            "'exec_summary_iteration', 'section_drafted', "
            "'section_approved', 'agent_interaction', 'job_status', "
            "'confluence_published', 'jira_created'."
        ),
    )
    title: str = Field(..., description="Short human-readable title.")
    detail: str = Field(default="", description="Longer description or content excerpt.")
    agent: str = Field(default="", description="Agent name involved (if any).")
    section_key: str = Field(default="", description="PRD section key (if applicable).")
    iteration: int = Field(default=0, description="Iteration number (if applicable).")
    score: str = Field(default="", description="Quality score (if applicable).")
    metadata: dict = Field(default_factory=dict, description="Extra context.")


class TimelineResponse(BaseModel):
    """Full PRD journey timeline."""

    run_id: str = Field(..., description="Flow run identifier.")
    total_events: int = Field(..., description="Total number of timeline events.")
    events: list[TimelineEvent] = Field(
        default_factory=list,
        description="Chronological list of events (oldest first).",
    )


# ── Helpers ───────────────────────────────────────────────────────────


def _iso(val) -> str:
    """Coerce a datetime or string to ISO-8601 string."""
    if val is None:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _build_timeline(run_id: str, limit: int) -> list[TimelineEvent]:
    """Query all three collections and merge into a sorted timeline."""
    from crewai_productfeature_planner.mongodb.agent_interactions import (
        find_interactions,
    )
    from crewai_productfeature_planner.mongodb.crew_jobs import find_job
    from crewai_productfeature_planner.mongodb.product_requirements import (
        get_delivery_record,
    )
    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_run_any_status,
    )

    events: list[TimelineEvent] = []

    # ── Working idea events ───────────────────────────────────────
    idea_doc = find_run_any_status(run_id)
    if idea_doc:
        # Idea submission
        events.append(TimelineEvent(
            timestamp=_iso(idea_doc.get("created_at", "")),
            event_type="idea_submitted",
            title="Idea submitted",
            detail=idea_doc.get("idea", "")[:500],
        ))

        # Refined idea
        if idea_doc.get("finalized_idea"):
            events.append(TimelineEvent(
                timestamp=_iso(idea_doc.get("update_date", "")),
                event_type="idea_refined",
                title="Idea refined",
                detail=idea_doc["finalized_idea"][:500],
            ))

        # Executive summary iterations
        for es in idea_doc.get("executive_summary", []):
            events.append(TimelineEvent(
                timestamp=_iso(es.get("updated_date", "")),
                event_type="exec_summary_iteration",
                title=f"Executive Summary — iteration {es.get('iteration', '?')}",
                detail=es.get("content", "")[:300],
                section_key="executive_summary",
                iteration=es.get("iteration", 0),
                score=es.get("critique", "")[:200] if es.get("critique") else "",
            ))

        # Section iterations + approval decisions
        sections = idea_doc.get("section", {})
        if isinstance(sections, dict):
            for section_key, iterations in sections.items():
                if not isinstance(iterations, list):
                    continue
                for idx, it in enumerate(iterations):
                    events.append(TimelineEvent(
                        timestamp=_iso(it.get("updated_date", "")),
                        event_type="section_drafted",
                        title=f"Section '{section_key}' — iteration {it.get('iteration', '?')}",
                        detail=it.get("content", "")[:300],
                        section_key=section_key,
                        iteration=it.get("iteration", 0),
                        score=it.get("critique", "")[:200] if it.get("critique") else "",
                    ))
                # Emit approval annotation after the last iteration
                if iterations:
                    last = iterations[-1]
                    events.append(TimelineEvent(
                        timestamp=_iso(last.get("updated_date", "")),
                        event_type="section_approved",
                        title=f"Section '{section_key}' approved",
                        detail=f"Approved after {len(iterations)} iteration(s)",
                        section_key=section_key,
                        iteration=last.get("iteration", 0),
                    ))

        # Completion
        if idea_doc.get("completed_at"):
            events.append(TimelineEvent(
                timestamp=_iso(idea_doc["completed_at"]),
                event_type="job_status",
                title="PRD completed",
                detail=f"Status: {idea_doc.get('status', 'completed')}",
            ))

    # ── Job lifecycle events ──────────────────────────────────────
    job_doc = find_job(run_id)
    if job_doc:
        if job_doc.get("queued_at"):
            events.append(TimelineEvent(
                timestamp=_iso(job_doc["queued_at"]),
                event_type="job_status",
                title="Job queued",
                metadata={"queue_time_human": job_doc.get("queue_time_human", "")},
            ))
        if job_doc.get("started_at"):
            events.append(TimelineEvent(
                timestamp=_iso(job_doc["started_at"]),
                event_type="job_status",
                title="Job started",
            ))

    # ── Agent interactions ────────────────────────────────────────
    interactions = find_interactions(run_id=run_id, limit=limit)
    for doc in interactions:
        events.append(TimelineEvent(
            timestamp=_iso(doc.get("created_at", "")),
            event_type="agent_interaction",
            title=f"Agent: {doc.get('intent', 'unknown')}",
            detail=doc.get("agent_response", "")[:300],
            agent=doc.get("source", ""),
            metadata={
                "interaction_id": doc.get("interaction_id", ""),
                "user_message": doc.get("user_message", "")[:200],
            },
        ))

    # ── Delivery events ───────────────────────────────────────────
    delivery = get_delivery_record(run_id)
    if delivery:
        if delivery.get("confluence_published"):
            events.append(TimelineEvent(
                timestamp=_iso(delivery.get("updated_at", "")),
                event_type="confluence_published",
                title="Published to Confluence",
                detail=delivery.get("confluence_url", ""),
                metadata={"page_id": delivery.get("confluence_page_id", "")},
            ))
        if delivery.get("jira_completed"):
            tickets = delivery.get("jira_tickets", [])
            events.append(TimelineEvent(
                timestamp=_iso(delivery.get("updated_at", "")),
                event_type="jira_created",
                title=f"Jira tickets created ({len(tickets)})",
                detail=", ".join(t.get("key", "") for t in tickets[:10]),
                metadata={"ticket_count": len(tickets)},
            ))

    # Sort by timestamp ascending (oldest first)
    events.sort(key=lambda e: e.timestamp or "")

    return events[:limit]


# ── Endpoint ──────────────────────────────────────────────────────────


@router.get(
    "/flow/runs/{run_id}/timeline",
    tags=["Flow Runs"],
    summary="Get unified PRD journey timeline",
    response_model=TimelineResponse,
    description=(
        "Returns a chronological timeline of all events for a PRD run — "
        "from idea submission through agent interactions, section iterations, "
        "approvals, and delivery. Stitches data from ``workingIdeas``, "
        "``crewJobs``, ``agentInteraction``, and ``productRequirements``."
    ),
    responses={
        200: {"description": "Timeline returned successfully."},
        404: {"description": "Run not found."},
        500: {"description": "Internal server error."},
        503: {"description": "Service unavailable."},
    },
)
async def get_run_timeline(
    run_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_sso_user),
):
    """Return the full PRD journey timeline for a run."""
    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_run_any_status,
    )

    idea_doc = find_run_any_status(run_id)
    if idea_doc is None:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        events = _build_timeline(run_id, limit=limit)
    except Exception as exc:
        logger.error(
            "[Timeline] Failed to build timeline for run_id=%s: %s",
            run_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to build timeline",
        ) from exc

    return TimelineResponse(
        run_id=run_id,
        total_events=len(events),
        events=events,
    )
