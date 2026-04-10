"""Projects API — shared Pydantic models and helpers.

Models:
    ProjectCreate       — Request body for POST /projects
    ProjectUpdate       — Request body for PATCH /projects/{project_id}
    ProjectItem         — Single project response
    ProjectListResponse — Paginated list of projects

Helpers:
    project_fields(doc) — Extract ProjectItem fields from a MongoDB document
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Constants ─────────────────────────────────────────────────

VALID_PAGE_SIZES = {5, 6, 10, 25, 50}


# ── Request models ────────────────────────────────────────────


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    confluence_space_key: str = Field(default="", max_length=50)
    jira_project_key: str = Field(default="", max_length=50)
    confluence_parent_id: str = Field(default="", max_length=50)
    reference_urls: list[str] = Field(default_factory=list, max_length=20)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    confluence_space_key: str | None = None
    jira_project_key: str | None = None
    confluence_parent_id: str | None = None


# ── Response models ───────────────────────────────────────────


class ProjectItem(BaseModel):
    project_id: str
    name: str
    description: str = ""
    confluence_space_key: str = ""
    jira_project_key: str = ""
    confluence_parent_id: str = ""
    reference_urls: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class ProjectListResponse(BaseModel):
    items: list[ProjectItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Helpers ───────────────────────────────────────────────────


def project_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract ProjectItem-compatible fields from a MongoDB document."""
    return {
        "project_id": doc.get("project_id", ""),
        "name": doc.get("name", ""),
        "description": doc.get("description", ""),
        "confluence_space_key": doc.get("confluence_space_key", ""),
        "jira_project_key": doc.get("jira_project_key", ""),
        "confluence_parent_id": doc.get("confluence_parent_id", ""),
        "reference_urls": doc.get("reference_urls", []),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }
