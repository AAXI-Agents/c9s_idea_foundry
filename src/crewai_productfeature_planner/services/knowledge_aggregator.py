"""Knowledge aggregator service.

Orchestrates the Content Reviewer agent to:
1. Review individual documents (single doc → summary + bullets + topics + confidence).
2. Aggregate all included documents into a unified summary with contradiction detection.
"""

from __future__ import annotations

import json
import threading

from crewai import Crew, Task

from crewai_productfeature_planner.agents.content_reviewer import (
    create_content_reviewer,
    get_task_configs,
)
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.knowledge_documents import (
    get_knowledge_document,
    list_knowledge_documents,
    set_review_result,
    update_knowledge_document,
)
from crewai_productfeature_planner.mongodb.knowledge_summaries import (
    upsert_knowledge_summary,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _parse_json_output(raw: str) -> dict | None:
    """Attempt to parse JSON from agent output, stripping markdown fencing."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("[KnowledgeAggregator] Failed to parse JSON output: %s", exc)
        return None


def review_document(
    *,
    doc_id: str,
    project_id: str,
    content: str,
    title: str,
    source: str,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Run the Content Reviewer on a single document.

    Args:
        doc_id: Document ID.
        project_id: Project ID.
        content: Full text content of the document.
        title: Document title/filename.
        source: Source descriptor (filename or URL).
        tenant: Tenant context.

    Returns:
        Review dict (summary, key_bullets, topics, confidence) or None on failure.
    """
    logger.info(
        "[KnowledgeAggregator] Reviewing doc=%s project=%s", doc_id, project_id
    )

    # Update status to reviewing
    update_knowledge_document(
        doc_id=doc_id, project_id=project_id, updates={"status": "reviewing"}, tenant=tenant
    )

    try:
        agent = create_content_reviewer()
        task_configs = get_task_configs()
        review_config = task_configs["review_document_task"]

        task = Task(
            description=review_config["description"].format(
                title=title, source=source, content=content[:50000]
            ),
            expected_output=review_config["expected_output"],
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        result = crew.kickoff()

        parsed = _parse_json_output(str(result))
        if not parsed:
            update_knowledge_document(
                doc_id=doc_id,
                project_id=project_id,
                updates={"status": "review_failed"},
                tenant=tenant,
            )
            return None

        set_review_result(
            doc_id=doc_id, project_id=project_id, review=parsed, tenant=tenant
        )
        logger.info("[KnowledgeAggregator] Review complete doc=%s", doc_id)
        return parsed

    except Exception as exc:
        logger.error(
            "[KnowledgeAggregator] Review failed doc=%s: %s",
            doc_id,
            exc,
            exc_info=True,
        )
        update_knowledge_document(
            doc_id=doc_id,
            project_id=project_id,
            updates={"status": "review_failed"},
            tenant=tenant,
        )
        return None


def review_document_async(
    *,
    doc_id: str,
    project_id: str,
    content: str,
    title: str,
    source: str,
    tenant: TenantContext | None = None,
) -> None:
    """Fire-and-forget review in a background thread."""
    thread = threading.Thread(
        target=review_document,
        kwargs={
            "doc_id": doc_id,
            "project_id": project_id,
            "content": content,
            "title": title,
            "source": source,
            "tenant": tenant,
        },
        name=f"review-{doc_id}",
        daemon=True,
    )
    thread.start()


def aggregate_knowledge(
    *,
    project_id: str,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Aggregate all included, reviewed documents into a unified summary.

    Returns the aggregated summary dict or None on failure.
    """
    logger.info("[KnowledgeAggregator] Aggregating project=%s", project_id)

    docs = list_knowledge_documents(project_id=project_id, tenant=tenant)
    included_docs = [
        d for d in docs if d.get("included") and d.get("review")
    ]

    if not included_docs:
        logger.info("[KnowledgeAggregator] No included reviewed docs for project=%s", project_id)
        return upsert_knowledge_summary(
            project_id=project_id,
            unified_summary="No knowledge documents available.",
            unified_bullets=[],
            contradictions=[],
            doc_count=0,
            tenant=tenant,
        )

    # Build reviews payload for the aggregation task
    reviews_payload = []
    for doc in included_docs:
        review = doc["review"]
        reviews_payload.append({
            "title": doc.get("filename") or doc.get("url") or doc["doc_id"],
            "summary": review.get("summary", ""),
            "key_bullets": review.get("key_bullets", []),
            "topics": review.get("topics", []),
            "confidence": review.get("confidence", 0.5),
        })

    try:
        agent = create_content_reviewer()
        task_configs = get_task_configs()
        agg_config = task_configs["aggregate_knowledge_task"]

        task = Task(
            description=agg_config["description"].format(
                reviews_json=json.dumps(reviews_payload, indent=2)
            ),
            expected_output=agg_config["expected_output"],
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        result = crew.kickoff()

        parsed = _parse_json_output(str(result))
        if not parsed:
            logger.warning("[KnowledgeAggregator] Aggregation parse failed project=%s", project_id)
            return None

        summary_doc = upsert_knowledge_summary(
            project_id=project_id,
            unified_summary=parsed.get("unified_summary", ""),
            unified_bullets=parsed.get("unified_bullets", []),
            contradictions=parsed.get("contradictions", []),
            doc_count=len(included_docs),
            tenant=tenant,
        )
        logger.info(
            "[KnowledgeAggregator] Aggregation complete project=%s docs=%d",
            project_id,
            len(included_docs),
        )
        return summary_doc

    except Exception as exc:
        logger.error(
            "[KnowledgeAggregator] Aggregation failed project=%s: %s",
            project_id,
            exc,
            exc_info=True,
        )
        return None


def aggregate_knowledge_async(
    *,
    project_id: str,
    tenant: TenantContext | None = None,
) -> None:
    """Fire-and-forget aggregation in a background thread."""
    thread = threading.Thread(
        target=aggregate_knowledge,
        kwargs={"project_id": project_id, "tenant": tenant},
        name=f"aggregate-{project_id}",
        daemon=True,
    )
    thread.start()
