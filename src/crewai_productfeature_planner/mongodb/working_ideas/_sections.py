"""Iteration save and update operations on the ``workingIdeas`` collection.

Functions that persist new iteration records (sections, executive summary,
pipeline steps) or update existing records (critique fields).
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


def save_iteration(
    run_id: str,
    idea: str,
    iteration: int,
    draft: dict[str, str],
    critique: str = "",
    step: str = "",
    finalized_idea: str = "",
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

    # Guard against MongoDB field-path injection via dots or $ operators
    if section_key and ("." in section_key or section_key.startswith("$")):
        logger.error(
            "[MongoDB] Rejected section_key with illegal chars: %r",
            section_key,
        )
        return None

    # Build the iteration record to push into the section array
    iteration_record = {
        "content": draft.get(section_key, "") if section_key else "",
        "iteration": iteration,
        "critique": critique,
        "updated_date": now,
    }

    try:
        db = _common.get_db()

        # Never overwrite terminal statuses — if the idea was archived,
        # completed, or failed, preserve that status.
        _TERMINAL = {"archived", "completed", "failed"}
        existing = db[WORKING_COLLECTION].find_one(
            {"run_id": run_id}, {"status": 1}
        )
        current_status = existing.get("status") if existing else None

        set_fields: dict[str, Any] = {
            "update_date": now,
        }
        if current_status not in _TERMINAL:
            set_fields["status"] = "inprogress"
        if finalized_idea:
            set_fields["finalized_idea"] = finalized_idea
        if idea:
            set_fields["idea"] = idea

        update_ops: dict[str, Any] = {
            "$set": set_fields,
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
        db = _common.get_db()
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
        db = _common.get_db()

        # Never overwrite terminal statuses
        _TERMINAL = {"archived", "completed", "failed"}
        existing = db[WORKING_COLLECTION].find_one(
            {"run_id": run_id}, {"status": 1}
        )
        current_status = existing.get("status") if existing else None
        _status_set = {} if current_status in _TERMINAL else {"status": "inprogress"}

        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {
                "$push": {"executive_summary": record},
                "$set": {
                    **_status_set,
                    "update_date": now,
                },
                "$setOnInsert": {
                    "run_id": run_id,
                    "idea": idea,
                    "created_at": now,
                    "completed_at": None,
                    "section": {},
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
        db = _common.get_db()
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
        db = _common.get_db()
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
    finalized_idea: str = "",
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

    # Guard against MongoDB field-path injection via dots or $ operators
    if "." in pipeline_key or pipeline_key.startswith("$"):
        logger.error(
            "[MongoDB] Rejected pipeline_key with illegal chars: %r",
            pipeline_key,
        )
        return None

    try:
        db = _common.get_db()

        # Never overwrite terminal statuses
        _TERMINAL = {"archived", "completed", "failed"}
        existing = db[WORKING_COLLECTION].find_one(
            {"run_id": run_id}, {"status": 1}
        )
        current_status = existing.get("status") if existing else None

        set_fields: dict[str, Any] = {
            "update_date": now,
        }
        if current_status not in _TERMINAL:
            set_fields["status"] = "inprogress"
        if finalized_idea:
            set_fields["finalized_idea"] = finalized_idea

        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {
                "$push": {f"{pipeline_key}": record},
                "$set": set_fields,
                "$setOnInsert": {
                    "run_id": run_id,
                    "idea": idea,
                    "created_at": now,
                    "completed_at": None,
                    "section": {},
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
        db = _common.get_db()
        col = db[WORKING_COLLECTION]

        # Ensure the ``section`` field exists on pre-existing documents
        # that were created before this initialisation was added.  The
        # filter ``section: {$exists: false}`` guarantees we never
        # overwrite real section data.
        col.update_one(
            {"run_id": run_id, "section": {"$exists": False}},
            {"$set": {"section": {}}},
        )

        result = col.update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "status": "failed",
                    "error": error,
                    "update_date": now,
                },
                "$setOnInsert": {
                    "run_id": run_id,
                    "idea": idea,
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
