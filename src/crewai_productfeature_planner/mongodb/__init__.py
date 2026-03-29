"""MongoDB persistence package.

Re-exports public symbols for backward-compatible imports::

    from crewai_productfeature_planner.mongodb import save_iteration, mark_completed

Sub-modules:
    - ``mongodb.client``               — connection management
    - ``mongodb.working_ideas``        — ``workingIdeas`` collection
    - ``mongodb.crew_jobs``            — ``crewJobs`` collection (job tracking)
    - ``mongodb.product_requirements`` — ``productRequirements`` collection
    - ``mongodb.agent_interactions``   — ``agentInteraction`` collection (fine-tuning data)
    - ``mongodb.project_config``       — ``projectConfig`` collection (project-level configuration)
    - ``mongodb.project_memory``       — ``projectMemory`` collection (per-project agent memory)
    - ``mongodb.user_session``         — ``userSession`` collection (Slack session tracking)
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
from crewai_productfeature_planner.mongodb.project_config.repository import (
    PROJECT_CONFIG_COLLECTION,
    create_project,
    delete_project,
    get_project,
    get_project_by_name,
    get_project_for_run,
    list_projects,
    update_project,
)
from crewai_productfeature_planner.mongodb.project_memory.repository import (
    PROJECT_MEMORY_COLLECTION,
    MemoryCategory,
    add_memory_entry,
    clear_category,
    delete_memory_entry,
    get_memories_for_agent,
    get_project_memory,
    list_memory_entries,
    replace_category_entries,
    upsert_project_memory,
)
from crewai_productfeature_planner.mongodb.working_ideas.repository import (
    WORKING_COLLECTION,
    ensure_section_field,
    find_completed_without_confluence,
    find_completed_without_output,
    find_run_any_status,
    find_unfinalized,
    get_output_file,
    get_run_documents,
    get_ux_output_file,
    mark_archived,
    mark_completed,
    mark_paused,
    save_executive_summary,
    save_failed,
    save_finalized_idea,
    save_iteration,
    save_output_file,
    save_pipeline_step,
    save_ux_output_file,
    save_project_ref,
    save_slack_context,
    update_executive_summary_critique,
    update_section_critique,
)
from crewai_productfeature_planner.mongodb.user_session import (
    USER_SESSION_COLLECTION,
    end_active_session,
    get_active_session,
    get_session,
    list_sessions,
    start_session,
    switch_session,
)
from crewai_productfeature_planner.mongodb.user_suggestions import (
    USER_SUGGESTIONS_COLLECTION,
    find_suggestions_by_project,
    log_suggestion,
)

__all__ = [
    "AGENT_INTERACTIONS_COLLECTION",
    "CREW_JOBS_COLLECTION",
    "PROJECT_CONFIG_COLLECTION",
    "PROJECT_MEMORY_COLLECTION",
    "DEFAULT_DB_NAME",
    "PRODUCT_REQUIREMENTS_COLLECTION",
    "WORKING_COLLECTION",
    "USER_SESSION_COLLECTION",
    "MemoryCategory",
    "_build_uri",
    "_get_db_name",
    "add_memory_entry",
    "clear_category",
    "create_job",
    "create_project",
    "delete_memory_entry",
    "delete_project",
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
    "find_run_any_status",
    "find_unfinalized",
    "get_delivery_record",
    "get_client",
    "get_db",
    "get_interaction",
    "get_memories_for_agent",
    "get_output_file",
    "get_ux_output_file",
    "get_project",
    "get_project_by_name",
    "get_project_for_run",
    "get_project_memory",
    "get_run_documents",
    "list_interactions",
    "list_jobs",
    "list_memory_entries",
    "list_projects",
    "log_interaction",
    "mark_archived",
    "mark_completed",
    "mark_paused",
    "reactivate_job",
    "replace_category_entries",
    "reset_client",
    "save_failed",
    "save_finalized_idea",
    "save_executive_summary",
    "save_iteration",
    "save_output_file",
    "save_ux_output_file",
    "save_pipeline_step",
    "save_project_ref",
    "save_slack_context",
    "update_executive_summary_critique",
    "update_job_completed",
    "update_job_failed",
    "update_job_started",
    "update_job_status",
    "update_project",
    "update_section_critique",
    "upsert_delivery_record",
    "upsert_project_memory",
    "end_active_session",
    "get_active_session",
    "get_session",
    "list_sessions",
    "start_session",
    "switch_session",
]
