"""Flow integration routes for project ideas.

POST   /projects/{project_id}/ideas/{idea_id}/start    — Start PRD flow for idea
GET    /projects/{project_id}/ideas/{idea_id}/progress  — Get flow progress
POST   /projects/{project_id}/ideas/{idea_id}/resume    — Resume paused flow
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from crewai_productfeature_planner.apis.admin_deps import resolve_tenant_context
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.ideas.repository import (
    get_idea,
    set_active_run,
    update_idea_status,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── POST /{idea_id}/start ─────────────────────────────────────


class _StartIdeaFlowRequest:
    """Empty body — all context comes from the idea document."""


@router.post(
    "/{idea_id}/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start PRD flow for this idea",
    description=(
        "Kicks off the PRD generation flow using the idea's title and "
        "description as input. The idea status transitions to `in_progress` "
        "and the new run_id is linked as `active_run_id`."
    ),
)
async def start_idea_flow(
    project_id: str,
    idea_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_sso_user),
):
    """Start PRD flow for an idea."""
    tenant = resolve_tenant_context(user)
    from crewai_productfeature_planner.apis.shared import FlowRun, runs
    from crewai_productfeature_planner.mongodb.crew_jobs import (
        create_job,
        find_active_job,
    )
    from crewai_productfeature_planner.mongodb.working_ideas import (
        save_project_ref,
    )
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow

    # Validate idea exists and belongs to project
    doc = get_idea(idea_id=idea_id, tenant=tenant)
    if not doc or doc.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Must be in draft or active status to start
    idea_status = doc.get("status", "")
    if idea_status not in ("draft", "active"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start flow: idea status is '{idea_status}'. "
            "Only draft or active ideas can start a new flow.",
        )

    # Check no active run already in progress
    if doc.get("active_run_id"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Idea already has an active run "
                f"(run_id={doc['active_run_id']}). "
                "Resume or complete it first."
            ),
        )

    # Enforce single active job
    active = find_active_job(tenant=tenant)
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A job is already active (job_id={active['job_id']}). "
                "Only one job can run at a time."
            ),
        )

    # Build idea text from title + description
    idea_text = doc.get("title", "")
    if doc.get("description"):
        idea_text += "\n\n" + doc["description"]

    # Create flow run
    run_id = uuid.uuid4().hex[:12]
    run = FlowRun(
        run_id=run_id,
        flow_name="prd",
        enterprise_id=tenant.enterprise_id if tenant else "",
        organization_id=tenant.organization_id if tenant else "",
    )
    runs[run_id] = run

    # Persist job
    create_job(job_id=run_id, flow_name="prd", idea=idea_text, tenant=tenant)
    save_project_ref(run_id, project_id, idea=idea_text, tenant=tenant)

    # Link run to idea
    set_active_run(idea_id=idea_id, run_id=run_id, tenant=tenant)
    update_idea_status(idea_id=idea_id, status="in_progress", tenant=tenant)

    logger.info(
        "[ProjectIdeas] Starting PRD flow for idea_id=%s, run_id=%s",
        idea_id, run_id,
    )

    # Kick off flow in background (auto-approve for idea workflow)
    background_tasks.add_task(
        run_prd_flow, run_id, idea_text, True,
        tenant_dict=tenant.to_dict() if tenant else None,
    )

    return {
        "idea_id": idea_id,
        "run_id": run_id,
        "status": "in_progress",
        "message": (
            f"PRD flow started. Poll GET /projects/{project_id}/ideas/"
            f"{idea_id}/progress for status."
        ),
    }


# ── GET /{idea_id}/progress ───────────────────────────────────


@router.get(
    "/{idea_id}/progress",
    summary="Get idea flow progress",
    description=(
        "Returns aggregated progress for the idea's active (or most recent) "
        "PRD flow run, including section completion, current phase, and status."
    ),
)
async def get_idea_progress(
    project_id: str,
    idea_id: str,
    user: dict = Depends(require_sso_user),
):
    """Get progress info for an idea's flow."""
    tenant = resolve_tenant_context(user)
    from crewai_productfeature_planner.apis.shared import runs
    from crewai_productfeature_planner.mongodb.crew_jobs import find_job
    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_run_any_status,
    )

    doc = get_idea(idea_id=idea_id, tenant=tenant)
    if not doc or doc.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Idea not found")

    run_id = doc.get("active_run_id")
    if not run_id:
        # No active run — return basic status from idea
        return {
            "idea_id": idea_id,
            "status": doc.get("status", "draft"),
            "active_run_id": None,
            "flow_status": None,
            "sections_approved": 0,
            "sections_total": 0,
            "iteration": 0,
            "overall_completion": doc.get("overall_completion", 0.0),
            "current_phase": None,
            "error": None,
        }

    # Check in-memory first (running flows)
    run = runs.get(run_id)
    if run:
        draft = run.current_draft
        approved_count = sum(1 for s in draft.sections if s.is_approved)
        total_sections = len(draft.sections)
        current_phase = _determine_phase(run)
        return {
            "idea_id": idea_id,
            "status": doc.get("status"),
            "active_run_id": run_id,
            "flow_status": run.status.value,
            "sections_approved": approved_count,
            "sections_total": total_sections,
            "iteration": run.iteration,
            "overall_completion": doc.get("overall_completion", 0.0),
            "current_phase": current_phase,
            "current_section_key": run.current_section_key,
            "error": run.error,
        }

    # Fall back to DB (completed/paused flows)
    job = find_job(run_id, tenant=tenant)
    if not job:
        return {
            "idea_id": idea_id,
            "status": doc.get("status"),
            "active_run_id": run_id,
            "flow_status": "unknown",
            "sections_approved": 0,
            "sections_total": 0,
            "iteration": 0,
            "overall_completion": doc.get("overall_completion", 0.0),
            "current_phase": None,
            "error": None,
        }

    # Try to get section data from workingIdeas
    wi_doc = find_run_any_status(run_id, tenant=tenant)
    sections_approved = 0
    sections_total = 10  # Default PRD section count
    if wi_doc and wi_doc.get("section"):
        sections_total = len(wi_doc["section"])
        sections_approved = sum(
            1 for v in wi_doc["section"].values()
            if isinstance(v, list) and any(
                isinstance(it, dict) and it.get("is_approved")
                for it in v
            )
        )

    return {
        "idea_id": idea_id,
        "status": doc.get("status"),
        "active_run_id": run_id,
        "flow_status": job.get("status", "unknown"),
        "sections_approved": sections_approved,
        "sections_total": sections_total,
        "iteration": 0,
        "overall_completion": doc.get("overall_completion", 0.0),
        "current_phase": "completed" if job.get("status") == "completed" else "paused",
        "error": job.get("error"),
    }


# ── POST /{idea_id}/resume ────────────────────────────────────


@router.post(
    "/{idea_id}/resume",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Resume paused flow for this idea",
    description=(
        "Resumes a paused PRD flow that is linked to this idea. "
        "The idea must have an `active_run_id` and the flow must be paused."
    ),
)
async def resume_idea_flow(
    project_id: str,
    idea_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_sso_user),
):
    """Resume a paused PRD flow for an idea."""
    tenant = resolve_tenant_context(user)
    from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs
    from crewai_productfeature_planner.mongodb.crew_jobs import find_job
    from crewai_productfeature_planner.apis.prd.service import resume_prd_flow

    doc = get_idea(idea_id=idea_id, tenant=tenant)
    if not doc or doc.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Idea not found")

    run_id = doc.get("active_run_id")
    if not run_id:
        raise HTTPException(
            status_code=409,
            detail="No active run to resume. Start a flow first.",
        )

    # Verify the job is paused
    job = find_job(run_id, tenant=tenant)
    if not job:
        raise HTTPException(status_code=404, detail="Flow run not found")

    job_status = job.get("status", "")
    if job_status not in ("paused", "queued"):
        raise HTTPException(
            status_code=409,
            detail=f"Flow is not resumable (status='{job_status}').",
        )

    # Re-create in-memory run if needed
    if run_id not in runs:
        runs[run_id] = FlowRun(
            run_id=run_id,
            flow_name="prd",
            status=FlowStatus.PAUSED,
            enterprise_id=tenant.enterprise_id if tenant else "",
            organization_id=tenant.organization_id if tenant else "",
        )

    logger.info(
        "[ProjectIdeas] Resuming flow for idea_id=%s, run_id=%s",
        idea_id, run_id,
    )

    background_tasks.add_task(
        resume_prd_flow, run_id, True,
        tenant_dict=tenant.to_dict() if tenant else None,
    )

    return {
        "idea_id": idea_id,
        "run_id": run_id,
        "status": "resuming",
        "message": "Flow resumed. Poll progress endpoint for updates.",
    }


# ── Helpers ───────────────────────────────────────────────────


def _determine_phase(run) -> str:
    """Determine the current high-level phase of a flow run."""
    from crewai_productfeature_planner.apis.shared import FlowStatus

    if run.status == FlowStatus.COMPLETED:
        return "completed"
    if run.status == FlowStatus.PAUSED:
        return "paused"
    if not run.idea_refined:
        return "idea_refinement"
    if not run.requirements_breakdown:
        return "requirements"
    if run.current_section_key == "executive_summary":
        return "executive_summary"
    if run.current_section_key:
        return "section_drafting"
    return "running"
