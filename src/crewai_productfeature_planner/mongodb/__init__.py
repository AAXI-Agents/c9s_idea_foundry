"""MongoDB persistence package.

Re-exports public symbols for backward-compatible imports::

    from crewai_productfeature_planner.mongodb import save_iteration, mark_completed

Sub-modules:
    - ``mongodb.client``               — connection management
    - ``mongodb.working_ideas``        — ``workingIdeas`` collection
    - ``mongodb.crew_jobs``            — ``crewJobs`` collection (job tracking)
    - ``mongodb.product_requirements`` — ``productRequirements`` collection
    - ``mongodb.agent_interactions``   — ``agentInteraction`` collection (fine-tuning data)
"""

from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
    AGENT_INTERACTIONS_COLLECTION,
    find_interactions,
    find_interactions_by_intent,
    find_interactions_by_source,
    get_interaction,
    list_interactions,
    log_interaction,
)
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
from crewai_productfeature_planner.mongodb.product_requirements.repository import (
    PRODUCT_REQUIREMENTS_COLLECTION,
    find_pending_delivery,
    get_delivery_record,
    upsert_delivery_record,
)
from crewai_productfeature_planner.mongodb.working_ideas.repository import (
    WORKING_COLLECTION,
    ensure_section_field,
    find_completed_without_confluence,
    find_completed_without_output,
    find_unfinalized,
    get_output_file,
    get_run_documents,
    mark_completed,
    mark_paused,
    save_confluence_url,
    save_executive_summary,
    save_failed,
    save_finalized_idea,
    save_iteration,
    save_output_file,
    save_pipeline_step,
    update_executive_summary_critique,
    update_section_critique,
)

__all__ = [
    "AGENT_INTERACTIONS_COLLECTION",
    "CREW_JOBS_COLLECTION",
    "DEFAULT_DB_NAME",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "PRODUCT_REQUIREMENTS_COLLECTION",
    "WORKING_COLLECTION",
    "_build_uri",
    "_get_db_name",
    "create_job",
    "ensure_section_field",
    "fail_incomplete_jobs_on_startup",
    "find_active_job",
    "find_completed_without_confluence",
    "find_completed_without_output",
    "find_interactions",
    "find_interactions_by_intent",
    "find_interactions_by_source",
    "find_job",
    "find_pending_delivery",
    "find_unfinalized",
    "get_delivery_record",
    "get_client",
    "get_db",
    "get_interaction",
    "get_output_file",
    "get_run_documents",
    "list_interactions",
    "list_jobs",
    "log_interaction",
    "mark_completed",
    "mark_paused",
    "reactivate_job",
    "reset_client",
    "save_confluence_url",
    "save_failed",
    "save_finalized_idea",
    "save_executive_summary",
    "save_iteration",
    "save_output_file",
    "save_pipeline_step",
    "update_executive_summary_critique",
    "update_job_completed",
    "update_job_failed",
    "update_job_started",
    "update_job_status",
    "update_section_critique",
    "upsert_delivery_record",
]
