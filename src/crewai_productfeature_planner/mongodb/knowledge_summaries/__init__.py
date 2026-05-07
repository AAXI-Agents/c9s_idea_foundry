"""Knowledge summaries MongoDB repository.

Stores aggregated summaries across all included knowledge documents
for a project, including unified bullets and contradiction analysis.
"""

from crewai_productfeature_planner.mongodb.knowledge_summaries.repository import (
    KNOWLEDGE_SUMMARIES_COLLECTION,
    get_knowledge_summary,
    upsert_knowledge_summary,
    delete_knowledge_summary,
)

__all__ = [
    "KNOWLEDGE_SUMMARIES_COLLECTION",
    "get_knowledge_summary",
    "upsert_knowledge_summary",
    "delete_knowledge_summary",
]
