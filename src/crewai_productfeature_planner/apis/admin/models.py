"""Pydantic models for admin API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrganizationItem(BaseModel):
    """An organization within the enterprise."""

    organization_id: str = Field(..., description="Organization ID")
    organization_name: str = Field(default="", description="Organization display name")
    project_count: int = Field(default=0, description="Number of projects in this org")


class OrganizationListResponse(BaseModel):
    """Response for GET /admin/organizations."""

    items: list[OrganizationItem] = Field(default_factory=list)
    total: int = Field(default=0)


class AdminProjectItem(BaseModel):
    """Project item for admin cross-org listing."""

    project_id: str
    name: str = ""
    description: str = ""
    organization_id: str = ""
    organization_name: str = ""
    enterprise_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class AdminProjectListResponse(BaseModel):
    """Response for GET /admin/projects."""

    items: list[AdminProjectItem] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    page_size: int = Field(default=20)


class CascadePreviewResponse(BaseModel):
    """Response for GET /admin/projects/{id}/cascade-preview."""

    project_id: str
    project_name: str = ""
    current_organization_id: str = ""
    current_organization_name: str = ""
    working_ideas_count: int = Field(default=0, description="Working ideas linked to this project")
    crew_jobs_count: int = Field(default=0, description="Crew jobs linked to this project")
    product_requirements_count: int = Field(default=0, description="Product requirements docs")
    total_documents: int = Field(default=0, description="Total documents that would be cascaded")


class TenantReassignRequest(BaseModel):
    """Request body for PATCH /admin/projects/{id}/tenant."""

    to_organization_id: str = Field(..., description="Target organization ID")
    to_organization_name: str = Field(default="", description="Target organization name")


class TenantReassignResponse(BaseModel):
    """Response for PATCH /admin/projects/{id}/tenant."""

    project_id: str
    project_name: str = ""
    from_organization_id: str = ""
    from_organization_name: str = ""
    to_organization_id: str = ""
    to_organization_name: str = ""
    cascaded_documents: int = Field(default=0)
    audit_id: str = ""


class AuditLogEntry(BaseModel):
    """A single audit log entry."""

    id: str = Field(default="", alias="audit_id")
    action: str = ""
    actor_id: str = ""
    actor_email: str = ""
    project_id: str = ""
    project_name: str = ""
    from_organization_id: str = ""
    from_organization_name: str = ""
    to_organization_id: str = ""
    to_organization_name: str = ""
    cascaded_documents: int = 0
    timestamp: str = ""

    class Config:
        populate_by_name = True


class AuditLogResponse(BaseModel):
    """Response for GET /admin/audit-log."""

    items: list[AuditLogEntry] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    page_size: int = Field(default=20)
