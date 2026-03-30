"""Status transitions, field updates, and metadata persistence.

Functions that change the status of a working-idea document (completed,
paused, archived) or update simple scalar fields (output_file,
project_id, slack_context).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.working_ideas import _common
from crewai_productfeature_planner.mongodb.working_ideas._common import (
    WORKING_COLLECTION,
    _now_iso,
    logger,
)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def mark_completed(run_id: str) -> int:
    """Mark the working-idea document for *run_id* as ``completed``.

    Sets ``status`` to ``"completed"`` so that ``find_unfinalized``
    excludes the run.

    Returns:
        The number of documents updated (0 or 1), or ``0`` on failure.
    """
    try:
        now = datetime.now(timezone.utc)
        result = _common.get_db()[WORKING_COLLECTION].update_one(
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


def mark_paused(run_id: str) -> int:
    """Mark the working-idea document for *run_id* as ``paused``.

    Called after ``save_progress()`` writes partial output so the
    document status reflects that the run can be resumed, not that
    it permanently failed.

    Returns:
        The number of documents updated (0 or 1), or ``0`` on failure.
    """
    try:
        now = _now_iso()
        result = _common.get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": {
                "status": "paused",
                "update_date": now,
            }},
        )
        logger.info(
            "[MongoDB] Marked working-idea doc paused for run_id=%s (matched=%d)",
            run_id, result.modified_count,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to mark working idea paused for run_id=%s: %s",
            run_id, exc,
        )
        return 0


def mark_archived(run_id: str) -> int:
    """Mark the working-idea document for *run_id* as ``archived``.

    Archived runs are preserved for reference but excluded from
    ``find_unfinalized()`` so they no longer appear as active or
    resumable.  Used when the user explicitly restarts a PRD flow —
    the old run is archived and a fresh flow begins with the same idea.

    Returns:
        The number of documents updated (0 or 1), or ``0`` on failure.
    """
    try:
        now = _now_iso()
        result = _common.get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": {
                "status": "archived",
                "archived_at": now,
                "update_date": now,
            }},
        )
        logger.info(
            "[MongoDB] Marked working-idea doc archived for run_id=%s (matched=%d)",
            run_id, result.modified_count,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to mark working idea archived for run_id=%s: %s",
            run_id, exc,
        )
        return 0


# ---------------------------------------------------------------------------
# Field operations
# ---------------------------------------------------------------------------


def ensure_section_field(run_id: str) -> bool:
    """Ensure the ``section`` field exists on the working-idea document.

    If the ``section`` object was accidentally deleted or never created,
    this function re-initialises it to an empty dict so that subsequent
    ``save_iteration`` / ``$push`` operations work correctly.

    The filter ``section: {$exists: false}`` guarantees we never
    overwrite real section data.

    Returns:
        ``True`` if the field was (re-)created, ``False`` if it already
        existed or on failure.
    """
    try:
        db = _common.get_db()
        result = db[WORKING_COLLECTION].update_one(
            {"run_id": run_id, "section": {"$exists": False}},
            {"$set": {"section": {}}},
        )
        if result.modified_count > 0:
            logger.warning(
                "[MongoDB] Re-initialised missing 'section' field "
                "for run_id=%s",
                run_id,
            )
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to ensure section field for run_id=%s: %s",
            run_id, exc,
        )
        return False


def get_output_file(run_id: str) -> str | None:
    """Return the current ``output_file`` path for *run_id*, or ``None``.

    Used to look up a previously-stored markdown path so the caller
    can delete the old file before persisting a new one.
    """
    try:
        db = _common.get_db()
        doc = db[WORKING_COLLECTION].find_one(
            {"run_id": run_id},
            {"output_file": 1, "_id": 0},
        )
        if doc:
            return doc.get("output_file") or None
        return None
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to get output_file for run_id=%s: %s",
            run_id, exc,
        )
        return None


def save_output_file(run_id: str, output_file: str) -> bool:
    """Store the generated markdown file path on the working-idea document.

    Called after ``PRDFileWriteTool`` successfully writes a file so that
    the ``workingIdeas`` document contains a reference to the on-disk
    output.

    Args:
        run_id: The run identifier.
        output_file: Relative or absolute path to the generated markdown
            file (e.g. ``"output/prds/2026/02/prd_v10_20260223_071542.md"``).

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
                    "output_file": output_file,
                    "update_date": now,
                },
            },
        )
        updated = result.modified_count > 0
        logger.info(
            "[MongoDB] Saved output_file for run_id=%s: %s (matched=%d)",
            run_id, output_file, result.modified_count,
        )
        return updated
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save output_file for run_id=%s: %s",
            run_id, exc,
        )
        return False


def get_ux_output_file(run_id: str) -> str | None:
    """Return the current ``ux_output_file`` path for *run_id*, or ``None``."""
    try:
        db = _common.get_db()
        doc = db[WORKING_COLLECTION].find_one(
            {"run_id": run_id},
            {"ux_output_file": 1, "_id": 0},
        )
        if doc:
            return doc.get("ux_output_file") or None
        return None
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to get ux_output_file for run_id=%s: %s",
            run_id, exc,
        )
        return None


def save_ux_output_file(run_id: str, ux_output_file: str) -> bool:
    """Store the UX design markdown file path on the working-idea document.

    Args:
        run_id: The run identifier.
        ux_output_file: Path to the generated UX design markdown file.

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
                    "ux_output_file": ux_output_file,
                    "update_date": now,
                },
            },
        )
        updated = result.modified_count > 0
        logger.info(
            "[MongoDB] Saved ux_output_file for run_id=%s: %s (matched=%d)",
            run_id, ux_output_file, result.modified_count,
        )
        return updated
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save ux_output_file for run_id=%s: %s",
            run_id, exc,
        )
        return False


# ---------------------------------------------------------------------------
# Metadata persistence
# ---------------------------------------------------------------------------


def save_project_ref(run_id: str, project_id: str, *, idea: str = "") -> int:
    """Associate a working-idea document with a project configuration.

    Sets the ``project_id`` field so the run can look up its
    project-level Confluence space key, Jira project key, and
    other project config via :func:`get_project_for_run`.

    Uses ``upsert=True`` so the association can be persisted even
    before the first ``save_iteration`` call creates the full
    document.  This ensures in-progress runs are visible to
    ``find_ideas_by_project`` as soon as the flow starts.

    Args:
        run_id: The run identifier.
        project_id: The project configuration identifier.
        idea: The original user-submitted idea text.  When non-empty
            the field is persisted via ``$set`` so the idea is always
            available for listing and rescan.

    Returns:
        Number of documents modified or created (0 or 1).
    """
    try:
        now = _now_iso()
        set_fields: dict[str, Any] = {
            "project_id": project_id,
            "update_date": now,
        }
        insert_fields: dict[str, Any] = {
            "run_id": run_id,
            "created_at": now,
            "status": "inprogress",
        }
        if idea:
            set_fields["idea"] = idea
        result = _common.get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {
                "$set": set_fields,
                "$setOnInsert": insert_fields,
            },
            upsert=True,
        )
        modified = result.modified_count + (1 if result.upserted_id else 0)
        logger.info(
            "[MongoDB] Saved project_id=%s for run_id=%s (matched=%d, upserted=%s)",
            project_id,
            run_id,
            result.matched_count,
            bool(result.upserted_id),
        )
        return modified
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save project ref for run_id=%s: %s",
            run_id,
            exc,
        )
        return 0


def save_slack_context(
    run_id: str,
    slack_channel: str,
    slack_thread_ts: str,
    *,
    idea: str = "",
) -> int:
    """Persist the Slack channel and thread_ts for a working-idea run.

    Called when a Slack-initiated PRD flow starts so the server can
    notify the same thread on auto-resume after a restart.

    Uses ``upsert=True`` so the context can be persisted even before
    the first ``save_iteration`` call creates the full document.

    Args:
        run_id: The run identifier.
        slack_channel: The Slack channel ID.
        slack_thread_ts: The Slack thread timestamp.
        idea: The original user-submitted idea text.  When non-empty
            the field is persisted via ``$set`` so the idea is always
            available for listing and rescan.

    Returns:
        Number of documents modified or created (0 or 1).
    """
    try:
        now = _now_iso()
        set_fields: dict[str, Any] = {
            "slack_channel": slack_channel,
            "slack_thread_ts": slack_thread_ts,
            "update_date": now,
        }
        insert_fields: dict[str, Any] = {
            "run_id": run_id,
            "created_at": now,
            "status": "inprogress",
        }
        if idea:
            set_fields["idea"] = idea
        result = _common.get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {
                "$set": set_fields,
                "$setOnInsert": insert_fields,
            },
            upsert=True,
        )
        modified = result.modified_count + (1 if result.upserted_id else 0)
        logger.info(
            "[MongoDB] Saved Slack context for run_id=%s "
            "(channel=%s, thread_ts=%s, matched=%d, upserted=%s)",
            run_id, slack_channel, slack_thread_ts,
            result.matched_count, bool(result.upserted_id),
        )
        return modified
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save Slack context for run_id=%s: %s",
            run_id, exc,
        )
        return 0


def save_jira_phase(run_id: str, phase: str) -> int:
    """Persist the current Jira ticketing phase on a working-idea document.

    The phase is stored at ``workingIdeas.jira_phase`` so the startup
    delivery scheduler can detect when an interactive flow is managing
    the Jira lifecycle and avoid creating tickets autonomously.

    Phase values:
        ``""``                  Not started / rejected
        ``"skeleton_pending"``  Skeleton generated, awaiting user approval
        ``"skeleton_approved"`` User approved, Phase 2 may proceed
        ``"epics_stories_done"`` Epics & Stories created, awaiting review
        ``"subtasks_ready"``    User approved, Phase 3 may proceed
        ``"subtasks_done"``     All Jira phases complete

    Returns:
        Number of documents modified (0 or 1).
    """
    try:
        result = _common.get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": {
                "jira_phase": phase,
                "update_date": _now_iso(),
            }},
        )
        logger.info(
            "[MongoDB] Saved jira_phase=%s for run_id=%s (matched=%d)",
            phase, run_id, result.modified_count,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save jira_phase for run_id=%s: %s",
            run_id, exc,
        )
        return 0


def save_ux_design(
    run_id: str,
    *,
    status: str = "",
) -> int:
    """Persist UX design status on a working-idea document.

    Updates ``ux_design_status`` on the ``workingIdeas`` document so
    the product list can show the current design state.

    Returns:
        Number of documents modified (0 or 1).
    """
    set_fields: dict = {"update_date": _now_iso()}
    if status:
        set_fields["ux_design_status"] = status

    try:
        result = _common.get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": set_fields},
        )
        logger.info(
            "[MongoDB] Saved ux_design (status=%s) for run_id=%s",
            status or "(unchanged)", run_id,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save ux_design for run_id=%s: %s",
            run_id, exc,
        )
        return 0


# Keep backward-compatible alias for any code still referencing the old name.
save_figma_design = save_ux_design


def save_jira_skeleton(run_id: str, skeleton: str) -> int:
    """Persist the Jira skeleton text on a working-idea document.

    The skeleton is stored at ``workingIdeas.jira_skeleton`` so it
    can be shown to the user when they resume the approval flow.

    Returns:
        Number of documents modified (0 or 1).
    """
    try:
        result = _common.get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": {
                "jira_skeleton": skeleton,
                "update_date": _now_iso(),
            }},
        )
        logger.info(
            "[MongoDB] Saved jira_skeleton for run_id=%s (%d chars, matched=%d)",
            run_id, len(skeleton), result.modified_count,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save jira_skeleton for run_id=%s: %s",
            run_id, exc,
        )
        return 0


def get_jira_skeleton(run_id: str) -> str:
    """Retrieve the persisted Jira skeleton for *run_id*.

    Returns:
        The skeleton text, or an empty string if not found.
    """
    try:
        doc = _common.get_db()[WORKING_COLLECTION].find_one(
            {"run_id": run_id},
            {"jira_skeleton": 1},
        )
        if doc:
            return doc.get("jira_skeleton") or ""
        return ""
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to fetch jira_skeleton for run_id=%s: %s",
            run_id, exc,
        )
        return ""


def save_jira_epics_stories_output(run_id: str, output: str) -> int:
    """Persist the Epics & Stories crew output on a working-idea document.

    Stored at ``workingIdeas.jira_epics_stories_output`` so that the
    Sub-tasks stage can resume after a server restart without
    re-running Phase 2.

    Returns:
        Number of documents modified (0 or 1).
    """
    try:
        result = _common.get_db()[WORKING_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": {
                "jira_epics_stories_output": output,
                "update_date": _now_iso(),
            }},
        )
        logger.info(
            "[MongoDB] Saved jira_epics_stories_output for run_id=%s "
            "(%d chars, matched=%d)",
            run_id, len(output), result.modified_count,
        )
        return result.modified_count
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to save jira_epics_stories_output for run_id=%s: %s",
            run_id, exc,
        )
        return 0


def get_jira_epics_stories_output(run_id: str) -> str:
    """Retrieve the persisted Epics & Stories output for *run_id*.

    Returns:
        The output text, or an empty string if not found.
    """
    try:
        doc = _common.get_db()[WORKING_COLLECTION].find_one(
            {"run_id": run_id},
            {"jira_epics_stories_output": 1},
        )
        if doc:
            return doc.get("jira_epics_stories_output") or ""
        return ""
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to fetch jira_epics_stories_output for run_id=%s: %s",
            run_id, exc,
        )
        return ""
