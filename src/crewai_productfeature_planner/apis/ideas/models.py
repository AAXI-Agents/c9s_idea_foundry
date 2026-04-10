"""Ideas API — shared Pydantic models and helpers.

Models:
    IdeaItem           — Single idea response
    IdeaListResponse   — Paginated list of ideas
    IdeaStatusUpdate   — Request body for PATCH status

Helpers:
    _idea_fields(doc)  — Extract IdeaItem fields from a MongoDB document
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Constants ─────────────────────────────────────────────────

VALID_STATUSES = {"inprogress", "completed", "paused", "failed", "archived"}
VALID_PAGE_SIZES = {5, 6, 10, 25, 50}
_TOTAL_SECTIONS = 12

# MongoDB projection for list queries — exclude heavy content fields
# that are not needed for the paginated idea list.  This avoids
# transferring multi-KB PRD text from Atlas for every list request.
IDEA_LIST_PROJECTION: dict[str, int] = {
    "_id": 0,
    # Heavy fields to exclude (each can be 10-100 KB):
    "finalized_idea": 0,
    "requirements_breakdown": 0,
    "refinement_options_history": 0,
    "jira_skeleton": 0,
    "jira_epics_stories_output": 0,
    "ux_design_content": 0,
    "output_file": 0,
    "ux_output_file": 0,
}


# ── Response models ───────────────────────────────────────────


class IdeaItem(BaseModel):
    run_id: str
    title: str = ""
    idea: str = ""
    finalized_idea: str = ""
    status: str = ""
    project_id: str = ""
    created_at: str = ""
    completed_at: str = ""
    sections_done: int = 0
    total_sections: int = 0
    iteration: int = 0
    confluence_url: str = ""
    jira_phase: str = ""
    ux_design_status: str = ""


class IdeaListResponse(BaseModel):
    items: list[IdeaItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Request models ────────────────────────────────────────────


class IdeaStatusUpdate(BaseModel):
    status: Literal["archived", "paused"] = Field(
        description="New status. Only 'archived' and 'paused' transitions are supported."
    )


# ── Helpers ───────────────────────────────────────────────────


def idea_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract IdeaItem-compatible fields from a MongoDB document."""
    status_val = doc.get("status", "unknown")

    section_obj = doc.get("section") or {}
    sections = [k for k, v in section_obj.items() if isinstance(v, list) and v]
    raw_exec = doc.get("executive_summary", [])
    has_exec = isinstance(raw_exec, list) and len(raw_exec) > 0
    exec_counted = "executive_summary" in sections
    sections_done = len(sections) + (1 if has_exec and not exec_counted else 0)
    if status_val == "completed":
        sections_done = _TOTAL_SECTIONS

    max_iter = 0
    for entries in section_obj.values():
        if isinstance(entries, list):
            for entry in entries:
                it = entry.get("iteration", 0) if isinstance(entry, dict) else 0
                if it > max_iter:
                    max_iter = it
    exec_iter_count = len(raw_exec) if isinstance(raw_exec, list) else 0
    effective_iter = max(max_iter, exec_iter_count)

    return {
        "run_id": doc.get("run_id", ""),
        "title": doc.get("title", ""),
        "idea": doc.get("idea", ""),
        "finalized_idea": doc.get("finalized_idea", ""),
        "status": status_val,
        "project_id": doc.get("project_id", ""),
        "created_at": doc.get("created_at", ""),
        "completed_at": doc.get("completed_at") or "",
        "sections_done": sections_done,
        "total_sections": _TOTAL_SECTIONS,
        "iteration": effective_iter,
        "confluence_url": doc.get("confluence_url", ""),
        "jira_phase": doc.get("jira_phase", ""),
        "ux_design_status": doc.get("ux_design_status", "") or doc.get("figma_design_status", ""),
    }
