"""Projects CRUD API — list, get, create, update, delete projects.

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

from crewai_productfeature_planner.apis.projects.router import router

__all__ = ["router"]
