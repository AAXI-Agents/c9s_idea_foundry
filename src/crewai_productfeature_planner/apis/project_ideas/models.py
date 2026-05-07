"""Project Ideas API — Pydantic models.

Models:
    IdeaFeatureItem        — Single feature within an idea
    ProjectIdeaItem        — Full idea response
    ProjectIdeaListResponse — Paginated list of ideas
    CreateIdeaRequest      — POST body for creating an idea
    UpdateIdeaRequest      — PATCH body for updating an idea
    UpdateIdeaStatusRequest — PATCH body for status transitions
    UpdateFeaturesRequest  — PATCH body for feature updates
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class IdeaFeatureItem(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    jira_epic_key: str | None = None
    completion_pct: float = 0.0


class ProjectIdeaItem(BaseModel):
    idea_id: str
    project_id: str = ""
    title: str = ""
    description: str = ""
    status: str = "draft"
    features: list[IdeaFeatureItem] = Field(default_factory=list)
    overall_completion: float = 0.0
    active_run_id: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    ideation_session_id: str | None = None
    design_url: str | None = None
    design_url_type: str | None = None
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    # Phase B0: extra fields for Features tab (completed ideas)
    completed_at: str = ""
    confluence_url: str | None = None
    jira_epic_key: str | None = None
    prd_summary: str = ""


class ProjectIdeaListResponse(BaseModel):
    items: list[ProjectIdeaItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateIdeaRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500, description="Idea title")
    description: str = Field(default="", max_length=10000, description="Idea description")
    ideation_session_id: str | None = Field(
        default=None, description="Link to ideation session that spawned this idea"
    )


class UpdateIdeaRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)


class UpdateIdeaStatusRequest(BaseModel):
    status: Literal["active", "in_progress", "completed", "archived"] = Field(
        description="New status for the idea"
    )


class UpdateFeaturesRequest(BaseModel):
    features: list[IdeaFeatureItem] = Field(
        min_length=0, description="Replacement features array"
    )


def idea_response_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract ProjectIdeaItem-compatible fields from a MongoDB document."""
    features = doc.get("features") or []
    return {
        "idea_id": doc.get("idea_id", ""),
        "project_id": doc.get("project_id", ""),
        "title": doc.get("title", ""),
        "description": doc.get("description", ""),
        "status": doc.get("status", "draft"),
        "features": [
            IdeaFeatureItem(
                id=f.get("id", ""),
                name=f.get("name", ""),
                description=f.get("description", ""),
                jira_epic_key=f.get("jira_epic_key"),
                completion_pct=f.get("completion_pct", 0.0),
            )
            for f in features
        ],
        "overall_completion": doc.get("overall_completion", 0.0),
        "active_run_id": doc.get("active_run_id"),
        "run_ids": doc.get("run_ids") or [],
        "ideation_session_id": doc.get("ideation_session_id"),
        "design_url": doc.get("design_url"),
        "design_url_type": doc.get("design_url_type"),
        "created_by": doc.get("created_by", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        # Phase B0: extra fields for Features tab (populated by enrich_completed_fields)
        "completed_at": doc.get("completed_at", ""),
        "confluence_url": doc.get("confluence_url"),
        "jira_epic_key": doc.get("jira_epic_key"),
        "prd_summary": doc.get("prd_summary", ""),
    }
