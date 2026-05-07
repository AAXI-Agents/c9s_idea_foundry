"""Repository functions for the knowledge_summaries collection."""

from __future__ import annotations

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

KNOWLEDGE_SUMMARIES_COLLECTION = "knowledgeSummaries"


def _col():
    return get_db()[KNOWLEDGE_SUMMARIES_COLLECTION]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_knowledge_summary(
    *,
    project_id: str,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Get the aggregated knowledge summary for a project."""
    try:
        doc = _col().find_one(
            {"project_id": project_id, **tenant_filter(tenant)}
        )
        if doc:
            doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[KnowledgeSummary] Failed to get summary project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return None


def upsert_knowledge_summary(
    *,
    project_id: str,
    unified_summary: str,
    unified_bullets: list[str],
    contradictions: list[dict],
    doc_count: int,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Create or replace the aggregated summary for a project.

    Args:
        project_id: Owning project.
        unified_summary: LLM-generated unified summary text.
        unified_bullets: Key bullet points across all docs.
        contradictions: List of contradiction dicts with keys:
            claim_a, source_a, claim_b, source_b, severity.
        doc_count: Number of included docs used in aggregation.
        tenant: Tenant context.

    Returns:
        The upserted document dict, or None on failure.
    """
    now = _now_iso()
    doc = {
        "project_id": project_id,
        "unified_summary": unified_summary,
        "unified_bullets": unified_bullets,
        "contradictions": contradictions,
        "doc_count": doc_count,
        "generated_at": now,
        "updated_at": now,
        **(tenant_fields(tenant) if tenant else {}),
    }
    try:
        _col().replace_one(
            {"project_id": project_id, **tenant_filter(tenant)},
            doc,
            upsert=True,
        )
        logger.info(
            "[KnowledgeSummary] Upserted summary project=%s doc_count=%d contradictions=%d",
            project_id,
            doc_count,
            len(contradictions),
        )
        doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[KnowledgeSummary] Failed to upsert summary project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return None


def delete_knowledge_summary(
    *,
    project_id: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Delete the aggregated summary for a project."""
    try:
        result = _col().delete_one(
            {"project_id": project_id, **tenant_filter(tenant)}
        )
        return result.deleted_count > 0
    except PyMongoError as exc:
        logger.error(
            "[KnowledgeSummary] Failed to delete project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return False
