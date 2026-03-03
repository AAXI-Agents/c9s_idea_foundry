"""Query and lookup operations on the ``workingIdeas`` collection.

Read-only (or bulk-status-change) functions that find, filter, or
aggregate working-idea documents.
"""

from __future__ import annotations

from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.working_ideas import _common
from crewai_productfeature_planner.mongodb.working_ideas._common import (
    WORKING_COLLECTION,
    _now_iso,
    logger,
)


def find_completed_without_confluence() -> list[dict[str, Any]]:
    """Find completed working ideas that have not been published to Confluence.

    Queries ``workingIdeas`` for documents whose ``status`` is
    ``"completed"`` and whose ``confluence_url`` field is either
    missing, null, or empty.

    Returns:
        A list of full document dicts, or an empty list on failure.
    """
    try:
        db = _common.get_db()
        query = {
            "status": "completed",
            "$or": [
                {"confluence_url": {"$exists": False}},
                {"confluence_url": None},
                {"confluence_url": ""},
            ],
        }
        docs = list(db[WORKING_COLLECTION].find(query).sort("created_at", -1))
        logger.info(
            "[MongoDB] Found %d completed idea(s) without Confluence publish",
            len(docs),
        )
        return docs
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to query completed ideas without Confluence: %s",
            exc,
        )
        return []


def find_completed_without_output() -> list[dict[str, Any]]:
    """Find completed working ideas that have no associated output file.

    Queries ``workingIdeas`` for documents whose ``status`` is
    ``"completed"`` and whose ``output_file`` field is either missing
    or ``null``.

    Returns:
        A list of full document dicts, or an empty list on failure.
    """
    try:
        db = _common.get_db()
        query = {
            "status": "completed",
            "$or": [
                {"output_file": {"$exists": False}},
                {"output_file": None},
                {"output_file": ""},
            ],
        }
        docs = list(db[WORKING_COLLECTION].find(query).sort("created_at", -1))
        logger.info(
            "[MongoDB] Found %d completed idea(s) without output file",
            len(docs),
        )
        return docs
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to query completed ideas without output: %s",
            exc,
        )
        return []


def fail_unfinalized_on_startup() -> list[dict[str, Any]]:
    """Mark all unfinalized working ideas as ``failed`` on server restart.

    Similar to ``fail_incomplete_jobs_on_startup`` in crew_jobs, this
    ensures that old PRD runs are not resumed after a server restart.
    Users can manually restart their PRD flows to pick up new code.

    Returns:
        A list of dicts ``{"run_id": ..., "idea": ..., "prev_status": ...,
        "slack_channel": ..., "slack_thread_ts": ...}`` for each idea
        that was marked as failed.  Empty list when nothing was recovered
        or on error.
    """
    now = _now_iso()
    recovered: list[dict[str, Any]] = []
    try:
        db = _common.get_db()
        query = {"status": {"$nin": ["completed", "archived", "failed"]}}
        docs = list(db[WORKING_COLLECTION].find(query))
        for doc in docs:
            run_id = doc.get("run_id", "unknown")
            prev_status = doc.get("status", "unknown")
            db[WORKING_COLLECTION].update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "status": "failed",
                    "error": (
                        f"Run was in '{prev_status}' status when the server "
                        f"restarted. Terminated to apply new code changes. "
                        f"Say 'create prd' to start a fresh run."
                    ),
                    "update_date": now,
                }},
            )
            logger.warning(
                "[MongoDB] Startup recovery: working idea %s (%s -> failed) — "
                "server restart",
                run_id, prev_status,
            )
            recovered.append({
                "run_id": run_id,
                "idea": doc.get("idea", ""),
                "prev_status": prev_status,
                "slack_channel": doc.get("slack_channel"),
                "slack_thread_ts": doc.get("slack_thread_ts"),
            })

        if recovered:
            logger.info(
                "[MongoDB] Startup recovery: %d unfinalized idea(s) marked failed",
                len(recovered),
            )
        else:
            logger.info("[MongoDB] Startup recovery — no unfinalized ideas found")
        return recovered
    except PyMongoError as exc:
        logger.error("[MongoDB] Startup recovery (unfinalized ideas) failed: %s", exc)
        return []


def find_unfinalized() -> list[dict[str, Any]]:
    """Find working ideas that have not been finalized.

    Queries ``workingIdeas`` for documents whose status is not
    ``completed``.  Failed runs are included so they can be
    resumed — the underlying executive summary and requirements
    data is still valid.

    Returns:
        A list of dicts, each containing:
        ``run_id``, ``idea``, ``iteration``, ``created_at``,
        ``sections`` (list of section keys that have drafts),
        and ``exec_summary_iterations`` (number of executive
        summary iteration records).
        Returns an empty list on failure.
    """
    try:
        db = _common.get_db()

        query = {
            "status": {"$nin": ["completed", "archived"]},
        }
        docs = list(db[WORKING_COLLECTION].find(query).sort("created_at", -1))
        runs = []
        for doc in docs:
            section_obj = doc.get("section") or {}
            sections = [k for k, v in section_obj.items() if isinstance(v, list) and v]
            # Determine latest iteration across all sections
            max_iter = 0
            for entries in section_obj.values():
                if isinstance(entries, list):
                    for entry in entries:
                        it = entry.get("iteration", 0) if isinstance(entry, dict) else 0
                        if it > max_iter:
                            max_iter = it
            # Count executive summary iterations (top-level array)
            raw_exec = doc.get("executive_summary", [])
            exec_iter_count = len(raw_exec) if isinstance(raw_exec, list) else 0
            # Count requirements_breakdown iterations (top-level array)
            raw_reqs = doc.get("requirements_breakdown", [])
            req_iter_count = len(raw_reqs) if isinstance(raw_reqs, list) else 0
            # Use whichever is higher for the overall iteration display
            effective_iter = max(max_iter, exec_iter_count)
            # Prefer the original idea; fall back to finalized_idea
            idea_text = doc.get("idea") or doc.get("finalized_idea") or ""
            runs.append({
                "run_id": doc.get("run_id", ""),
                "idea": idea_text,
                "status": doc.get("status", "unknown"),
                "iteration": effective_iter,
                "created_at": doc.get("created_at"),
                "sections": sections,
                "sections_done": len(sections),
                "total_sections": 10,
                "exec_summary_iterations": exec_iter_count,
                "req_breakdown_iterations": req_iter_count,
                "section_missing": "section" not in doc,
                "project_id": doc.get("project_id"),
                "slack_channel": doc.get("slack_channel"),
                "slack_thread_ts": doc.get("slack_thread_ts"),
            })
        logger.info("[MongoDB] Found %d unfinalized working idea(s)", len(runs))
        return runs
    except PyMongoError as exc:
        logger.error("[MongoDB] Failed to query unfinalized ideas: %s", exc)
        return []


def _backfill_orphaned_ideas(
    project_id: str,
    channel: str | None,
) -> list:
    """Find working ideas missing ``project_id`` that belong to *channel*.

    Looks for non-archived working-idea documents whose ``project_id``
    is absent or null.  For each, checks whether a corresponding crew
    job exists with the given *channel*.  Matching documents get their
    ``project_id`` back-filled in MongoDB so future queries find them
    normally.

    Returns:
        The list of matching raw MongoDB documents (already updated).
    """
    if not channel:
        return []
    try:
        db = _common.get_db()
        orphans = list(
            db[WORKING_COLLECTION].find({
                "status": {"$ne": "archived"},
                "$or": [
                    {"project_id": {"$exists": False}},
                    {"project_id": None},
                    {"project_id": ""},
                ],
            })
        )
        if not orphans:
            return []

        # Import crew jobs lazily to avoid circular imports
        from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
            find_job,
        )

        matched: list = []
        for doc in orphans:
            run_id = doc.get("run_id", "")
            if not run_id:
                continue
            # Check if the crew job lives in the same channel
            job = find_job(run_id)
            if not job:
                continue
            job_channel = job.get("slack_channel") or ""
            if job_channel != channel:
                continue
            # Backfill project_id
            try:
                db[WORKING_COLLECTION].update_one(
                    {"run_id": run_id},
                    {"$set": {
                        "project_id": project_id,
                        "update_date": _now_iso(),
                    }},
                )
                doc["project_id"] = project_id
                logger.info(
                    "[MongoDB] Backfilled project_id=%s on orphaned "
                    "working idea run_id=%s (channel=%s)",
                    project_id, run_id, channel,
                )
            except PyMongoError:
                logger.debug(
                    "Backfill project_id failed for run_id=%s",
                    run_id, exc_info=True,
                )
            matched.append(doc)
        return matched
    except PyMongoError as exc:
        logger.debug("_backfill_orphaned_ideas failed: %s", exc)
        return []


def _doc_to_idea_dict(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw working-idea document to the dict format
    returned by :func:`find_ideas_by_project`."""
    section_obj = doc.get("section") or {}
    sections = [k for k, v in section_obj.items() if isinstance(v, list) and v]
    max_iter = 0
    for entries in section_obj.values():
        if isinstance(entries, list):
            for entry in entries:
                it = entry.get("iteration", 0) if isinstance(entry, dict) else 0
                if it > max_iter:
                    max_iter = it
    raw_exec = doc.get("executive_summary", [])
    exec_iter_count = len(raw_exec) if isinstance(raw_exec, list) else 0
    effective_iter = max(max_iter, exec_iter_count)
    idea_text = (
        doc.get("idea")
        or doc.get("finalized_idea")
        or ""
    )
    return {
        "run_id": doc.get("run_id", ""),
        "idea": idea_text,
        "status": doc.get("status", "unknown"),
        "iteration": effective_iter,
        "created_at": doc.get("created_at"),
        "sections_done": len(sections),
        "total_sections": 10,
    }


def find_ideas_by_project(
    project_id: str,
    *,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Find all working ideas associated with a project.

    Returns ideas in any status (in-progress, paused, completed, failed)
    except ``archived``.  Results are sorted newest-first.

    If *channel* is provided, also checks for orphaned working ideas
    (those missing ``project_id``) whose crew job lives in the same
    channel.  Any matches are back-filled with *project_id* so future
    queries find them without the channel hint.

    Returns:
        A list of dicts, each containing: ``run_id``, ``idea``,
        ``status``, ``iteration``, ``created_at``, ``sections_done``,
        ``total_sections``.  Returns an empty list on failure.
    """
    try:
        db = _common.get_db()
        query: dict[str, Any] = {
            "project_id": project_id,
            "status": {"$ne": "archived"},
        }
        docs = list(db[WORKING_COLLECTION].find(query).sort("created_at", -1))
        known_run_ids = {doc.get("run_id") for doc in docs}

        # Attempt to rescue orphaned ideas that lack project_id
        if channel:
            orphan_docs = _backfill_orphaned_ideas(project_id, channel)
            for od in orphan_docs:
                if od.get("run_id") not in known_run_ids:
                    docs.append(od)
                    known_run_ids.add(od.get("run_id"))

        ideas = [_doc_to_idea_dict(doc) for doc in docs]
        # Re-sort by created_at descending (orphans may be interleaved)
        ideas.sort(
            key=lambda x: x.get("created_at") or "",
            reverse=True,
        )
        logger.info(
            "[MongoDB] Found %d idea(s) for project_id=%s",
            len(ideas), project_id,
        )
        return ideas
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to query ideas for project_id=%s: %s",
            project_id, exc,
        )
        return []


def find_run_any_status(run_id: str) -> dict[str, Any] | None:
    """Fetch a working-idea document by *run_id* regardless of status.

    Unlike :func:`get_run_documents` this does **not** exclude
    ``completed`` documents.  Only ``archived`` runs are filtered out.

    Returns:
        The document dict, or ``None`` if not found.
    """
    try:
        db = _common.get_db()
        doc = db[WORKING_COLLECTION].find_one(
            {"run_id": run_id, "status": {"$ne": "archived"}}
        )
        if doc is None:
            logger.info("[MongoDB] No document (any status) for run_id=%s", run_id)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to fetch document (any status) for run_id=%s: %s",
            run_id, exc,
        )
        return None


def get_run_documents(run_id: str) -> list[dict[str, Any]]:
    """Fetch the working-idea document for a given run_id.

    In the single-document model there is at most one document per
    run_id.  The result is returned as a one-element list for
    backward-compatibility with callers that expect a list.

    Returns:
        A list containing the document, or an empty list on failure /
        not found.
    """
    try:
        db = _common.get_db()
        doc = db[WORKING_COLLECTION].find_one(
            {"run_id": run_id, "status": {"$ne": "completed"}}
        )
        if doc is None:
            logger.info("[MongoDB] No document found for run_id=%s", run_id)
            return []
        logger.info("[MongoDB] Fetched document for run_id=%s", run_id)
        return [doc]
    except PyMongoError as exc:
        logger.error("[MongoDB] Failed to fetch document for run_id=%s: %s", run_id, exc)
        return []
