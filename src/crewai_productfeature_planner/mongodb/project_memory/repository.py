"""Repository for the ``projectMemory`` collection.

Stores project-level memory entries organised into three categories
that seed CrewAI agent memory before each run.

Categories
----------
* **idea_iteration** — behavioural guardrails for how an agent should
  act when iterating through an idea (role definitions, tone,
  iteration limits, approval criteria, etc.).
* **knowledge** — links, document references, or uploaded files that
  serve as guidelines for the project's domain context.
* **tools** — the concrete technologies, databases, algorithms,
  frameworks, and services the team uses when implementing.

Each project has one ``projectMemory`` document keyed by
``project_id``.  The three categories are stored as arrays so users
can incrementally add, remove, or replace entries.

Document schema::

    {
        "project_id":       str,            # FK → projectConfig
        "idea_iteration":   [               # ← MemoryCategory.IDEA_ITERATION
            {
                "content":    str,           # e.g. "Be concise, focus on MVP"
                "added_by":   str,           # Slack user_id or "system"
                "added_at":   str,           # ISO-8601
            }
        ],
        "knowledge":        [               # ← MemoryCategory.KNOWLEDGE
            {
                "content":    str,           # link, title, or note
                "kind":       str,           # "link" | "document" | "note"
                "added_by":   str,
                "added_at":   str,
            }
        ],
        "tools":            [               # ← MemoryCategory.TOOLS
            {
                "content":    str,           # e.g. "mongodb atlas for persistence"
                "added_by":   str,
                "added_at":   str,
            }
        ],
        "created_at":       str,            # ISO-8601
        "updated_at":       str,            # ISO-8601
    }

Functions follow the same CRUD conventions used by ``project_config``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import TenantContext, tenant_fields
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_MEMORY_COLLECTION = "projectMemory"


class MemoryCategory(str, Enum):
    """The three memory-category keys stored per project."""

    IDEA_ITERATION = "idea_iteration"
    KNOWLEDGE = "knowledge"
    TOOLS = "tools"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── helpers ──────────────────────────────────────────────────────────


def _collection():
    """Return the ``projectMemory`` Mongo collection handle."""
    return get_db()[PROJECT_MEMORY_COLLECTION]


def _empty_doc(project_id: str) -> dict[str, Any]:
    """Scaffold an empty project-memory document."""
    now = _now_iso()
    return {
        "project_id": project_id,
        "idea_iteration": [],
        "knowledge": [],
        "tools": [],
        "created_at": now,
        "updated_at": now,
    }


# ── Create / Upsert ─────────────────────────────────────────────────


def upsert_project_memory(
    project_id: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Ensure a ``projectMemory`` document exists for *project_id*.

    Creates an empty-scaffold document if one does not already exist.

    Returns:
        ``True`` if a document now exists (created or already present).
    """
    try:
        insert_doc = _empty_doc(project_id)
        if tenant:
            insert_doc.update(tenant_fields(tenant))
        result = _collection().update_one(
            {"project_id": project_id},
            {"$setOnInsert": insert_doc},
            upsert=True,
        )
        if result.upserted_id:
            logger.info(
                "[MongoDB] Created projectMemory scaffold for project_id=%s",
                project_id,
            )
        return True
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed upsert for projectMemory project_id=%s: %s",
            project_id, exc,
        )
        return False


# ── Read ─────────────────────────────────────────────────────────────


def get_project_memory(project_id: str) -> dict[str, Any] | None:
    """Fetch the full project-memory document.

    Returns:
        The document (without ``_id``) or ``None``.
    """
    try:
        return _collection().find_one(
            {"project_id": project_id}, {"_id": 0},
        )
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to fetch projectMemory project_id=%s: %s",
            project_id, exc,
        )
        return None


def list_memory_entries(
    project_id: str,
    category: MemoryCategory,
) -> list[dict[str, Any]]:
    """Return all entries in a specific category.

    Returns:
        A list of entry dicts, or ``[]`` on error / missing doc.
    """
    doc = get_project_memory(project_id)
    if not doc:
        return []
    return doc.get(category.value, [])


def get_memories_for_agent(
    project_id: str,
    agent_role: str,
) -> dict[str, list[dict[str, Any]]]:
    """Load project memories relevant to an agent.

    Returns a dict with keys ``idea_iteration``, ``knowledge``, and
    ``tools``, each containing the entry list for that category.

    *agent_role* is stored for logging and potential future per-role
    filtering.

    Returns:
        ``{category: [entries]}`` — empty lists when nothing stored.
    """
    doc = get_project_memory(project_id)
    if not doc:
        logger.debug(
            "[ProjectMemory] No memory found for project_id=%s agent=%s",
            project_id, agent_role,
        )
        return {c.value: [] for c in MemoryCategory}

    logger.info(
        "[ProjectMemory] Loaded memory for project_id=%s agent=%s "
        "(idea_iteration=%d, knowledge=%d, tools=%d)",
        project_id,
        agent_role,
        len(doc.get("idea_iteration", [])),
        len(doc.get("knowledge", [])),
        len(doc.get("tools", [])),
    )
    return {
        c.value: doc.get(c.value, []) for c in MemoryCategory
    }


# ── Add entries ──────────────────────────────────────────────────────


def add_memory_entry(
    project_id: str,
    category: MemoryCategory,
    content: str,
    *,
    added_by: str = "system",
    kind: str | None = None,
) -> bool:
    """Append a single entry to a memory category array.

    Args:
        project_id: The project this memory belongs to.
        category: Which category array to append to.
        content: The memory text (instruction, link, tool name, etc.).
        added_by: Slack ``user_id`` or ``"system"``.
        kind: Only for ``knowledge`` entries — ``"link"`` / ``"document"``
            / ``"note"``.  Ignored for other categories.

    Returns:
        ``True`` on success.
    """
    entry: dict[str, Any] = {
        "content": content,
        "added_by": added_by,
        "added_at": _now_iso(),
    }
    if category == MemoryCategory.KNOWLEDGE and kind:
        entry["kind"] = kind

    try:
        # Ensure the document exists first
        upsert_project_memory(project_id)

        result = _collection().update_one(
            {"project_id": project_id},
            {
                "$push": {category.value: entry},
                "$set": {"updated_at": _now_iso()},
            },
        )
        logger.info(
            "[MongoDB] Added %s entry to project_id=%s: %s",
            category.value, project_id, content[:80],
        )
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to add %s entry project_id=%s: %s",
            category.value, project_id, exc,
        )
        return False


# ── Replace / Clear ──────────────────────────────────────────────────


def replace_category_entries(
    project_id: str,
    category: MemoryCategory,
    entries: list[dict[str, Any]],
) -> bool:
    """Replace all entries in a category with the given list.

    Useful for bulk-set from a Slack multi-line reply.

    Returns:
        ``True`` on success.
    """
    try:
        upsert_project_memory(project_id)
        result = _collection().update_one(
            {"project_id": project_id},
            {"$set": {
                category.value: entries,
                "updated_at": _now_iso(),
            }},
        )
        logger.info(
            "[MongoDB] Replaced %s entries for project_id=%s (%d items)",
            category.value, project_id, len(entries),
        )
        return result.modified_count > 0 or result.matched_count > 0
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to replace %s entries project_id=%s: %s",
            category.value, project_id, exc,
        )
        return False


def clear_category(
    project_id: str,
    category: MemoryCategory,
) -> bool:
    """Remove all entries from a category (set to ``[]``).

    Returns:
        ``True`` on success.
    """
    return replace_category_entries(project_id, category, [])


# ── Delete ───────────────────────────────────────────────────────────


def delete_memory_entry(
    project_id: str,
    category: MemoryCategory,
    content: str,
) -> bool:
    """Remove the first entry matching *content* from a category.

    Returns:
        ``True`` if an entry was removed.
    """
    try:
        result = _collection().update_one(
            {"project_id": project_id},
            {
                "$pull": {category.value: {"content": content}},
                "$set": {"updated_at": _now_iso()},
            },
        )
        if result.modified_count:
            logger.info(
                "[MongoDB] Removed %s entry from project_id=%s: %s",
                category.value, project_id, content[:80],
            )
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to remove %s entry project_id=%s: %s",
            category.value, project_id, exc,
        )
        return False
