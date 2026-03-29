"""PRD flow router -- status, listing, and job endpoints.

Action endpoints (kickoff, approve, pause, resume) live in
``_route_actions.py`` and are included via ``action_router``.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from crewai_productfeature_planner.apis.prd.models import (
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
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.crew_jobs import (
    find_job,
    list_jobs,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

from crewai_productfeature_planner.apis.prd._route_actions import (
    _ERROR_RESPONSES,
    action_router,
)

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_sso_user)])
router.include_router(action_router)


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
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    draft = run.current_draft
    approved_count = sum(1 for s in draft.sections if s.is_approved)
    total_sections = len(draft.sections)
    current_section = draft.get_section(run.current_section_key) if run.current_section_key else None
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
    return data


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
async def list_runs(user: dict = Depends(require_sso_user)):
    result = []
    for run in runs.values():
        result.append({
            "run_id": run.run_id,
            "flow_name": run.flow_name,
            "status": run.status.value,
            "iteration": run.iteration,
            "created_at": run.created_at,
            "current_section_key": run.current_section_key,
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

    try:
        unfinalized = find_unfinalized()
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
    user: dict = Depends(require_sso_user),
):
    """List persistent job records, optionally filtered."""
    try:
        docs = list_jobs(status=status, flow_name=flow_name, limit=limit)
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
    try:
        doc = find_job(job_id)
    except Exception as exc:
        logger.error("[PRD] Failed to find job %s: %s", job_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to find job") from exc
    if doc is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_doc_to_detail(doc)
