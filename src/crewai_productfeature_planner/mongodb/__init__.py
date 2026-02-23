"""MongoDB persistence package.

Re-exports public symbols for backward-compatible imports::

    from crewai_productfeature_planner.mongodb import save_iteration, mark_completed

Sub-modules:
    - ``mongodb.client``               — connection management
    - ``mongodb.working_ideas``        — ``workingIdeas`` collection
    - ``mongodb.crew_jobs``            — ``crewJobs`` collection (job tracking)
"""

from crewai_productfeature_planner.mongodb.client import (
    DEFAULT_DB_NAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    _build_uri,
    _get_db_name,
    get_client,
    get_db,
    reset_client,
)
from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
    CREW_JOBS_COLLECTION,
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
from crewai_productfeature_planner.mongodb.working_ideas.repository import (
    WORKING_COLLECTION,
    find_unfinalized,
    get_run_documents,
    mark_completed,
    save_executive_summary,
    save_failed,
    save_finalized_idea,
    save_iteration,
    save_pipeline_step,
    update_executive_summary_critique,
    update_section_critique,
)

__all__ = [
    "CREW_JOBS_COLLECTION",
    "DEFAULT_DB_NAME",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "WORKING_COLLECTION",
    "_build_uri",
    "_get_db_name",
    "create_job",
    "fail_incomplete_jobs_on_startup",
    "find_active_job",
    "find_job",
    "find_unfinalized",
    "get_client",
    "get_db",
    "get_run_documents",
    "list_jobs",
    "mark_completed",
    "reactivate_job",
    "reset_client",
    "save_failed",
    "save_finalized_idea",
    "save_executive_summary",
    "save_iteration",
    "save_pipeline_step",
    "update_executive_summary_critique",
    "update_job_completed",
    "update_job_failed",
    "update_job_started",
    "update_job_status",
    "update_section_critique",
]
