"""Repository for the ``workingIdeas`` collection.

Stores PRD drafts using a single-document-per-run model.  Each run_id
maps to one document whose ``section`` object contains section keys with
arrays of iteration records (content, iteration, critique, updated_date).
"""

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.mongodb.client import get_db

logger = get_logger(__name__)

WORKING_COLLECTION = "workingIdeas"


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def mark_completed(run_id: str) -> int:
    """Mark the working-idea document for *run_id* as ``completed``.

    Sets ``status`` to ``"completed"`` so that ``find_unfinalized``
    excludes the run.

    Returns:
        The number of documents updated (0 or 1), or ``0`` on failure.
    """
    try:
        now = datetime.now(timezone.utc)
        result = get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": {
                "status": "completed",
                "completed_at": now.isoformat(),
                "update_date": now.isoformat(),
            }},
        )
        logger.info(
            "[MongoDB] Marked working-idea doc completed for run_id=%s (matched=%d)",
            run_id, result.modified_count,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to mark working idea completed for run_id=%s: %s",
            run_id, exc,
        )
        return 0


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
        db = get_db()

        query = {
            "status": {"$nin": ["completed"]},
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
            runs.append({
                "run_id": doc.get("run_id", ""),
                "idea": doc.get("idea", ""),
                "iteration": effective_iter,
                "created_at": doc.get("created_at"),
                "sections": sections,
                "exec_summary_iterations": exec_iter_count,
                "req_breakdown_iterations": req_iter_count,
            })
        logger.info("[MongoDB] Found %d unfinalized working idea(s)", len(runs))
        return runs
    except PyMongoError as exc:
        logger.error("[MongoDB] Failed to query unfinalized ideas: %s", exc)
        return []


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
        db = get_db()
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


def save_iteration(
    run_id: str,
    idea: str,
    iteration: int,
    draft: dict[str, str],
    critique: str = "",
    step: str = "",
    **extra: Any,
) -> str | None:
    """Persist a section iteration to the single ``workingIdeas`` document.

    Uses an upsert to create the document on first call, then appends
    iteration records into the appropriate ``section.<section_key>`` array
    on subsequent calls.

    Args:
        draft: A dict mapping section keys to their content,
            e.g. ``{"executive_summary": "# Summary ..."}``.  Each
            call typically contains a single key for the section
            that was just drafted/refined.
        iteration: Per-section iteration number (1-based).
        step: Descriptive step label (e.g. ``"draft_executive_summary"``).
            Kept for logging only.
        **extra: Accepts ``section_key`` and any other metadata.

    Returns:
        The upserted/updated document ``run_id`` as a string, or
        ``None`` on failure.

    Note:
        MongoDB errors are caught and logged so the agent flow is never
        interrupted by a database issue.
    """
    now = _now_iso()

    # Determine the section_key from the draft dict or from the step label
    section_key = extra.get("section_key", "")
    if not section_key and draft:
        section_key = next(iter(draft))

    # Build the iteration record to push into the section array
    iteration_record = {
        "content": draft.get(section_key, "") if section_key else "",
        "iteration": iteration,
        "critique": critique,
        "updated_date": now,
    }

    try:
        db = get_db()
        update_ops: dict[str, Any] = {
            "$set": {
                "idea": idea,
                "status": "inprogress",
                "update_date": now,
            },
            "$setOnInsert": {
                "run_id": run_id,
                "created_at": now,
                "completed_at": None,
            },
        }

        if section_key:
            update_ops["$push"] = {f"section.{section_key}": iteration_record}

        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            update_ops,
            upsert=True,
        )
        doc_id = str(result.upserted_id) if result.upserted_id else run_id
        logger.info(
            "[MongoDB] Saved iteration %d (step=%s, section=%s) for run_id=%s",
            iteration,
            step or "section",
            section_key,
            run_id,
        )
        return doc_id
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save iteration %d for run_id=%s: %s",
            iteration,
            run_id,
            exc,
        )
        return None


def update_section_critique(
    run_id: str,
    section_key: str,
    iteration: int,
    critique: str,
) -> bool:
    """Update the critique field on an existing iteration record.

    Finds the iteration record in ``section.<section_key>`` whose
    ``iteration`` value matches and sets its ``critique`` and
    ``updated_date`` fields.  This avoids creating a duplicate
    array element for the critique step.

    Args:
        run_id: The run identifier.
        section_key: The section whose iteration record to update.
        iteration: The per-section iteration number to match.
        critique: The critique text to set.

    Returns:
        ``True`` if the record was updated, ``False`` otherwise.
    """
    now = _now_iso()
    try:
        db = get_db()
        result = db[WORKING_COLLECTION].update_one(
            {
                "run_id": run_id,
                f"section.{section_key}.iteration": iteration,
            },
            {
                "$set": {
                    f"section.{section_key}.$.critique": critique,
                    f"section.{section_key}.$.updated_date": now,
                    "update_date": now,
                },
            },
        )
        updated = result.modified_count > 0
        logger.info(
            "[MongoDB] Updated critique on section=%s iteration=%d "
            "for run_id=%s (matched=%d)",
            section_key, iteration, run_id, result.modified_count,
        )
        return updated
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to update critique for section=%s "
            "run_id=%s: %s",
            section_key, run_id, exc,
        )
        return False


def save_executive_summary(
    run_id: str,
    idea: str,
    iteration: int,
    content: str,
    critique: str | None = None,
) -> str | None:
    """Persist an executive summary iteration to the ``workingIdeas`` document.

    Pushes a new record into the top-level ``executive_summary`` array.
    This is separate from the ``draft`` object — the executive summary
    is iterated as the first phase before section-level work begins.

    Args:
        run_id: The run identifier.
        idea: The current idea text.
        iteration: 1-based iteration number.
        content: The executive summary content for this iteration.
        critique: Critique feedback (``None`` for the initial draft).

    Returns:
        The document ``run_id`` as a string, or ``None`` on failure.
    """
    now = _now_iso()
    record = {
        "content": content,
        "iteration": iteration,
        "critique": critique,
        "updated_date": now,
    }
    try:
        db = get_db()
        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {
                "$push": {"executive_summary": record},
                "$set": {
                    "idea": idea,
                    "status": "inprogress",
                    "update_date": now,
                },
                "$setOnInsert": {
                    "run_id": run_id,
                    "created_at": now,
                    "completed_at": None,
                },
            },
            upsert=True,
        )
        doc_id = str(result.upserted_id) if result.upserted_id else run_id
        logger.info(
            "[MongoDB] Saved executive_summary iteration=%d for run_id=%s",
            iteration, run_id,
        )
        return doc_id
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save executive_summary iteration=%d "
            "for run_id=%s: %s",
            iteration, run_id, exc,
        )
        return None


def update_executive_summary_critique(
    run_id: str,
    iteration: int,
    critique: str,
) -> bool:
    """Update the critique field on an existing executive summary record.

    Finds the record in ``executive_summary`` whose ``iteration``
    matches and sets its ``critique`` and ``updated_date`` fields.

    Args:
        run_id: The run identifier.
        iteration: The iteration number to match.
        critique: The critique text to set.

    Returns:
        ``True`` if the record was updated, ``False`` otherwise.
    """
    now = _now_iso()
    try:
        db = get_db()
        result = db[WORKING_COLLECTION].update_one(
            {
                "run_id": run_id,
                "executive_summary.iteration": iteration,
            },
            {
                "$set": {
                    "executive_summary.$.critique": critique,
                    "executive_summary.$.updated_date": now,
                    "update_date": now,
                },
            },
        )
        updated = result.modified_count > 0
        logger.info(
            "[MongoDB] Updated executive_summary critique iteration=%d "
            "for run_id=%s (matched=%d)",
            iteration, run_id, result.modified_count,
        )
        return updated
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to update executive_summary critique "
            "run_id=%s: %s",
            run_id, exc,
        )
        return False


def save_finalized_idea(
    run_id: str,
    finalized_idea: str,
) -> bool:
    """Copy the last executive summary content to the top-level ``finalized_idea`` field.

    Called at the end of executive summary iteration to persist the
    approved content as a standalone field in the ``workingIdeas`` document.

    Args:
        run_id: The run identifier.
        finalized_idea: The executive summary content to store.

    Returns:
        ``True`` if the document was updated, ``False`` otherwise.
    """
    now = _now_iso()
    try:
        db = get_db()
        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "finalized_idea": finalized_idea,
                    "update_date": now,
                },
            },
        )
        updated = result.modified_count > 0
        logger.info(
            "[MongoDB] Saved finalized_idea for run_id=%s (matched=%d)",
            run_id, result.modified_count,
        )
        return updated
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save finalized_idea for run_id=%s: %s",
            run_id, exc,
        )
        return False


def save_pipeline_step(
    run_id: str,
    idea: str,
    pipeline_key: str,
    iteration: int,
    content: str,
    critique: str = "",
    step: str = "",
) -> str | None:
    """Persist a pre-PRD pipeline iteration (requirements breakdown, etc.).

    Stores the record under ``<pipeline_key>`` as a top-level array
    (e.g. ``requirements_breakdown``) — not nested under ``pipeline``
    — so the document matches the ``draft_prd_task`` JSON schema.

    Args:
        run_id: The run identifier.
        idea: The original user-inputted idea text.
        pipeline_key: Identifier for the pipeline stage
            (e.g. ``"requirements_breakdown"``).
        iteration: 1-based iteration number within this pipeline stage.
        content: The content produced in this iteration.
        critique: Evaluation / feedback text.
        step: Descriptive step label for logging.

    Returns:
        The document ``run_id`` as a string, or ``None`` on failure.
    """
    now = _now_iso()
    record = {
        "content": content,
        "iteration": iteration,
        "critique": critique,
        "step": step,
        "updated_date": now,
    }
    try:
        db = get_db()
        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {
                "$push": {f"{pipeline_key}": record},
                "$set": {
                    "idea": idea,
                    "status": "inprogress",
                    "update_date": now,
                },
                "$setOnInsert": {
                    "run_id": run_id,
                    "created_at": now,
                    "completed_at": None,
                },
            },
            upsert=True,
        )
        doc_id = str(result.upserted_id) if result.upserted_id else run_id
        logger.info(
            "[MongoDB] Saved pipeline step %s iteration=%d for run_id=%s",
            pipeline_key, iteration, run_id,
        )
        return doc_id
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save pipeline step %s for run_id=%s: %s",
            pipeline_key, run_id, exc,
        )
        return None


def save_failed(
    run_id: str,
    idea: str,
    iteration: int,
    error: str,
    draft: dict[str, str] | None = None,
    step: str = "",
    **extra: Any,
) -> str | None:
    """Mark a run as failed in ``workingIdeas``.

    Updates the existing document (or inserts one) with ``status=failed``
    and the error details.

    Returns:
        The document ``run_id`` as a string, or ``None`` on failure.
    """
    now = _now_iso()
    try:
        db = get_db()
        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "idea": idea,
                    "status": "failed",
                    "error": error,
                    "update_date": now,
                },
                "$setOnInsert": {
                    "run_id": run_id,
                    "created_at": now,
                    "completed_at": None,
                    "section": {},
                },
            },
            upsert=True,
        )
        doc_id = str(result.upserted_id) if result.upserted_id else run_id
        logger.info(
            "[MongoDB] Saved failure record for run_id=%s",
            run_id,
        )
        return doc_id
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save failure record for run_id=%s: %s",
            run_id,
            exc,
        )
        return None
