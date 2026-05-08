"""Knowledge documents MongoDB repository.

Stores metadata for uploaded files and fetched URLs attached to projects.
Actual file content lives in GCS; this collection stores status, summaries,
and inclusion flags used by the aggregator.
"""

from crewai_productfeature_planner.mongodb.knowledge_documents.repository import (
    KNOWLEDGE_DOCUMENTS_COLLECTION,
    create_knowledge_document,
    count_knowledge_documents,
    find_duplicate_document,
    find_duplicate_url,
    get_knowledge_document,
    list_knowledge_documents,
    update_knowledge_document,
    toggle_included,
    delete_knowledge_document,
    set_review_result,
)

__all__ = [
    "KNOWLEDGE_DOCUMENTS_COLLECTION",
    "create_knowledge_document",
    "count_knowledge_documents",
    "find_duplicate_document",
    "find_duplicate_url",
    "get_knowledge_document",
    "list_knowledge_documents",
    "update_knowledge_document",
    "toggle_included",
    "delete_knowledge_document",
    "set_review_result",
]
