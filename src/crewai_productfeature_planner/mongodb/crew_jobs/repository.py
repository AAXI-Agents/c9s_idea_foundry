"""Repository for the ``crewJobs`` collection.

Tracks every flow run as a persistent job document with lifecycle
timestamps and computed durations.

Standard job document schema
----------------------------
::

    {
        "job_id":             str,              # unique identifier (same as run_id)
        "flow_name":          str,              # e.g. "prd"
        "idea":               str,              # feature idea / input text
        "status":             str,              # queued | running | awaiting_approval
                                                #   | paused | completed | failed
        "error":              str | None,       # error message when status == failed

        "queued_at":          datetime (UTC),    # when the job was created
        "started_at":         datetime | None,   # when execution began
        "completed_at":       datetime | None,   # when the job reached a terminal state

        "queue_time_ms":      int | None,        # (started_at - queued_at) in ms
        "queue_time_human":   str | None,        # e.g. "0h 0m 12s"
        "running_time_ms":    int | None,        # (completed_at - started_at) in ms
        "running_time_human": str | None,        # e.g. "1h 23m 45s"

        "updated_at":         datetime (UTC),    # last status update
    }
"""

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    tenant_fields,
    tenant_filter,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

CREW_JOBS_COLLECTION = "crewJobs"

# Statuses that indicate the job has not finished yet.
_INCOMPLETE_STATUSES = ["queued", "running", "awaiting_approval"]


# ── helpers ───────────────────────────────────────────────────


def _ms_between(start: datetime, end: datetime) -> int:
    """Return the difference in milliseconds between two datetimes.

    Handles mixed offset-naive / offset-aware datetimes by treating
    naive values as UTC.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    delta = end - start
    return int(delta.total_seconds() * 1000)


def _human_duration(ms: int) -> str:
    """Format milliseconds as ``Xh Ym Zs``.

    Examples:
        >>> _human_duration(0)
        '0h 0m 0s'
        >>> _human_duration(90_061)
        '0h 1m 30s'
        >>> _human_duration(3_723_000)
        '1h 2m 3s'
    """
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}h {minutes}m {seconds}s"


# ── queries (early – used by create_job guard) ───────────────


def find_active_job() -> dict[str, Any] | None:
    """Return the single incomplete job, if any.

    An *active* job is one whose status is in ``queued``, ``running``,
    or ``awaiting_approval``.  The crewJobs collection is designed to
    hold **at most one** active job at a time.

    Returns:
        The active job document, or ``None``.
    """
    try:
        return get_db()[CREW_JOBS_COLLECTION].find_one(
            {"status": {"$in": _INCOMPLETE_STATUSES}}
        )
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to query active job: %s", exc)
        return None


# ── create ────────────────────────────────────────────────────


def create_job(
    job_id: str,
    flow_name: str,
    idea: str = "",
    slack_channel: str | None = None,
    slack_thread_ts: str | None = None,
    tenant: TenantContext | None = None,
) -> str | None:
    """Insert a new job document in ``queued`` status.

    Only one active (incomplete) job is allowed at a time.  If an
    incomplete job already exists the call is rejected and ``None`` is
    returned.

    Args:
        job_id: Unique identifier (typically the ``run_id``).
        flow_name: Name of the flow being executed (e.g. ``"prd"``).
        idea: The feature idea or input text.
        slack_channel: Optional Slack channel (for auto-resume).
        slack_thread_ts: Optional Slack thread timestamp (for auto-resume).

    Returns:
        The inserted document ``_id`` as string, or ``None`` on failure.
    """
    try:
        active = find_active_job()
        if active is not None:
            logger.warning(
                "[CrewJobs] Rejected create_job(%s) — active job %s already exists (status=%s)",
                job_id, active.get("job_id"), active.get("status"),
            )
            return None
    except PyMongoError as exc:
        logger.error("[CrewJobs] Active-job check failed for %s: %s", job_id, exc)
        # Fail-open: allow the insert so we don't silently block work

    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "job_id": job_id,
        "flow_name": flow_name,
        "idea": idea,
        "status": "queued",
        "error": None,
        "slack_channel": slack_channel,
        "slack_thread_ts": slack_thread_ts,
        "queued_at": now,
        "started_at": None,
        "completed_at": None,
        "queue_time_ms": None,
        "queue_time_human": None,
        "running_time_ms": None,
        "running_time_human": None,
        "updated_at": now,
        **(tenant_fields(tenant) if tenant else {}),
    }
    try:
        result = get_db()[CREW_JOBS_COLLECTION].insert_one(doc)
        logger.info(
            "[CrewJobs] Created job %s (flow=%s, doc_id=%s)",
            job_id, flow_name, result.inserted_id,
        )
        return str(result.inserted_id)
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to create job %s: %s", job_id, exc)
        return None


# ── status transitions ───────────────────────────────────────


def update_job_status(job_id: str, status: str, **extra: Any) -> bool:
    """Generic status update for a job.

    Args:
        job_id: The job identifier.
        status: New status value.
        **extra: Additional fields to ``$set``.

    Returns:
        ``True`` if the document was updated, ``False`` otherwise.
    """
    update_fields: dict[str, Any] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
        **extra,
    }
    try:
        result = get_db()[CREW_JOBS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": update_fields},
        )
        if result.modified_count:
            logger.info("[CrewJobs] Job %s → %s", job_id, status)
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to update job %s to %s: %s", job_id, status, exc)
        return False


def update_job_started(job_id: str) -> bool:
    """Mark a job as ``running`` and record ``started_at``.

    Also computes ``queue_time_ms`` and ``queue_time_human`` from the
    difference between ``queued_at`` and now.

    Returns:
        ``True`` if the document was updated.
    """
    now = datetime.now(timezone.utc)
    try:
        db = get_db()
        doc = db[CREW_JOBS_COLLECTION].find_one({"job_id": job_id})
        if doc is None:
            logger.warning("[CrewJobs] Job %s not found for started update", job_id)
            return False

        queued_at = doc.get("queued_at")
        queue_time_ms: int | None = None
        queue_time_human: str | None = None
        if queued_at is not None:
            queue_time_ms = _ms_between(queued_at, now)
            queue_time_human = _human_duration(queue_time_ms)

        result = db[CREW_JOBS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "running",
                "started_at": now,
                "queue_time_ms": queue_time_ms,
                "queue_time_human": queue_time_human,
                "updated_at": now,
            }},
        )
        if result.modified_count:
            logger.info(
                "[CrewJobs] Job %s → running (queue_time=%s)",
                job_id, queue_time_human,
            )
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to start job %s: %s", job_id, exc)
        return False


def update_job_completed(job_id: str, status: str = "completed") -> bool:
    """Mark a job as completed (or paused) and compute running duration.

    Computes ``running_time_ms`` and ``running_time_human`` from the
    difference between ``started_at`` and now.

    Args:
        job_id: The job identifier.
        status: Terminal status — ``"completed"`` or ``"paused"``.

    Returns:
        ``True`` if the document was updated.
    """
    now = datetime.now(timezone.utc)
    try:
        db = get_db()
        doc = db[CREW_JOBS_COLLECTION].find_one({"job_id": job_id})
        if doc is None:
            logger.warning("[CrewJobs] Job %s not found for completed update", job_id)
            return False

        started_at = doc.get("started_at")
        running_time_ms: int | None = None
        running_time_human: str | None = None
        if started_at is not None:
            running_time_ms = _ms_between(started_at, now)
            running_time_human = _human_duration(running_time_ms)

        result = db[CREW_JOBS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": {
                "status": status,
                "completed_at": now,
                "running_time_ms": running_time_ms,
                "running_time_human": running_time_human,
                "updated_at": now,
            }},
        )
        if result.modified_count:
            logger.info(
                "[CrewJobs] Job %s → %s (running_time=%s)",
                job_id, status, running_time_human,
            )
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to complete job %s: %s", job_id, exc)
        return False


def update_job_failed(job_id: str, error: str) -> bool:
    """Mark a job as ``failed`` with an error message and compute running duration.

    Returns:
        ``True`` if the document was updated.
    """
    now = datetime.now(timezone.utc)
    try:
        db = get_db()
        doc = db[CREW_JOBS_COLLECTION].find_one({"job_id": job_id})

        running_time_ms: int | None = None
        running_time_human: str | None = None
        queue_time_ms: int | None = None
        queue_time_human: str | None = None

        if doc is not None:
            started_at = doc.get("started_at")
            if started_at is not None:
                running_time_ms = _ms_between(started_at, now)
                running_time_human = _human_duration(running_time_ms)
            # If started_at was never set, compute queue_time if missing
            queued_at = doc.get("queued_at")
            if doc.get("queue_time_ms") is None and queued_at is not None:
                queue_time_ms = _ms_between(queued_at, now)
                queue_time_human = _human_duration(queue_time_ms)

        update_fields: dict[str, Any] = {
            "status": "failed",
            "error": error,
            "completed_at": now,
            "updated_at": now,
        }
        if running_time_ms is not None:
            update_fields["running_time_ms"] = running_time_ms
            update_fields["running_time_human"] = running_time_human
        if queue_time_ms is not None:
            update_fields["queue_time_ms"] = queue_time_ms
            update_fields["queue_time_human"] = queue_time_human

        result = get_db()[CREW_JOBS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": update_fields},
        )
        if result.modified_count:
            logger.info("[CrewJobs] Job %s → failed: %s", job_id, error[:120])
        return result.modified_count > 0
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to mark job %s as failed: %s", job_id, exc)
        return False


def reactivate_job(job_id: str) -> bool:
    """Reset an existing job document back to ``queued`` for a resume.

    Clears terminal-state fields (``error``, ``completed_at``,
    running/queue times) so the job can be tracked through a fresh
    lifecycle while keeping the original ``queued_at``.

    Returns:
        ``True`` if the document was updated, ``False`` otherwise.
    """
    now = datetime.now(timezone.utc)
    try:
        result = get_db()[CREW_JOBS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "queued",
                "error": None,
                "started_at": None,
                "completed_at": None,
                "queue_time_ms": None,
                "queue_time_human": None,
                "running_time_ms": None,
                "running_time_human": None,
                "queued_at": now,
                "updated_at": now,
            }},
        )
        if result.modified_count:
            logger.info("[CrewJobs] Reactivated job %s for resume", job_id)
            return True
        if result.matched_count == 0:
            logger.warning("[CrewJobs] Job %s not found for reactivation", job_id)
        return False
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to reactivate job %s: %s", job_id, exc)
        return False


# ── queries ───────────────────────────────────────────────────


def find_job(job_id: str) -> dict[str, Any] | None:
    """Fetch a single job document by ``job_id``.

    Returns:
        The document dict, or ``None`` if not found or on error.
    """
    try:
        doc = get_db()[CREW_JOBS_COLLECTION].find_one({"job_id": job_id})
        return doc
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to find job %s: %s", job_id, exc)
        return None


def list_jobs(
    status: str | None = None,
    flow_name: str | None = None,
    limit: int = 50,
    tenant: TenantContext | None = None,
) -> list[dict[str, Any]]:
    """List jobs, optionally filtered by status and/or flow_name.

    Returns:
        A list of job documents sorted by ``queued_at`` descending.
    """
    query: dict[str, Any] = {}
    if tenant:
        query.update(tenant_filter(tenant))
    if status is not None:
        query["status"] = status
    if flow_name is not None:
        query["flow_name"] = flow_name
    try:
        cursor = (
            get_db()[CREW_JOBS_COLLECTION]
            .find(query)
            .sort("queued_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error("[CrewJobs] Failed to list jobs: %s", exc)
        return []


# ── startup recovery ─────────────────────────────────────────


def fail_incomplete_jobs_on_startup() -> list[dict[str, str]]:
    """Mark all incomplete jobs as failed on application startup.

    Any job whose status is in ``queued``, ``running``, or
    ``awaiting_approval`` is considered orphaned (the process that
    owned it has exited) and is marked ``failed`` with an appropriate
    error message.

    Returns:
        A list of dicts ``{"job_id": ..., "prev_status": ...}`` for
        each job that was marked as failed.  Empty list when nothing
        was recovered or on error.
    """
    now = datetime.now(timezone.utc)
    recovered: list[dict[str, str]] = []
    try:
        db = get_db()
        incomplete = list(
            db[CREW_JOBS_COLLECTION].find({"status": {"$in": _INCOMPLETE_STATUSES}})
        )
        for doc in incomplete:
            job_id = doc.get("job_id", "unknown")
            prev_status = doc.get("status", "unknown")

            running_time_ms: int | None = None
            running_time_human: str | None = None
            queue_time_ms: int | None = None
            queue_time_human: str | None = None

            started_at = doc.get("started_at")
            if started_at is not None:
                running_time_ms = _ms_between(started_at, now)
                running_time_human = _human_duration(running_time_ms)

            queued_at = doc.get("queued_at")
            if doc.get("queue_time_ms") is None and queued_at is not None:
                queue_time_ms = _ms_between(queued_at, now)
                queue_time_human = _human_duration(queue_time_ms)

            update_fields: dict[str, Any] = {
                "status": "failed",
                "error": (
                    f"Job was in '{prev_status}' status when the server/process "
                    f"restarted. Marked as failed due to force exit or server downtime."
                ),
                "completed_at": now,
                "updated_at": now,
            }
            if running_time_ms is not None:
                update_fields["running_time_ms"] = running_time_ms
                update_fields["running_time_human"] = running_time_human
            if queue_time_ms is not None:
                update_fields["queue_time_ms"] = queue_time_ms
                update_fields["queue_time_human"] = queue_time_human

            db[CREW_JOBS_COLLECTION].update_one(
                {"_id": doc["_id"]},
                {"$set": update_fields},
            )
            logger.warning(
                "[CrewJobs] Startup recovery: job %s (%s → failed) — "
                "force exit or server downtime",
                job_id, prev_status,
            )
            recovered.append({"job_id": job_id, "prev_status": prev_status})

        if recovered:
            logger.info(
                "[CrewJobs] Startup recovery complete — %d incomplete job(s) marked failed",
                len(recovered),
            )
        else:
            logger.info("[CrewJobs] Startup recovery — no incomplete jobs found")

        return recovered
    except PyMongoError as exc:
        logger.error("[CrewJobs] Startup recovery failed: %s", exc)
        return []


def archive_stale_jobs_on_startup() -> int:
    """Mark crew jobs as archived if their working idea is archived.

    On startup, cross-references non-final crew jobs against the
    workingIdeas collection.  Any job whose idea has ``status: "archived"``
    is marked ``archived`` so the scheduler and delivery scanner skip it.

    Returns:
        The number of jobs archived.
    """
    now = datetime.now(timezone.utc)
    count = 0
    try:
        db = get_db()
        # Find non-final crew jobs
        stale_statuses = ["queued", "running", "awaiting_approval", "paused"]
        jobs = list(
            db[CREW_JOBS_COLLECTION].find(
                {"status": {"$in": stale_statuses}},
                {"job_id": 1, "_id": 1},
            )
        )
        if not jobs:
            return 0

        job_ids = [j["job_id"] for j in jobs if j.get("job_id")]
        # Check which of these have archived working ideas
        archived_docs = list(
            db["workingIdeas"].find(
                {"run_id": {"$in": job_ids}, "status": "archived"},
                {"run_id": 1, "_id": 0},
            )
        )
        archived_ids = {d["run_id"] for d in archived_docs}

        for job in jobs:
            jid = job.get("job_id", "")
            if jid in archived_ids:
                db[CREW_JOBS_COLLECTION].update_one(
                    {"_id": job["_id"]},
                    {"$set": {
                        "status": "archived",
                        "error": "Idea was archived by user",
                        "completed_at": now,
                        "updated_at": now,
                    }},
                )
                count += 1
                logger.info(
                    "[CrewJobs] Startup: archived stale job %s "
                    "(idea was archived by user)",
                    jid,
                )

        if count:
            logger.info(
                "[CrewJobs] Startup: %d stale job(s) archived "
                "(ideas were archived by user)",
                count,
            )
        return count
    except PyMongoError as exc:
        logger.error("[CrewJobs] archive_stale_jobs_on_startup failed: %s", exc)
        return 0
