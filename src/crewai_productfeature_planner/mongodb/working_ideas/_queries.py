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

# Must match len(SECTION_ORDER) in apis.prd._sections — duplicated here
# to avoid a circular import through the apis package __init__.
_TOTAL_SECTIONS = 12


def find_completed_without_confluence() -> list[dict[str, Any]]:
    """Find completed working ideas that have not been published to Confluence.

    Uses a two-phase approach to avoid fetching large full documents
    unnecessarily: first queries with a lightweight projection to
    identify unpublished ``run_id`` values, then fetches full documents
    only for those that need publishing.

    Returns:
        A list of full document dicts, or an empty list on failure.
    """
    from crewai_productfeature_planner.mongodb.product_requirements import (
        PRODUCT_REQUIREMENTS_COLLECTION,
    )

    try:
        db = _common.get_db()

        # Phase 1: lightweight projection — only fetch run_id
        completed_ids = list(
            db[WORKING_COLLECTION]
            .find({"status": "completed"}, {"run_id": 1})
            .sort("created_at", -1)
        )
        if not completed_ids:
            logger.info(
                "[MongoDB] Found 0 completed idea(s) without Confluence publish",
            )
            return []

        run_ids = [d["run_id"] for d in completed_ids if d.get("run_id")]

        # Phase 2: exclude already-published run_ids
        published_ids: set[str] = set()
        if run_ids:
            published_docs = db[PRODUCT_REQUIREMENTS_COLLECTION].find(
                {
                    "run_id": {"$in": run_ids},
                    "confluence_published": True,
                },
                {"run_id": 1},
            )
            published_ids = {
                d["run_id"] for d in published_docs if d.get("run_id")
            }

        unpublished_ids = [
            rid for rid in run_ids if rid not in published_ids
        ]

        if not unpublished_ids:
            logger.info(
                "[MongoDB] Found 0 completed idea(s) without Confluence publish",
            )
            return []

        # Phase 3: fetch full documents only for unpublished run_ids
        result = list(
            db[WORKING_COLLECTION]
            .find({"run_id": {"$in": unpublished_ids}})
            .sort("created_at", -1)
        )
        logger.info(
            "[MongoDB] Found %d completed idea(s) without Confluence publish",
            len(result),
        )
        return result
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


def find_resumable_on_startup() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition unfinalized ideas into resumable vs failed on startup.

    Ideas with Slack context (``slack_channel`` + ``slack_thread_ts``)
    and ``inprogress`` or ``paused`` status are considered resumable.
    All other unfinalized ideas are marked as ``failed``.

    Returns:
        A 2-tuple ``(resumable, failed)`` where each element is a list
        of dicts with ``run_id``, ``idea``, ``prev_status``,
        ``slack_channel``, ``slack_thread_ts``.
    """
    now = _now_iso()
    resumable: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    try:
        db = _common.get_db()
        query = {"status": {"$nin": ["completed", "archived", "failed"]}}
        docs = list(db[WORKING_COLLECTION].find(query))
        for doc in docs:
            run_id = doc.get("run_id", "unknown")
            prev_status = doc.get("status", "unknown")
            slack_channel = doc.get("slack_channel")
            slack_thread_ts = doc.get("slack_thread_ts")

            info = {
                "run_id": run_id,
                "idea": doc.get("idea", ""),
                "prev_status": prev_status,
                "slack_channel": slack_channel,
                "slack_thread_ts": slack_thread_ts,
                "project_id": doc.get("project_id"),
            }

            # Resumable: has Slack context and was actively running
            if (
                slack_channel
                and slack_thread_ts
                and prev_status in ("inprogress", "paused")
            ):
                resumable.append(info)
                logger.info(
                    "[MongoDB] Startup: idea %s (%s) is resumable",
                    run_id, prev_status,
                )
            else:
                # Mark as failed
                db[WORKING_COLLECTION].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "status": "failed",
                        "error": (
                            f"Run was in '{prev_status}' status when the "
                            f"server restarted. No Slack context available "
                            f"for auto-resume."
                        ),
                        "update_date": now,
                    }},
                )
                failed.append(info)
                logger.warning(
                    "[MongoDB] Startup recovery: working idea %s "
                    "(%s -> failed) — no resume context",
                    run_id, prev_status,
                )

        logger.info(
            "[MongoDB] Startup partition: %d resumable, %d failed",
            len(resumable), len(failed),
        )
        return resumable, failed
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Startup partition (unfinalized ideas) failed: %s", exc,
        )
        return [], []


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
                "total_sections": _TOTAL_SECTIONS,
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
    is absent or null.  For each, checks whether the document's own
    ``slack_channel`` matches the given *channel*.  If the document
    has no ``slack_channel``, falls back to checking the corresponding
    crew job.  Matching documents get their ``project_id`` back-filled
    in MongoDB so future queries find them normally.

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
            # Primary check: does the document's own slack_channel match?
            doc_channel = doc.get("slack_channel") or ""
            if doc_channel == channel:
                _do_backfill(db, run_id, project_id, channel, doc, matched)
                continue
            # Fallback: check the crew job's channel
            job = find_job(run_id)
            if not job:
                continue
            job_channel = job.get("slack_channel") or ""
            if job_channel != channel:
                continue
            _do_backfill(db, run_id, project_id, channel, doc, matched)
        return matched
    except PyMongoError as exc:
        logger.debug("_backfill_orphaned_ideas failed: %s", exc)
        return []


def _do_backfill(
    db,
    run_id: str,
    project_id: str,
    channel: str,
    doc: dict,
    matched: list,
) -> None:
    """Backfill ``project_id`` on a single orphaned document."""
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


def _doc_to_idea_dict(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw working-idea document to the dict format
    returned by :func:`find_ideas_by_project`."""
    total_sections = _TOTAL_SECTIONS
    status = doc.get("status", "unknown")

    section_obj = doc.get("section") or {}
    sections = [k for k, v in section_obj.items() if isinstance(v, list) and v]
    # The executive summary is stored at the document root, not
    # inside the ``section`` object.  Count it as a completed section
    # when present, but avoid double-counting if it also appears
    # under ``section`` (unlikely but defensive).
    raw_exec = doc.get("executive_summary", [])
    has_exec = isinstance(raw_exec, list) and len(raw_exec) > 0
    exec_already_counted = "executive_summary" in sections
    sections_done = len(sections) + (1 if has_exec and not exec_already_counted else 0)

    # A completed idea has all sections done by definition.
    if status == "completed":
        sections_done = total_sections

    max_iter = 0
    for entries in section_obj.values():
        if isinstance(entries, list):
            for entry in entries:
                it = entry.get("iteration", 0) if isinstance(entry, dict) else 0
                if it > max_iter:
                    max_iter = it
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
        "status": status,
        "iteration": effective_iter,
        "created_at": doc.get("created_at"),
        "sections_done": sections_done,
        "total_sections": total_sections,
    }


def has_active_idea_flow(project_id: str) -> bool:
    """Return ``True`` if the project has any in-progress idea flow.

    Checks the ``workingIdeas`` collection for documents with
    ``status == "inprogress"`` and matching *project_id*.  Used by
    admin guardrails to prevent project configuration while a flow
    is actively running.
    """
    try:
        db = _common.get_db()
        count = db[WORKING_COLLECTION].count_documents(
            {"project_id": project_id, "status": "inprogress"},
            limit=1,
        )
        return count > 0
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] has_active_idea_flow check failed for project %s: %s",
            project_id, exc,
        )
        return False


def find_ideas_by_project(
    project_id: str,
    *,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Find all working ideas associated with a project.

    Returns ideas that are still actionable (in-progress, paused,
    failed) — excludes ``archived`` and ``completed`` statuses.
    Results are sorted newest-first.

    When *channel* is provided the query also matches orphaned ideas
    (those missing ``project_id``) that live in the same Slack channel
    — either by their own ``slack_channel`` field or via the crew-job
    collection.  Matched orphans are back-filled with *project_id* so
    subsequent queries find them without the channel hint.

    Returns:
        A list of dicts, each containing: ``run_id``, ``idea``,
        ``status``, ``iteration``, ``created_at``, ``sections_done``,
        ``total_sections``.  Returns an empty list on failure.
    """
    try:
        db = _common.get_db()

        # Build an $or query that catches both project-matched AND
        # channel-matched orphan ideas in a single round-trip so that
        # in-progress ideas without project_id are never invisible.
        or_conditions: list[dict[str, Any]] = [
            {"project_id": project_id},
        ]
        if channel:
            _no_project = {
                "$or": [
                    {"project_id": {"$exists": False}},
                    {"project_id": None},
                    {"project_id": ""},
                ],
            }
            or_conditions.append(
                {"slack_channel": channel, **_no_project},
            )

        query: dict[str, Any] = {
            "status": {"$nin": ["archived", "completed"]},
            "$or": or_conditions,
        }

        docs = list(db[WORKING_COLLECTION].find(query).sort("created_at", -1))
        known_run_ids = {doc.get("run_id") for doc in docs}

        # Attempt to rescue orphaned ideas whose slack_channel is also
        # missing — falls back to crew-jobs channel lookup.
        if channel:
            orphan_docs = _backfill_orphaned_ideas(project_id, channel)
            for od in orphan_docs:
                if od.get("run_id") not in known_run_ids:
                    docs.append(od)
                    known_run_ids.add(od.get("run_id"))

        # Backfill project_id on any docs found via the channel match
        # so future queries find them by project_id alone.
        for doc in docs:
            _pid = doc.get("project_id")
            if _pid in (None, "") or "project_id" not in doc:
                _rid = doc.get("run_id", "")
                if _rid:
                    try:
                        db[WORKING_COLLECTION].update_one(
                            {"run_id": _rid},
                            {"$set": {
                                "project_id": project_id,
                                "update_date": _now_iso(),
                            }},
                        )
                        doc["project_id"] = project_id
                        logger.info(
                            "[MongoDB] Inline backfilled project_id=%s "
                            "for run_id=%s",
                            project_id, _rid,
                        )
                    except PyMongoError:
                        logger.debug(
                            "Inline backfill failed for run_id=%s",
                            _rid, exc_info=True,
                        )

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


def _doc_to_product_dict(doc: dict[str, Any], delivery: dict[str, Any] | None) -> dict[str, Any]:
    """Convert a completed working-idea doc to a product summary dict.

    Enriches the basic idea dict with delivery status fields from the
    ``productRequirements`` delivery record.
    """
    base = _doc_to_idea_dict(doc)
    base["confluence_url"] = (
        (delivery.get("confluence_url") if delivery else None)
        or doc.get("confluence_url")
        or ""
    )
    base["jira_phase"] = doc.get("jira_phase") or ""
    # The delivery record (productRequirements) is the sole authority
    # for whether Confluence was actually published.  A stale
    # ``confluence_url`` on the workingIdeas document must NOT be
    # treated as proof of publication — the URL may be left over
    # from a prior publish that was subsequently reset/deleted.
    base["confluence_published"] = bool(
        delivery and delivery.get("confluence_published")
    )
    # The ``jira_phase`` field on the working-idea document is the
    # authoritative source of truth for the interactive Jira flow.
    # When the interactive flow is active (jira_phase is set and not
    # "subtasks_done"), override the delivery record — the user has
    # explicitly started or restarted phased Jira ticketing and the
    # delivery record may hold stale data from a prior auto-delivery.
    raw_jira_done = bool(delivery and delivery.get("jira_completed"))
    jira_tickets = (delivery.get("jira_tickets") or []) if delivery else []
    jira_phase = base["jira_phase"]
    if jira_phase and jira_phase != "subtasks_done":
        # Interactive flow is in progress — not done yet.
        base["jira_completed"] = False
    elif jira_phase == "subtasks_done":
        # Interactive flow completed — but cross-validate against the
        # delivery record.  If the delivery record has no tickets AND
        # does not confirm jira_completed, the phase marker is stale
        # (e.g. leftover from pre-approval-gate code or a data fix
        # that only partially cleaned up).
        base["jira_completed"] = bool(raw_jira_done or jira_tickets)
    elif raw_jira_done and not jira_tickets:
        # No interactive flow, delivery says done but zero tickets — bogus.
        base["jira_completed"] = False
    else:
        base["jira_completed"] = raw_jira_done
    base["jira_tickets"] = jira_tickets
    # UX design status from the working-idea document.
    base["ux_design_status"] = (
        doc.get("ux_design_status")
        or doc.get("figma_design_status")
        or ""
    )
    return base


def find_completed_ideas_by_project(
    project_id: str,
    *,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Find all *completed* (not archived) working ideas for a project.

    This powers the "list products" intent — showing ideas that are
    ready for delivery manager actions (Confluence publish, Jira
    skeleton review, Jira epic/story & sub-task creation).

    Returns:
        A list of dicts with idea info plus delivery status fields.
        Sorted newest-first.  Returns an empty list on failure.
    """
    try:
        db = _common.get_db()

        or_conditions: list[dict[str, Any]] = [
            {"project_id": project_id},
        ]
        if channel:
            _no_project = {
                "$or": [
                    {"project_id": {"$exists": False}},
                    {"project_id": None},
                    {"project_id": ""},
                ],
            }
            or_conditions.append(
                {"slack_channel": channel, **_no_project},
            )

        query: dict[str, Any] = {
            "status": "completed",
            "$or": or_conditions,
        }

        docs = list(db[WORKING_COLLECTION].find(query).sort("created_at", -1))

        # Enrich each doc with its delivery record
        from crewai_productfeature_planner.mongodb.product_requirements import (
            get_delivery_record,
        )

        products: list[dict[str, Any]] = []
        for doc in docs:
            run_id = doc.get("run_id", "")
            if not run_id:
                continue
            record = get_delivery_record(run_id)
            products.append(_doc_to_product_dict(doc, record))

        logger.info(
            "[MongoDB] Found %d completed product(s) for project_id=%s",
            len(products), project_id,
        )
        return products
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] Failed to query completed products for project_id=%s: %s",
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
            {"run_id": run_id, "status": {"$nin": ["completed", "archived"]}}
        )
        if doc is None:
            logger.info("[MongoDB] No document found for run_id=%s", run_id)
            return []
        logger.info("[MongoDB] Fetched document for run_id=%s", run_id)
        return [doc]
    except PyMongoError as exc:
        logger.error("[MongoDB] Failed to fetch document for run_id=%s: %s", run_id, exc)
        return []


def find_idea_by_thread(
    channel: str,
    thread_ts: str,
) -> dict[str, Any] | None:
    """Find the most-recent working-idea document for a Slack thread.

    Looks up by ``slack_channel`` + ``slack_thread_ts``.  Excludes
    archived ideas.  Returns the newest match (by ``created_at``
    descending) or ``None``.
    """
    try:
        db = _common.get_db()
        doc = db[WORKING_COLLECTION].find_one(
            {
                "slack_channel": channel,
                "slack_thread_ts": thread_ts,
                "status": {"$ne": "archived"},
            },
            sort=[("created_at", -1)],
        )
        return doc
    except PyMongoError as exc:
        logger.error(
            "[MongoDB] find_idea_by_thread failed (channel=%s thread=%s): %s",
            channel, thread_ts, exc,
        )
        return None
