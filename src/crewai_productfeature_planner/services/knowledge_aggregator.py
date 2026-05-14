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
from crewai_productfeature_planner.apis.knowledge._ws_knowledge import (
    broadcast_knowledge_sync,
)
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.knowledge_documents import (
    count_knowledge_documents,
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

    # Strip markdown fencing (```json ... ``` or ``` ... ```)
    if "```" in text:
        # Find the content between the first ``` and last ```
        lines = text.split("\n")
        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("```") and start_idx is None:
                start_idx = i
            elif line.strip() == "```" and start_idx is not None:
                end_idx = i
        if start_idx is not None:
            inner_lines = lines[start_idx + 1 : end_idx if end_idx else len(lines)]
            text = "\n".join(inner_lines).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find a JSON object in the response (LLM may add preamble/postamble)
    brace_start = text.find("{")
    if brace_start != -1:
        # Find matching closing brace by scanning from the end
        brace_end = text.rfind("}")
        if brace_end > brace_start:
            candidate = text[brace_start : brace_end + 1]
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                pass

    logger.warning("[KnowledgeAggregator] Failed to parse JSON output: %.200s", text)
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
            doc = get_knowledge_document(doc_id=doc_id, project_id=project_id, tenant=tenant)
            if doc:
                broadcast_knowledge_sync(project_id, {
                    "event": "knowledge.doc.updated",
                    "data": doc,
                })
            return None

        set_review_result(
            doc_id=doc_id, project_id=project_id, review=parsed, tenant=tenant
        )
        logger.info("[KnowledgeAggregator] Review complete doc=%s", doc_id)

        # Broadcast doc update via WebSocket
        doc = get_knowledge_document(doc_id=doc_id, project_id=project_id, tenant=tenant)
        if doc:
            broadcast_knowledge_sync(project_id, {
                "event": "knowledge.doc.updated",
                "data": doc,
            })

        # Auto-trigger aggregation after successful review
        aggregate_knowledge_async(project_id=project_id, tenant=tenant)

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
        # Broadcast failure via WebSocket
        doc = get_knowledge_document(doc_id=doc_id, project_id=project_id, tenant=tenant)
        if doc:
            broadcast_knowledge_sync(project_id, {
                "event": "knowledge.doc.updated",
                "data": doc,
            })
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
        total_count = count_knowledge_documents(project_id=project_id, tenant=tenant)
        return upsert_knowledge_summary(
            project_id=project_id,
            unified_summary="No knowledge documents available.",
            unified_bullets=[],
            contradictions=[],
            doc_count=total_count,
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

        # Broadcast summary update via WebSocket
        if summary_doc:
            broadcast_knowledge_sync(project_id, {
                "event": "knowledge.summary.updated",
                "data": summary_doc,
            })

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
