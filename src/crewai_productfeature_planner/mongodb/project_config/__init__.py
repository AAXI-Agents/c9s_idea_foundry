"""Project Configuration sub-package — operations on the ``projectConfig`` collection."""

from crewai_productfeature_planner.mongodb.project_config.repository import (
    PROJECT_CONFIG_COLLECTION,
    create_project,
    delete_project,
    get_project,
    get_project_by_name,
    get_project_for_run,
    list_projects,
    update_project,
)

__all__ = [
    "PROJECT_CONFIG_COLLECTION",
    "create_project",
    "delete_project",
    "get_project",
    "get_project_by_name",
    "get_project_for_run",
    "list_projects",
    "update_project",
]
