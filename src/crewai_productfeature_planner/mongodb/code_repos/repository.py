"""Repository functions for the code_repos collection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    tenant_fields,
    tenant_filter,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

CODE_REPOS_COLLECTION = "codeRepos"


def _col():
    return get_db()[CODE_REPOS_COLLECTION]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_code_repo(
    *,
    project_id: str,
    url: str,
    name: str,
    owner: str,
    created_by: str,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Register a new code repository for a project.

    Args:
        project_id: Owning project.
        url: Full GitHub URL (e.g. https://github.com/org/repo).
        name: Repository name.
        owner: Repository owner/org.
        created_by: User who registered it.
        tenant: Tenant context.

    Returns:
        Created document dict or None on failure.
    """
    repo_id = uuid.uuid4().hex
    doc = {
        "repo_id": repo_id,
        "project_id": project_id,
        "url": url,
        "name": name,
        "owner": owner,
        "status": "pending",
        "analysis": None,
        "kb_path": None,
        "last_analyzed_at": None,
        "created_by": created_by,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        **(tenant_fields(tenant) if tenant else {}),
    }
    try:
        _col().insert_one(doc)
        logger.info(
            "[CodeRepos] Created repo=%s project=%s url=%s",
            repo_id,
            project_id,
            url,
        )
        doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[CodeRepos] Failed to create repo project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return None


def get_code_repo(
    *,
    repo_id: str,
    project_id: str,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Fetch a single code repo by ID."""
    try:
        doc = _col().find_one(
            {"repo_id": repo_id, "project_id": project_id, **tenant_filter(tenant)}
        )
        if doc:
            doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[CodeRepos] Failed to get repo=%s: %s", repo_id, exc, exc_info=True
        )
        return None


def list_code_repos(
    *,
    project_id: str,
    tenant: TenantContext | None = None,
) -> list[dict]:
    """List all code repos for a project."""
    try:
        cursor = _col().find(
            {"project_id": project_id, **tenant_filter(tenant)},
            sort=[("created_at", -1)],
        )
        docs = []
        for doc in cursor:
            doc.pop("_id", None)
            docs.append(doc)
        return docs
    except PyMongoError as exc:
        logger.error(
            "[CodeRepos] Failed to list repos project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return []


def update_code_repo(
    *,
    repo_id: str,
    project_id: str,
    updates: dict,
    tenant: TenantContext | None = None,
) -> bool:
    """Update fields on a code repo."""
    updates["updated_at"] = _now_iso()
    try:
        result = _col().update_one(
            {"repo_id": repo_id, "project_id": project_id, **tenant_filter(tenant)},
            {"$set": updates},
        )
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error(
            "[CodeRepos] Failed to update repo=%s: %s", repo_id, exc, exc_info=True
        )
        return False


def delete_code_repo(
    *,
    repo_id: str,
    project_id: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Delete a code repo record."""
    try:
        result = _col().delete_one(
            {"repo_id": repo_id, "project_id": project_id, **tenant_filter(tenant)}
        )
        if result.deleted_count > 0:
            logger.info("[CodeRepos] Deleted repo=%s project=%s", repo_id, project_id)
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[CodeRepos] Failed to delete repo=%s: %s", repo_id, exc, exc_info=True
        )
        return False


def set_analysis_result(
    *,
    repo_id: str,
    project_id: str,
    analysis: dict,
    kb_path: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Store the Coding Agent analysis result.

    Args:
        analysis: Dict with keys like architecture, apis, schema, dependencies.
        kb_path: Path in the knowledge base repo where results were committed.
    """
    return update_code_repo(
        repo_id=repo_id,
        project_id=project_id,
        updates={
            "analysis": analysis,
            "kb_path": kb_path,
            "status": "analyzed",
            "last_analyzed_at": _now_iso(),
        },
        tenant=tenant,
    )
