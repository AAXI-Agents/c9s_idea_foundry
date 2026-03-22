"""Project-memory loader for agent backstory enrichment.

Reads project-level memory entries from the ``projectMemory`` MongoDB
collection and formats them into a structured context block that is
appended to an agent's backstory.  This ensures every agent in the
pipeline recalls the team's guardrails, knowledge references, and
technology stack without relying on a secondary vector-store.

Usage::

    from crewai_productfeature_planner.scripts.memory_loader import (
        enrich_backstory_for_project,
        resolve_project_id,
    )

    project_id = resolve_project_id(run_id)
    backstory = enrich_backstory_for_project(backstory, project_id)
    agent = Agent(backstory=backstory, ...)

Three memory categories are injected:

* **Idea-Iteration Guardrails** — behavioural constraints on how
  agents iterate and refine ideas (tone, iteration philosophy, etc.).
* **Knowledge References** — links, documents, and notes the team
  uses as domain-level guidelines.
* **Technology Stack** — concrete tools, databases, frameworks, and
  algorithms the team builds with.
"""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


# ── resolve helpers ──────────────────────────────────────────────────


def resolve_project_id(run_id: str) -> str | None:
    """Map a flow *run_id* to its ``project_id`` (if linked).

    Reads the ``project_id`` field stored on the ``workingIdeas``
    document for the given *run_id*.

    Returns:
        The ``project_id`` string, or ``None`` when the run is not
        linked to a project (or on any DB error).
    """
    if not run_id:
        return None
    try:
        from crewai_productfeature_planner.mongodb.client import get_db

        doc = get_db()["workingIdeas"].find_one(
            {"run_id": run_id},
            {"project_id": 1, "_id": 0},
        )
        pid = (doc or {}).get("project_id")
        if pid:
            logger.debug(
                "[MemoryLoader] Resolved run_id=%s → project_id=%s",
                run_id, pid,
            )
        return pid or None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[MemoryLoader] Failed to resolve project_id for "
            "run_id=%s: %s",
            run_id, exc,
        )
        return None


# ── formatting ───────────────────────────────────────────────────────


def _format_entries(entries: list[dict], *, numbered: bool = True) -> str:
    """Format a list of memory entries into a human-readable block."""
    if not entries:
        return "(none configured)"
    lines: list[str] = []
    for idx, entry in enumerate(entries, 1):
        content = entry.get("content", "").strip()
        if not content:
            continue
        kind = entry.get("kind")
        prefix = f"{idx}. " if numbered else "• "
        if kind:
            lines.append(f"{prefix}[{kind}] {content}")
        else:
            lines.append(f"{prefix}{content}")
    return "\n".join(lines) if lines else "(none configured)"


def load_project_memory_context(project_id: str) -> str:
    """Load project memory from MongoDB and format as backstory context.

    Returns an empty string when no memory exists or on error, so it
    is always safe to append to a backstory.
    """
    if not project_id:
        return ""

    try:
        from crewai_productfeature_planner.mongodb.project_memory import (
            get_project_memory,
        )

        doc = get_project_memory(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[MemoryLoader] Failed to load projectMemory for "
            "project_id=%s: %s",
            project_id, exc,
        )
        return ""

    if not doc:
        logger.debug(
            "[MemoryLoader] No projectMemory document for project_id=%s",
            project_id,
        )
        return ""

    idea_entries = doc.get("idea_iteration", [])
    knowledge_entries = doc.get("knowledge", [])
    tools_entries = doc.get("tools", [])

    # Nothing stored yet → no enrichment
    if not idea_entries and not knowledge_entries and not tools_entries:
        logger.debug(
            "[MemoryLoader] projectMemory exists but all categories "
            "empty for project_id=%s",
            project_id,
        )
        return ""

    sections: list[str] = [
        "",
        "═══════════════════════════════════════════════════",
        "PROJECT MEMORY — Team-Configured Guardrails",
        "═══════════════════════════════════════════════════",
        "",
        "The following project-level memories have been configured by",
        "the team.  Treat them as hard constraints that override general",
        "best-practice defaults wherever they conflict.",
        "",
    ]

    if idea_entries:
        sections.extend([
            "── Idea-Iteration Guardrails ──────────────────────",
            "How to iterate, refine, and evaluate ideas for this project:",
            _format_entries(idea_entries),
            "",
        ])

    if knowledge_entries:
        sections.extend([
            "── Knowledge References ────────────────────────────",
            "Links, documents, and notes that serve as domain context:",
            _format_entries(knowledge_entries),
            "",
        ])

    if tools_entries:
        sections.extend([
            "── Technology Stack ────────────────────────────────",
            "Technologies, databases, frameworks, and algorithms the",
            "team uses when implementing:",
            _format_entries(tools_entries),
            "",
        ])

    sections.append(
        "═══════════════════════════════════════════════════"
    )

    context = "\n".join(sections)
    logger.info(
        "[MemoryLoader] Loaded project memory for project_id=%s "
        "(%d idea, %d knowledge, %d tools → %d chars)",
        project_id,
        len(idea_entries),
        len(knowledge_entries),
        len(tools_entries),
        len(context),
    )
    return context


# ── public API ───────────────────────────────────────────────────────


def enrich_backstory(backstory: str, project_id: str | None) -> str:
    """Append project-memory context to an agent *backstory*.

    Safe to call with ``project_id=None`` — returns the original
    backstory unchanged.
    """
    if not project_id:
        return backstory

    context = load_project_memory_context(project_id)
    if context:
        backstory = f"{backstory}\n{context}"

    # Append completed-idea summaries so agents avoid duplication
    try:
        from crewai_productfeature_planner.scripts.project_knowledge import (
            load_completed_ideas_context,
        )
        ideas_ctx = load_completed_ideas_context(project_id)
        if ideas_ctx:
            backstory = f"{backstory}\n{ideas_ctx}"
    except Exception:  # noqa: BLE001
        logger.debug(
            "[MemoryLoader] Could not load completed ideas for "
            "project_id=%s",
            project_id,
            exc_info=True,
        )

    return backstory


def enrich_backstory_for_run(backstory: str, run_id: str) -> str:
    """Convenience wrapper: resolve *run_id* → ``project_id``, then enrich.

    If the run is not linked to a project the backstory is returned
    unchanged.
    """
    pid = resolve_project_id(run_id)
    return enrich_backstory(backstory, pid)
