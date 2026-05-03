"""PRD flow router -- status, listing, and job endpoints.

Action endpoints (kickoff, approve, pause, resume) live in
``_route_actions.py`` and are included via ``action_router``.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from crewai_productfeature_planner.apis.prd.models import (
    ActivityEvent,
    ActivityLogResponse,
    ErrorResponse,
    JobDetail,
    JobListResponse,
    PRDDraftDetail,
    PRDResumableListResponse,
    PRDResumableRun,
    PRDRunStatusResponse,
    PRDSectionDetail,
)
from crewai_productfeature_planner.apis.shared import (
    runs,
)
from crewai_productfeature_planner.apis.admin_deps import resolve_tenant_context
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.crew_jobs import (
    find_job,
    list_jobs,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

from crewai_productfeature_planner.apis.prd._route_actions import (
    _ERROR_RESPONSES,
    action_router,
)
from crewai_productfeature_planner.apis.prd.service import restore_prd_state
from crewai_productfeature_planner.apis.prd._route_timeline import (
    router as timeline_router,
)
from crewai_productfeature_planner.apis.prd._route_ux_design import (
    ux_design_router,
)
from crewai_productfeature_planner.apis.prd._route_versions import (
    router as versions_router,
)
from crewai_productfeature_planner.apis.prd._route_websocket import (
    ws_router,
)

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_sso_user)])
router.include_router(action_router)
router.include_router(timeline_router)
router.include_router(versions_router)
router.include_router(ux_design_router)

# WebSocket router has no SSO dependency (auth is per-message / token-based).
ws_only_router = APIRouter()
ws_only_router.include_router(ws_router)


# ── Helpers ───────────────────────────────────────────────────


def _build_agent_roster(
    run_id: str,
    *,
    tenant: TenantContext | None = None,
) -> tuple[list[dict], bool]:
    """Build agent roster data for a run by aggregating interactions.

    Returns:
        (roster_items, cost_tracking_available)
    """
    from crewai_productfeature_planner.mongodb.agent_interactions import (
        find_interactions,
    )
    from crewai_productfeature_planner.mongodb.agent_registry import (
        list_agents,
    )

    # Get all interactions for this run
    interactions = find_interactions(run_id=run_id, limit=500, tenant=tenant)

    # Build per-agent aggregation from interactions
    agent_data: dict[str, dict] = {}
    cost_available = False
    for doc in interactions:
        meta = doc.get("metadata") or {}
        agent_id = meta.get("agent_id")
        if not agent_id:
            continue

        if agent_id not in agent_data:
            agent_data[agent_id] = {
                "tokens_used": 0,
                "cost_usd": 0.0,
                "last_activity_at": None,
            }
        entry = agent_data[agent_id]
        entry["tokens_used"] += meta.get("tokens_delta", 0)
        entry["cost_usd"] += meta.get("cost_usd_delta", 0.0)
        if meta.get("tokens_delta", 0) > 0:
            cost_available = True

        created = doc.get("created_at")
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        elif created is not None:
            created = str(created)
        if created and (
            entry["last_activity_at"] is None
            or created > entry["last_activity_at"]
        ):
            entry["last_activity_at"] = created

    # Enrich with registry data
    registry = {a["agent_id"]: a for a in list_agents()}

    roster = []
    for aid, data in agent_data.items():
        reg = registry.get(aid, {})
        roster.append({
            "id": aid,
            "name": reg.get("display_name", aid),
            "role": reg.get("role", ""),
            "title": reg.get("title", ""),
            "reports_to": reg.get("reports_to"),
            "status": reg.get("status", "idle"),
            "current_step": None,
            "last_activity_at": data["last_activity_at"],
            "tokens_used": data["tokens_used"],
            "cost_usd": round(data["cost_usd"], 6),
        })

    return roster, cost_available


def _build_run_response(run) -> dict:
    """Build a PRDRunStatusResponse dict from an in-memory FlowRun."""
    draft = run.current_draft
    approved_count = sum(1 for s in draft.sections if s.is_approved)
    total_sections = len(draft.sections)
    current_section = (
        draft.get_section(run.current_section_key)
        if run.current_section_key
        else None
    )
    current_step = current_section.step if current_section else 0
    data = run.model_dump()
    data["current_draft"] = PRDDraftDetail(
        sections=[
            PRDSectionDetail(**s.model_dump()) for s in draft.sections
        ],
        all_approved=draft.all_approved(),
    ).model_dump()
    data["sections_approved"] = approved_count
    data["sections_total"] = total_sections
    data["current_step"] = current_step
    # Agent roster
    try:
        roster, cost_avail = _build_agent_roster(run.run_id)
        data["agents"] = roster
        data["cost_tracking_available"] = cost_avail
    except Exception:
        logger.debug("[PRD] Failed to build agent roster for run_id=%s", run.run_id, exc_info=True)
        data["agents"] = []
        data["cost_tracking_available"] = False
    return data


def _build_run_response_from_db(
    run_id: str,
    tenant: TenantContext | None = None,
) -> dict:
    """Reconstruct a run-status response from MongoDB.

    Queries ``crewJobs`` for lifecycle metadata and ``workingIdeas`` for
    draft content so that runs survive server restarts.
    """
    from crewai_productfeature_planner.apis.prd.models import (
        ExecutiveSummaryDraft,
        PRDDraft,
    )

    job = find_job(run_id, tenant=tenant)
    if job is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Attempt to rebuild draft from workingIdeas.
    idea_doc: dict = {}
    try:
        (
            idea, draft, exec_summary,
            requirements_breakdown, _bh, _rh,
        ) = restore_prd_state(run_id)
        # Keep the raw doc around for UX design fields.
        from crewai_productfeature_planner.mongodb.working_ideas import (
            find_run_any_status,
        )
        idea_doc = find_run_any_status(run_id, tenant=tenant) or {}
    except Exception:
        logger.debug(
            "[PRD] Could not restore draft for run_id=%s, using empty draft",
            run_id,
        )
        idea = job.get("idea", "")
        draft = PRDDraft.create_empty()
        exec_summary = ExecutiveSummaryDraft()
        requirements_breakdown = ""

    def _iso(val):
        if val is None:
            return None
        return val.isoformat() if hasattr(val, "isoformat") else str(val)

    approved_count = sum(1 for s in draft.sections if s.is_approved)
    total_sections = len(draft.sections)
    total_iterations = max(
        (s.iteration for s in draft.sections), default=0,
    )

    result = {
        "run_id": run_id,
        "flow_name": job.get("flow_name", "prd"),
        "status": job.get("status", "unknown"),
        "iteration": total_iterations,
        "created_at": _iso(job.get("queued_at")) or "",
        "update_date": _iso(job.get("updated_at")),
        "completed_at": _iso(job.get("completed_at")),
        "result": None,
        "error": job.get("error"),
        "current_section_key": "",
        "current_step": 0,
        "sections_approved": approved_count,
        "sections_total": total_sections,
        "active_agents": [],
        "dropped_agents": [],
        "agent_errors": {},
        "original_idea": idea,
        "idea_refined": False,
        "finalized_idea": idea,
        "requirements_breakdown": requirements_breakdown,
        "executive_summary": exec_summary.model_dump(),
        "confluence_url": job.get("confluence_url", ""),
        "jira_output": "",
        "output_file": job.get("output_file", ""),
        "ux_design_status": (
            idea_doc.get("ux_design_status")
            or idea_doc.get("figma_design_status")
            or ""
        ),
        "ux_design_content": idea_doc.get("ux_design_content", ""),
        "current_draft": PRDDraftDetail(
            sections=[
                PRDSectionDetail(**s.model_dump()) for s in draft.sections
            ],
            all_approved=draft.all_approved(),
        ).model_dump(),
    }
    # Agent roster enrichment
    try:
        roster, cost_avail = _build_agent_roster(run_id, tenant=tenant)
        result["agents"] = roster
        result["cost_tracking_available"] = cost_avail
    except Exception:
        logger.debug("[PRD] Failed to build agent roster for run_id=%s", run_id, exc_info=True)
        result["agents"] = []
        result["cost_tracking_available"] = False
    return result


@router.get(
    "/flow/runs/{run_id}",
    tags=["Flow Runs"],
    summary="Get flow run status",
    response_model=PRDRunStatusResponse,
    description=(
        "Returns the current status, iteration, section progress, and draft "
        "content for a flow run. Includes per-section approval status, "
        "current step number, and agent participation details.\n\n"
        "The flow uses a **two-phase architecture**:\n"
        "- **Phase 1** -- Executive Summary: iterative refinement.\n"
        "- **Phase 2** -- 9 remaining sections: each auto-iterates between "
        "PRD_SECTION_MIN_ITERATIONS and PRD_SECTION_MAX_ITERATIONS cycles.\n\n"
        "Use this endpoint to poll for state changes after kickoff, "
        "approval, pause, or resume actions."
    ),
    responses={
        200: {"description": "Run details returned successfully."},
        404: {"description": "Run not found."},
        **_ERROR_RESPONSES,
    },
)
async def get_run_status(run_id: str, user: dict = Depends(require_sso_user)):
    """Check the status of a flow run."""
    from crewai_productfeature_planner.apis.shared import run_visible_to_tenant

    tenant = TenantContext.from_user(user)
    run = runs.get(run_id)
    if run is not None:
        if not run_visible_to_tenant(run, tenant):
            raise HTTPException(status_code=404, detail="Run not found")
        return _build_run_response(run)

    # Fallback: reconstruct from MongoDB for runs lost after restart.
    return _build_run_response_from_db(run_id, tenant=tenant)


@router.get(
    "/flow/runs/{run_id}/activity",
    tags=["Flow Runs"],
    summary="Get agent activity log for a run",
    response_model=ActivityLogResponse,
    description=(
        "Returns agent interaction events associated with a flow run. "
        "Events are returned newest-first from the ``agentInteraction`` "
        "MongoDB collection. Use ``limit`` to control the number of "
        "events returned."
    ),
    responses={
        200: {"description": "Activity log returned successfully."},
        **_ERROR_RESPONSES,
    },
)
async def get_run_activity(
    run_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    user: dict = Depends(require_sso_user),
):
    """Return agent activity events for a flow run."""
    from crewai_productfeature_planner.mongodb.agent_interactions import (
        find_interactions,
    )

    tenant = TenantContext.from_user(user)
    try:
        docs = find_interactions(run_id=run_id, limit=limit, tenant=tenant)
    except Exception as exc:
        logger.error(
            "[PRD] Failed to query activity for run_id=%s: %s",
            run_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to query activity log",
        ) from exc

    events = []
    for doc in docs:
        created = doc.get("created_at")
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        meta = doc.get("metadata") or {}
        # Derive severity from metadata flags
        severity = "info"
        if meta.get("error") or doc.get("intent") == "error":
            severity = "error"
        elif meta.get("retry") or meta.get("rate_limited"):
            severity = "warn"
        elif meta.get("debug"):
            severity = "debug"
        events.append(ActivityEvent(
            interaction_id=doc.get("interaction_id", ""),
            source=doc.get("source", ""),
            intent=doc.get("intent", ""),
            agent_response=doc.get("agent_response", ""),
            run_id=doc.get("run_id"),
            user_id=doc.get("user_id"),
            created_at=str(created) if created else "",
            predicted_next_step=doc.get("predicted_next_step"),
            agent_id=meta.get("agent_id"),
            severity=severity,
            tokens_delta=meta.get("tokens_delta", 0),
            cost_usd_delta=meta.get("cost_usd_delta", 0.0),
            summary=doc.get("agent_response", "")[:120],
        ))

    return ActivityLogResponse(
        run_id=run_id,
        count=len(events),
        events=events,
    )


@router.get(
    "/flow/runs",
    tags=["Flow Runs"],
    summary="List all flow runs",
    description=(
        "Returns all in-memory flow runs. Useful for dashboards and MCP "
        "clients to discover active, paused, or completed runs."
    ),
    responses={
        200: {"description": "List of all runs."},
        **_ERROR_RESPONSES,
    },
)
async def list_runs(
    organization_id: str | None = Query(
        default=None,
        description="Filter by organization (enterprise admins only)",
    ),
    user: dict = Depends(require_sso_user),
):
    # Start with active in-memory runs.
    from crewai_productfeature_planner.apis.shared import run_visible_to_tenant

    tenant = resolve_tenant_context(user, organization_id)
    seen: set[str] = set()
    result = []
    for run in runs.values():
        if not run_visible_to_tenant(run, tenant):
            continue
        seen.add(run.run_id)
        result.append({
            "run_id": run.run_id,
            "flow_name": run.flow_name,
            "status": run.status.value,
            "iteration": run.iteration,
            "created_at": run.created_at,
            "current_section_key": run.current_section_key,
        })

    # Supplement with persistent jobs from MongoDB.
    try:
        db_jobs = list_jobs(limit=100, tenant=tenant)
    except Exception:
        db_jobs = []
    for doc in db_jobs:
        job_id = doc.get("job_id", "")
        if job_id in seen:
            continue
        seen.add(job_id)
        queued = doc.get("queued_at")
        result.append({
            "run_id": job_id,
            "flow_name": doc.get("flow_name", "prd"),
            "status": doc.get("status", "unknown"),
            "iteration": 0,
            "created_at": (
                queued.isoformat()
                if hasattr(queued, "isoformat")
                else str(queued or "")
            ),
            "current_section_key": "",
        })

    return {"count": len(result), "runs": result}


@router.get(
    "/flow/prd/resumable",
    tags=["Flow Runs"],
    summary="List resumable (unfinalized) runs",
    response_model=PRDResumableListResponse,
    description=(
        "Returns a list of working ideas from MongoDB that have not been "
        "finalized. These are runs that were paused, abandoned, or "
        "interrupted and can be resumed via POST /flow/prd/resume."
    ),
    responses={
        200: {"description": "Resumable runs listed successfully."},
        **_ERROR_RESPONSES,
    },
)
async def list_resumable_runs(user: dict = Depends(require_sso_user)):
    from crewai_productfeature_planner.mongodb import find_unfinalized

    tenant = TenantContext.from_user(user)
    try:
        unfinalized = find_unfinalized(tenant=tenant)
    except Exception as exc:
        logger.error("[PRD] Failed to query resumable runs: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query resumable runs") from exc
    items = []
    for r in unfinalized:
        created = r.get("created_at")
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        items.append(PRDResumableRun(
            run_id=r["run_id"],
            idea=r.get("idea", ""),
            iteration=r.get("iteration", 0),
            created_at=str(created) if created else None,
            sections=r.get("sections", []),
            exec_summary_iterations=r.get("exec_summary_iterations", 0),
            req_breakdown_iterations=r.get("req_breakdown_iterations", 0),
        ))
    return PRDResumableListResponse(count=len(items), runs=items)


def _job_doc_to_detail(doc: dict) -> JobDetail:
    """Convert a raw MongoDB job document to a ``JobDetail`` response model."""

    def _iso(val):
        if val is None:
            return None
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    return JobDetail(
        job_id=doc.get("job_id", ""),
        flow_name=doc.get("flow_name", ""),
        idea=doc.get("idea", ""),
        status=doc.get("status", "unknown"),
        error=doc.get("error"),
        queued_at=_iso(doc.get("queued_at")),
        started_at=_iso(doc.get("started_at")),
        completed_at=_iso(doc.get("completed_at")),
        queue_time_ms=doc.get("queue_time_ms"),
        queue_time_human=doc.get("queue_time_human"),
        running_time_ms=doc.get("running_time_ms"),
        running_time_human=doc.get("running_time_human"),
        updated_at=_iso(doc.get("updated_at")),
        output_file=doc.get("output_file"),
        confluence_url=doc.get("confluence_url"),
    )


@router.get(
    "/flow/jobs",
    tags=["Jobs"],
    summary="List all persistent job records",
    response_model=JobListResponse,
    description=(
        "Returns job records from the ``crewJobs`` MongoDB collection."
    ),
    responses={
        200: {"description": "Job list returned successfully."},
        **_ERROR_RESPONSES,
    },
)
async def list_all_jobs(
    status: str | None = None,
    flow_name: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    organization_id: str | None = Query(
        default=None,
        description="Filter by organization (enterprise admins only)",
    ),
    user: dict = Depends(require_sso_user),
):
    """List persistent job records, optionally filtered."""
    tenant = resolve_tenant_context(user, organization_id)
    try:
        docs = list_jobs(status=status, flow_name=flow_name, limit=limit, tenant=tenant)
    except Exception as exc:
        logger.error("[PRD] Failed to list jobs: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list jobs") from exc
    items = [_job_doc_to_detail(d) for d in docs]
    return JobListResponse(count=len(items), jobs=items)


@router.get(
    "/flow/jobs/{job_id}",
    tags=["Jobs"],
    summary="Get a single job record",
    response_model=JobDetail,
    description=(
        "Returns a single job record by ``job_id`` from the ``crewJobs`` "
        "collection. Includes lifecycle timestamps and computed durations."
    ),
    responses={
        200: {"description": "Job details returned successfully."},
        404: {"description": "Job not found."},
        **_ERROR_RESPONSES,
    },
)
async def get_job(job_id: str, user: dict = Depends(require_sso_user)):
    """Fetch a single persistent job record."""
    tenant = TenantContext.from_user(user)
    try:
        doc = find_job(job_id, tenant=tenant)
    except Exception as exc:
        logger.error("[PRD] Failed to find job %s: %s", job_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to find job") from exc
    if doc is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_doc_to_detail(doc)
