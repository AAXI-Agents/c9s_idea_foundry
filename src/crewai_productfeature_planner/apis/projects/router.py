"""Projects CRUD router — assembles all project route modules.

Route modules:
    get_projects.py     — GET /projects (paginated list)
    get_project.py      — GET /projects/{project_id}
    post_project.py     — POST /projects (create)
    patch_project.py    — PATCH /projects/{project_id} (update)
    delete_project.py   — DELETE /projects/{project_id}

Shared:
    models.py           — ProjectCreate, ProjectUpdate, ProjectItem,
                          ProjectListResponse, project_fields()
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from crewai_productfeature_planner.apis.projects.get_projects import router as get_projects_router
from crewai_productfeature_planner.apis.projects.get_project import router as get_project_router
from crewai_productfeature_planner.apis.projects.post_project import router as post_project_router
from crewai_productfeature_planner.apis.projects.patch_project import router as patch_project_router
from crewai_productfeature_planner.apis.projects.delete_project import router as delete_project_router
from crewai_productfeature_planner.apis.sso_auth import require_sso_user

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
    dependencies=[Depends(require_sso_user)],
)
router.include_router(get_projects_router)
router.include_router(get_project_router)
router.include_router(post_project_router)
router.include_router(patch_project_router)
router.include_router(delete_project_router)
