"""Deliverables route for project ideas.

GET /projects/{project_id}/ideas/{idea_id}/deliverables — Aggregated PRD sections view
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from crewai_productfeature_planner.apis.admin_deps import resolve_tenant_context
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.ideas.repository import get_idea
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/{idea_id}/deliverables",
    summary="Get idea deliverables",
    description=(
        "Returns an aggregated view of all deliverables for this idea: "
        "PRD sections, executive summary, design URLs, Confluence page, "
        "and Jira tickets."
    ),
)
async def get_idea_deliverables(
    project_id: str,
    idea_id: str,
    user: dict = Depends(require_sso_user),
):
    """Aggregate all deliverables for an idea."""
    from crewai_productfeature_planner.mongodb.working_ideas import (
        find_run_any_status,
    )
    from crewai_productfeature_planner.mongodb.product_requirements import (
        get_delivery_record,
    )

    tenant = resolve_tenant_context(user)

    doc = get_idea(idea_id=idea_id, tenant=tenant)
    if not doc or doc.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Idea not found")

    run_ids = doc.get("run_ids", [])
    active_run_id = doc.get("active_run_id")

    # Aggregate deliverables from the most recent run
    target_run_id = active_run_id or (run_ids[-1] if run_ids else None)

    deliverables: dict = {
        "idea_id": idea_id,
        "title": doc.get("title", ""),
        "status": doc.get("status", ""),
        "prd_sections": [],
        "executive_summary": None,
        "requirements_breakdown": None,
        "confluence_url": None,
        "jira_output": None,
        "design_url": doc.get("design_url"),
        "design_url_type": doc.get("design_url_type"),
        "output_file": None,
        "run_id": target_run_id,
    }

    if not target_run_id:
        return deliverables

    # Get working idea (PRD sections)
    wi_doc = find_run_any_status(target_run_id, tenant=tenant)
    if wi_doc:
        deliverables["executive_summary"] = wi_doc.get("finalized_idea")
        deliverables["confluence_url"] = wi_doc.get("confluence_url")
        deliverables["jira_output"] = wi_doc.get("jira_output")
        deliverables["output_file"] = wi_doc.get("output_file")

        # Extract PRD sections with their latest content
        section_data = wi_doc.get("section", {})
        for section_key, iterations in section_data.items():
            if not isinstance(iterations, list) or not iterations:
                continue
            # Get the latest iteration
            latest = iterations[-1] if iterations else {}
            if isinstance(latest, dict):
                deliverables["prd_sections"].append({
                    "key": section_key,
                    "content": latest.get("content", ""),
                    "iteration": latest.get("iteration", 0),
                    "is_approved": latest.get("is_approved", False),
                    "critique": latest.get("critique", ""),
                })

        # UX design content
        if wi_doc.get("ux_design_content"):
            deliverables["ux_design"] = {
                "content": wi_doc["ux_design_content"],
                "status": wi_doc.get("ux_design_status", ""),
            }

    # Get product requirements (delivery records)
    pr_doc = get_delivery_record(target_run_id, tenant=tenant)
    if pr_doc:
        deliverables["confluence_url"] = (
            deliverables["confluence_url"] or pr_doc.get("confluence_url")
        )
        deliverables["jira_output"] = (
            deliverables["jira_output"] or pr_doc.get("jira_output")
        )

    return deliverables
