"""Repository functions for the knowledge_documents collection."""

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

KNOWLEDGE_DOCUMENTS_COLLECTION = "knowledgeDocuments"

# Max file size: 25 MB
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
# Max URL fetch body: 10 MB
MAX_URL_FETCH_BYTES = 10 * 1024 * 1024

# Blocked media MIME prefixes for URL ingestion
BLOCKED_MEDIA_PREFIXES = ("video/", "audio/", "image/")


def _col():
    return get_db()[KNOWLEDGE_DOCUMENTS_COLLECTION]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_knowledge_document(
    *,
    project_id: str,
    source_type: str,
    filename: str | None = None,
    url: str | None = None,
    file_size: int | None = None,
    content_type: str | None = None,
    gcs_path: str | None = None,
    created_by: str,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Create a new knowledge document record.

    Args:
        project_id: Owning project.
        source_type: 'upload' or 'url'.
        filename: Original filename (uploads).
        url: Source URL (url ingestion).
        file_size: Size in bytes.
        content_type: MIME type.
        gcs_path: GCS object key.
        created_by: User ID.
        tenant: Tenant context for multi-tenancy.

    Returns:
        The created document dict, or None on failure.
    """
    doc_id = uuid.uuid4().hex
    doc = {
        "doc_id": doc_id,
        "project_id": project_id,
        "source_type": source_type,
        "filename": filename,
        "url": url,
        "file_size": file_size,
        "content_type": content_type,
        "gcs_path": gcs_path,
        "status": "uploading" if source_type == "upload" else "fetching",
        "included": True,
        "review": None,
        "created_by": created_by,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        **(tenant_fields(tenant) if tenant else {}),
    }
    try:
        _col().insert_one(doc)
        logger.info(
            "[Knowledge] Created doc=%s project=%s source_type=%s",
            doc_id,
            project_id,
            source_type,
        )
        doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[Knowledge] Failed to create doc project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return None


def get_knowledge_document(
    *,
    doc_id: str,
    project_id: str,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Fetch a single knowledge document by ID."""
    try:
        doc = _col().find_one(
            {"doc_id": doc_id, "project_id": project_id, **tenant_filter(tenant)}
        )
        if doc:
            doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[Knowledge] Failed to get doc=%s: %s", doc_id, exc, exc_info=True
        )
        return None


def list_knowledge_documents(
    *,
    project_id: str,
    tenant: TenantContext | None = None,
) -> list[dict]:
    """List all knowledge documents for a project."""
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
            "[Knowledge] Failed to list docs project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return []


def update_knowledge_document(
    *,
    doc_id: str,
    project_id: str,
    updates: dict,
    tenant: TenantContext | None = None,
) -> bool:
    """Update arbitrary fields on a knowledge document."""
    updates["updated_at"] = _now_iso()
    try:
        result = _col().update_one(
            {"doc_id": doc_id, "project_id": project_id, **tenant_filter(tenant)},
            {"$set": updates},
        )
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error(
            "[Knowledge] Failed to update doc=%s: %s", doc_id, exc, exc_info=True
        )
        return False


def toggle_included(
    *,
    doc_id: str,
    project_id: str,
    included: bool,
    tenant: TenantContext | None = None,
) -> bool:
    """Toggle the included flag for aggregation."""
    return update_knowledge_document(
        doc_id=doc_id,
        project_id=project_id,
        updates={"included": included},
        tenant=tenant,
    )


def delete_knowledge_document(
    *,
    doc_id: str,
    project_id: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Delete a knowledge document record."""
    try:
        result = _col().delete_one(
            {"doc_id": doc_id, "project_id": project_id, **tenant_filter(tenant)}
        )
        if result.deleted_count > 0:
            logger.info("[Knowledge] Deleted doc=%s project=%s", doc_id, project_id)
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[Knowledge] Failed to delete doc=%s: %s", doc_id, exc, exc_info=True
        )
        return False


def set_review_result(
    *,
    doc_id: str,
    project_id: str,
    review: dict,
    tenant: TenantContext | None = None,
) -> bool:
    """Store the Content Reviewer output on a document.

    Args:
        review: Dict with keys: summary, key_bullets, topics, confidence.
    """
    return update_knowledge_document(
        doc_id=doc_id,
        project_id=project_id,
        updates={"review": review, "status": "reviewed"},
        tenant=tenant,
    )


def count_knowledge_documents(
    *,
    project_id: str,
    tenant: TenantContext | None = None,
) -> int:
    """Count all knowledge documents for a project."""
    try:
        return _col().count_documents(
            {"project_id": project_id, **tenant_filter(tenant)}
        )
    except PyMongoError as exc:
        logger.error(
            "[Knowledge] Failed to count docs project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return 0


def find_duplicate_document(
    *,
    project_id: str,
    filename: str,
    file_size: int,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Check for an existing document with the same filename and file_size.

    Returns the existing document dict if found, else None.
    """
    try:
        doc = _col().find_one(
            {
                "project_id": project_id,
                "filename": filename,
                "file_size": file_size,
                **tenant_filter(tenant),
            }
        )
        if doc:
            doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[Knowledge] Duplicate check failed project=%s filename=%s: %s",
            project_id,
            filename,
            exc,
            exc_info=True,
        )
        return None


def find_duplicate_url(
    *,
    project_id: str,
    url: str,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Check for an existing document with the same URL in the project.

    Returns the existing document dict if found, else None.
    """
    try:
        doc = _col().find_one(
            {
                "project_id": project_id,
                "source_type": "url",
                "url": url,
                **tenant_filter(tenant),
            }
        )
        if doc:
            doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[Knowledge] URL duplicate check failed project=%s url=%s: %s",
            project_id,
            url,
            exc,
            exc_info=True,
        )
        return None
