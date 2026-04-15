"""Repository for the ``projectConfig`` collection.

Stores project-level configuration including Confluence space keys,
Jira project keys, reference URLs, and
Slack-uploaded document refs.  Each project has a UUID
``project_id`` that can be referenced by working ideas to bind
runs to a specific project context.

Document schema::

    {
        "project_id":                str,   # UUID hex (primary key)
        "name":                      str,   # human-readable project name
        "confluence_space_key":      str,   # Confluence space for this project
        "jira_project_key":          str,   # Jira project for this project
        "confluence_parent_id":      str,   # optional Confluence parent page ID
        "reference_urls":            [str], # public URLs for context/research
        "slack_file_refs":           [      # documents uploaded via Slack
            {
                "file_id":     str,
                "name":        str,
                "url":         str,
                "uploaded_at": str,    # ISO-8601
            }
        ],
        "design_preferences":        {      # UX/UI design style preferences
            "style":       str,              # e.g. "material", "minimal"
            "brand_colors": [str],           # hex colour codes
            "typography":  str,              # font family or style
        },
        "review_checklists":         [      # custom review checklists
            {
                "name":   str,               # checklist name
                "items":  [str],             # checklist items
            }
        ],
        "technical_profile":         {      # detected/configured tech stack
            "languages":  [str],             # e.g. ["Python", "TypeScript"]
            "frameworks": [str],             # e.g. ["FastAPI", "React"]
            "infra":      [str],             # e.g. ["AWS", "Docker"]
        },
        "board_style":               str,   # "scrum" (default) or "kanban"
        "created_at":                str,   # ISO-8601
        "updated_at":                str,   # ISO-8601
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    tenant_fields,
    tenant_filter,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_CONFIG_COLLECTION = "projectConfig"


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_project(
    *,
    name: str,
    description: str = "",
    confluence_space_key: str = "",
    jira_project_key: str = "",
    confluence_parent_id: str = "",
    reference_urls: list[str] | None = None,
    slack_file_refs: list[dict[str, str]] | None = None,
    design_preferences: dict[str, Any] | None = None,
    review_checklists: list[dict[str, Any]] | None = None,
    technical_profile: dict[str, Any] | None = None,
    board_style: str = "scrum",
    tenant: TenantContext | None = None,
) -> str | None:
    """Create a new project configuration document.

    Args:
        name: Human-readable project name.
        description: Optional project description text.
        confluence_space_key: Confluence space key for publishing.
        jira_project_key: Jira project key for ticket creation.
        confluence_parent_id: Optional Confluence parent page ID.
        reference_urls: Optional list of public reference URLs.
        slack_file_refs: Optional list of Slack file reference dicts
            (each with ``file_id``, ``name``, ``url``, ``uploaded_at``).

    Returns:
        The generated ``project_id`` (UUID hex) on success, or ``None``.
    """
    project_id = uuid.uuid4().hex
    now = _now_iso()

    doc: dict[str, Any] = {
        "project_id": project_id,
        "name": name,
        "description": description,
        "confluence_space_key": confluence_space_key,
        "jira_project_key": jira_project_key,
        "confluence_parent_id": confluence_parent_id,
        "reference_urls": reference_urls or [],
        "slack_file_refs": slack_file_refs or [],
        "design_preferences": design_preferences or {},
        "review_checklists": review_checklists or [],
        "technical_profile": technical_profile or {},
        "board_style": board_style,
        "created_at": now,
        "updated_at": now,
        **(tenant_fields(tenant) if tenant else {}),
    }

    try:
        get_db()[PROJECT_CONFIG_COLLECTION].insert_one(doc)
        logger.info(
            "[MongoDB] Created project config: project_id=%s name=%s",
            project_id,
            name,
        )

        # Bootstrap the Obsidian project knowledge folder
        try:
            from crewai_productfeature_planner.scripts.project_knowledge import (
                sync_project_knowledge,
            )
            sync_project_knowledge(project_id)
        except Exception:  # noqa: BLE001
            logger.debug(
                "[MongoDB] Could not sync project knowledge for "
                "project_id=%s",
                project_id,
                exc_info=True,
            )

        return project_id
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to create project config for name=%s: %s",
            name,
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_project(
    project_id: str,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Fetch a single project configuration by ``project_id``.

    Returns:
        The project document (without MongoDB ``_id``) or ``None``.
    """
    try:
        query: dict[str, Any] = {"project_id": project_id}
        if tenant:
            query.update(tenant_filter(tenant))
        doc = get_db()[PROJECT_CONFIG_COLLECTION].find_one(
            query,
            {"_id": 0},
        )
        return doc
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to fetch project config project_id=%s: %s",
            project_id,
            exc,
        )
        return None


def get_project_by_name(name: str) -> dict[str, Any] | None:
    """Fetch a single project configuration by ``name``.

    Returns:
        The project document (without MongoDB ``_id``) or ``None``.
    """
    try:
        doc = get_db()[PROJECT_CONFIG_COLLECTION].find_one(
            {"name": name},
            {"_id": 0},
        )
        return doc
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to fetch project config name=%s: %s",
            name,
            exc,
        )
        return None


def list_projects(
    limit: int = 100,
    tenant: TenantContext | None = None,
) -> list[dict[str, Any]]:
    """List project configurations, newest first.

    Args:
        limit: Maximum number of results (default 100).
        tenant: Tenant context for data isolation.

    Returns:
        List of project documents (without ``_id``).
    """
    try:
        query = tenant_filter(tenant) if tenant else {}
        cursor = (
            get_db()[PROJECT_CONFIG_COLLECTION]
            .find(query, {"_id": 0})
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error("[MongoDB] Failed to list project configs: %s", exc)
        return []


def get_project_for_run(run_id: str) -> dict[str, Any] | None:
    """Look up the project config associated with a PRD run.

    Reads the ``project_id`` field from the ``workingIdeas`` document
    for *run_id*, then fetches the corresponding project config.

    Returns:
        The project config document or ``None`` if not linked.
    """
    try:
        db = get_db()
        doc = db["workingIdeas"].find_one(
            {"run_id": run_id},
            {"project_id": 1, "_id": 0},
        )
        if not doc or not doc.get("project_id"):
            return None
        return get_project(doc["project_id"])
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to look up project for run_id=%s: %s",
            run_id,
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_project(
    project_id: str,
    tenant: TenantContext | None = None,
    **fields: Any,
) -> int:
    """Update fields on an existing project configuration.

    Accepts any top-level field names as keyword arguments.  The
    ``updated_at`` timestamp is always refreshed.

    Returns:
        Number of documents modified (0 or 1).
    """
    if not fields:
        return 0

    fields["updated_at"] = _now_iso()

    try:
        query: dict[str, Any] = {"project_id": project_id}
        if tenant:
            query.update(tenant_filter(tenant))
        result = get_db()[PROJECT_CONFIG_COLLECTION].update_one(
            query,
            {"$set": fields},
        )
        logger.info(
            "[MongoDB] Updated project config project_id=%s fields=%s (matched=%d)",
            project_id,
            list(fields.keys()),
            result.modified_count,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to update project config project_id=%s: %s",
            project_id,
            exc,
        )
        return 0


def add_reference_url(project_id: str, url: str) -> int:
    """Append a reference URL to the project's ``reference_urls`` array.

    Uses ``$addToSet`` to avoid duplicates.

    Returns:
        Number of documents modified (0 or 1).
    """
    try:
        result = get_db()[PROJECT_CONFIG_COLLECTION].update_one(
            {"project_id": project_id},
            {
                "$addToSet": {"reference_urls": url},
                "$set": {"updated_at": _now_iso()},
            },
        )
        logger.info(
            "[MongoDB] Added reference URL to project_id=%s: %s",
            project_id,
            url,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to add reference URL to project_id=%s: %s",
            project_id,
            exc,
        )
        return 0


def add_slack_file_ref(
    project_id: str,
    *,
    file_id: str,
    name: str,
    url: str,
) -> int:
    """Append a Slack file reference to the project.

    Returns:
        Number of documents modified (0 or 1).
    """
    ref = {
        "file_id": file_id,
        "name": name,
        "url": url,
        "uploaded_at": _now_iso(),
    }
    try:
        result = get_db()[PROJECT_CONFIG_COLLECTION].update_one(
            {"project_id": project_id},
            {
                "$push": {"slack_file_refs": ref},
                "$set": {"updated_at": _now_iso()},
            },
        )
        logger.info(
            "[MongoDB] Added Slack file ref to project_id=%s: file_id=%s name=%s",
            project_id,
            file_id,
            name,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to add Slack file ref to project_id=%s: %s",
            project_id,
            exc,
        )
        return 0


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def delete_project(
    project_id: str,
    tenant: TenantContext | None = None,
) -> int:
    """Delete a project configuration by ``project_id``.

    Returns:
        Number of documents deleted (0 or 1).
    """
    try:
        query: dict[str, Any] = {"project_id": project_id}
        if tenant:
            query.update(tenant_filter(tenant))
        result = get_db()[PROJECT_CONFIG_COLLECTION].delete_one(
            query,
        )
        logger.info(
            "[MongoDB] Deleted project config project_id=%s (count=%d)",
            project_id,
            result.deleted_count,
        )
        return result.deleted_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to delete project config project_id=%s: %s",
            project_id,
            exc,
        )
        return 0
