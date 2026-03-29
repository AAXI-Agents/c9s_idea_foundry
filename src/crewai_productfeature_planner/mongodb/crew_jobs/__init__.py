"""crew_jobs sub-package — persistence for flow run job tracking.

Re-exports the public repository API so callers can do::

    from crewai_productfeature_planner.mongodb.crew_jobs import create_job, ...
"""

from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
    CREW_JOBS_COLLECTION,
    archive_stale_jobs_on_startup,
    create_job,
    fail_incomplete_jobs_on_startup,
    find_active_job,
    find_job,
    list_jobs,
    reactivate_job,
    update_job_completed,
    update_job_failed,
    update_job_started,
    update_job_status,
)

__all__ = [
    "CREW_JOBS_COLLECTION",
    "archive_stale_jobs_on_startup",
    "create_job",
    "fail_incomplete_jobs_on_startup",
    "find_active_job",
    "find_job",
    "list_jobs",
    "reactivate_job",
    "update_job_completed",
    "update_job_failed",
    "update_job_started",
    "update_job_status",
]
