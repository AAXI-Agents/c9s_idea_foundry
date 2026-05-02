"""Admin API router — enterprise admin endpoints.

Provides:
    GET   /admin/organizations            — list orgs in enterprise
    GET   /admin/projects                 — list projects cross-org
    GET   /admin/projects/{id}/cascade-preview  — doc counts before reassign
    PATCH /admin/projects/{id}/tenant     — reassign project to another org
    GET   /admin/audit-log                — paginated audit log
"""

from crewai_productfeature_planner.apis.admin.router import router

__all__ = ["router"]
