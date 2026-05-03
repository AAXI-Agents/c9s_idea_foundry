"""Admin API router — enterprise admin endpoints.

All endpoints require the ``enterprise_admin`` role.  Results are
scoped to the admin's enterprise (not global).

Endpoints:
    GET   /admin/organizations            — list orgs in enterprise
    GET   /admin/projects                 — list projects cross-org
    GET   /admin/projects/{id}/cascade-preview  — doc counts before reassign
    PATCH /admin/projects/{id}/tenant     — reassign project to another org
    GET   /admin/audit-log                — paginated audit log
"""

from __future__ import annotations

from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis.admin.models import (
    AdminProjectItem,
    AdminProjectListResponse,
    AuditLogEntry,
    AuditLogResponse,
    CascadePreviewResponse,
    OrganizationItem,
    OrganizationListResponse,
    TenantReassignRequest,
    TenantReassignResponse,
)
from crewai_productfeature_planner.apis.admin_deps import require_enterprise_admin
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_enterprise_admin)],
)


# ---------------------------------------------------------------------------
# GET /admin/organizations
# ---------------------------------------------------------------------------


@router.get(
    "/organizations",
    response_model=OrganizationListResponse,
    summary="List organizations in the enterprise",
)
async def list_organizations(
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> OrganizationListResponse:
    """Return all organizations within the authenticated admin's enterprise.

    Derives the organization list by aggregating distinct organization_id
    values from projectConfig documents scoped to the enterprise.
    """
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[Admin] list_organizations called by user_id=%s enterprise_id=%s",
        user.get("user_id"),
        enterprise_id,
    )

    from crewai_productfeature_planner.mongodb.async_client import get_async_db
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        PROJECT_CONFIG_COLLECTION,
    )

    db = get_async_db()
    coll = db[PROJECT_CONFIG_COLLECTION]

    # Aggregate distinct organizations with project counts
    pipeline = [
        {"$match": {"enterprise_id": enterprise_id}},
        {
            "$group": {
                "_id": "$organization_id",
                "organization_name": {"$first": "$organization_name"},
                "project_count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    results = await coll.aggregate(pipeline).to_list(length=500)

    items = [
        OrganizationItem(
            organization_id=doc["_id"] or "",
            organization_name=doc.get("organization_name") or "",
            project_count=doc.get("project_count", 0),
        )
        for doc in results
        if doc["_id"]  # Skip documents without organization_id
    ]

    return OrganizationListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# GET /admin/projects
# ---------------------------------------------------------------------------


@router.get(
    "/projects",
    response_model=AdminProjectListResponse,
    summary="List all projects across orgs (enterprise-scoped)",
)
async def list_admin_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    organization_id: str | None = Query(default=None, description="Filter to specific org"),
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> AdminProjectListResponse:
    """Return paginated projects across all orgs in the enterprise."""
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[Admin] list_admin_projects by user_id=%s enterprise=%s org_filter=%s",
        user.get("user_id"),
        enterprise_id,
        organization_id,
    )

    from crewai_productfeature_planner.mongodb.async_client import get_async_db
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        PROJECT_CONFIG_COLLECTION,
    )

    db = get_async_db()
    coll = db[PROJECT_CONFIG_COLLECTION]

    query: dict[str, Any] = {"enterprise_id": enterprise_id}
    if organization_id:
        query["organization_id"] = organization_id

    total = await coll.count_documents(query)
    skip = (page - 1) * page_size
    cursor = coll.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(page_size)
    docs = await cursor.to_list(length=page_size)

    items = [
        AdminProjectItem(
            project_id=d.get("project_id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            organization_id=d.get("organization_id", ""),
            organization_name=d.get("organization_name", ""),
            enterprise_id=d.get("enterprise_id", ""),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
        )
        for d in docs
    ]

    return AdminProjectListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# GET /admin/projects/{project_id}/cascade-preview
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/cascade-preview",
    response_model=CascadePreviewResponse,
    summary="Preview document counts before tenant reassignment",
)
async def cascade_preview(
    project_id: str,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> CascadePreviewResponse:
    """Return counts of documents that would be affected by reassignment."""
    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[Admin] cascade_preview project_id=%s by user_id=%s",
        project_id,
        user.get("user_id"),
    )

    from crewai_productfeature_planner.mongodb.async_client import get_async_db
    from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
        CREW_JOBS_COLLECTION,
    )
    from crewai_productfeature_planner.mongodb.product_requirements.repository import (
        PRODUCT_REQUIREMENTS_COLLECTION,
    )
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        PROJECT_CONFIG_COLLECTION,
    )
    from crewai_productfeature_planner.mongodb.working_ideas._common import (
        WORKING_COLLECTION,
    )

    db = get_async_db()

    # Verify project belongs to this enterprise
    project = await db[PROJECT_CONFIG_COLLECTION].find_one(
        {"project_id": project_id, "enterprise_id": enterprise_id},
        {"_id": 0},
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found in this enterprise.",
        )

    # Count related documents
    ideas_count = await db[WORKING_COLLECTION].count_documents(
        {"project_id": project_id}
    )
    jobs_count = await db[CREW_JOBS_COLLECTION].count_documents(
        {"project_id": project_id}
    )
    reqs_count = await db[PRODUCT_REQUIREMENTS_COLLECTION].count_documents(
        {"project_id": project_id}
    )

    total = ideas_count + jobs_count + reqs_count

    return CascadePreviewResponse(
        project_id=project_id,
        project_name=project.get("name", ""),
        current_organization_id=project.get("organization_id", ""),
        current_organization_name=project.get("organization_name", ""),
        working_ideas_count=ideas_count,
        crew_jobs_count=jobs_count,
        product_requirements_count=reqs_count,
        total_documents=total,
    )


# ---------------------------------------------------------------------------
# PATCH /admin/projects/{project_id}/tenant
# ---------------------------------------------------------------------------


@router.patch(
    "/projects/{project_id}/tenant",
    response_model=TenantReassignResponse,
    summary="Reassign project to another organization",
)
async def reassign_project_tenant(
    project_id: str,
    body: TenantReassignRequest,
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> TenantReassignResponse:
    """Reassign a project and its related documents to a new org.

    Cascades the organization_id update to workingIdeas, crewJobs,
    and productRequirements. Creates an audit log entry.
    """
    enterprise_id = user.get("enterprise_id", "")
    actor_id = user.get("user_id", "")
    actor_email = user.get("email", "")
    logger.info(
        "[Admin] reassign_project_tenant project_id=%s to_org=%s by user_id=%s",
        project_id,
        body.to_organization_id,
        actor_id,
    )

    from crewai_productfeature_planner.mongodb.admin_audit_log import (
        create_audit_entry,
    )
    from crewai_productfeature_planner.mongodb.async_client import get_async_db
    from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
        CREW_JOBS_COLLECTION,
    )
    from crewai_productfeature_planner.mongodb.product_requirements.repository import (
        PRODUCT_REQUIREMENTS_COLLECTION,
    )
    from crewai_productfeature_planner.mongodb.project_config.repository import (
        PROJECT_CONFIG_COLLECTION,
    )
    from crewai_productfeature_planner.mongodb.working_ideas._common import (
        WORKING_COLLECTION,
    )

    db = get_async_db()

    # Verify project belongs to this enterprise
    project = await db[PROJECT_CONFIG_COLLECTION].find_one(
        {"project_id": project_id, "enterprise_id": enterprise_id},
        {"_id": 0},
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found in this enterprise.",
        )

    from_org_id = project.get("organization_id", "")
    from_org_name = project.get("organization_name", "")
    to_org_id = body.to_organization_id
    to_org_name = body.to_organization_name

    if from_org_id == to_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project is already in the target organization.",
        )

    # Cascade update to all related collections
    update_fields = {"$set": {"organization_id": to_org_id}}
    cascaded = 0

    # Update project config
    await db[PROJECT_CONFIG_COLLECTION].update_one(
        {"project_id": project_id, "enterprise_id": enterprise_id},
        {"$set": {"organization_id": to_org_id, "organization_name": to_org_name}},
    )

    # Update working ideas (defense-in-depth: also filter by enterprise_id)
    result = await db[WORKING_COLLECTION].update_many(
        {"project_id": project_id, "enterprise_id": enterprise_id},
        update_fields,
    )
    cascaded += result.modified_count

    # Update crew jobs
    result = await db[CREW_JOBS_COLLECTION].update_many(
        {"project_id": project_id, "enterprise_id": enterprise_id},
        update_fields,
    )
    cascaded += result.modified_count

    # Update product requirements
    result = await db[PRODUCT_REQUIREMENTS_COLLECTION].update_many(
        {"project_id": project_id, "enterprise_id": enterprise_id},
        update_fields,
    )
    cascaded += result.modified_count

    # Create audit log entry
    audit_doc = create_audit_entry(
        action="project_reassignment",
        actor_id=actor_id,
        actor_email=actor_email,
        project_id=project_id,
        project_name=project.get("name", ""),
        from_organization_id=from_org_id,
        from_organization_name=from_org_name,
        to_organization_id=to_org_id,
        to_organization_name=to_org_name,
        cascaded_documents=cascaded,
        enterprise_id=enterprise_id,
    )

    logger.info(
        "[Admin] Reassigned project_id=%s from org=%s to org=%s cascaded=%d",
        project_id,
        from_org_id,
        to_org_id,
        cascaded,
    )

    return TenantReassignResponse(
        project_id=project_id,
        project_name=project.get("name", ""),
        from_organization_id=from_org_id,
        from_organization_name=from_org_name,
        to_organization_id=to_org_id,
        to_organization_name=to_org_name,
        cascaded_documents=cascaded,
        audit_id=audit_doc.get("audit_id", ""),
    )


# ---------------------------------------------------------------------------
# GET /admin/audit-log
# ---------------------------------------------------------------------------


@router.get(
    "/audit-log",
    response_model=AuditLogResponse,
    summary="Paginated audit log of admin actions",
)
async def list_audit_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None, description="Filter by action type"),
    user: dict[str, Any] = Depends(require_enterprise_admin),
) -> AuditLogResponse:
    """Return paginated audit log entries for the enterprise."""
    from crewai_productfeature_planner.mongodb._tenant import TenantContext
    from crewai_productfeature_planner.mongodb.admin_audit_log import (
        list_audit_entries,
    )
    from crewai_productfeature_planner.rbac import Role

    enterprise_id = user.get("enterprise_id", "")
    logger.info(
        "[Admin] list_audit_log by user_id=%s enterprise=%s action=%s",
        user.get("user_id"),
        enterprise_id,
        action,
    )

    tenant = TenantContext(
        enterprise_id=enterprise_id,
        organization_id="",
        role=Role.ENT_ADMIN,
    )

    items_raw, total = list_audit_entries(
        tenant=tenant,
        action=action,
        page=page,
        page_size=page_size,
    )

    items = []
    for doc in items_raw:
        ts = doc.get("timestamp")
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        items.append(
            AuditLogEntry(
                audit_id=doc.get("audit_id", ""),
                action=doc.get("action", ""),
                actor_id=doc.get("actor_id", ""),
                actor_email=doc.get("actor_email", ""),
                project_id=doc.get("project_id", ""),
                project_name=doc.get("project_name", ""),
                from_organization_id=doc.get("from_organization_id", ""),
                from_organization_name=doc.get("from_organization_name", ""),
                to_organization_id=doc.get("to_organization_id", ""),
                to_organization_name=doc.get("to_organization_name", ""),
                cascaded_documents=doc.get("cascaded_documents", 0),
                timestamp=str(ts) if ts else "",
            )
        )

    return AuditLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
