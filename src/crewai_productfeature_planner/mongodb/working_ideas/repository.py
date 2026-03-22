"""Repository for the ``workingIdeas`` collection -- re-export facade.

Stores PRD drafts using a single-document-per-run model.  Each run_id
maps to one document whose ``section`` object contains section keys with
arrays of iteration records (content, iteration, critique, updated_date).

All implementation lives in the private sub-modules ``_status``,
``_queries``, and ``_sections``.  This file re-exports every public
name so that existing ``from ...repository import X`` paths continue
to work unchanged.
"""

from crewai_productfeature_planner.mongodb.working_ideas._common import (  # noqa: F401
    WORKING_COLLECTION,
)

# -- Status transitions & field operations ----------------------------------
from crewai_productfeature_planner.mongodb.working_ideas._status import (  # noqa: F401
    ensure_section_field,
    get_jira_epics_stories_output,
    get_jira_skeleton,
    get_output_file,
    get_ux_output_file,
    mark_archived,
    mark_completed,
    mark_paused,
    save_figma_design,
    save_jira_epics_stories_output,
    save_jira_phase,
    save_jira_skeleton,
    save_output_file,
    save_project_ref,
    save_slack_context,
    save_ux_output_file,
)

# -- Query / lookup operations ----------------------------------------------
from crewai_productfeature_planner.mongodb.working_ideas._queries import (  # noqa: F401
    fail_unfinalized_on_startup,
    find_completed_ideas_by_project,
    find_completed_without_confluence,
    find_completed_without_output,
    find_ideas_by_project,
    find_run_any_status,
    find_unfinalized,
    get_run_documents,
)

# -- Iteration save / update operations -------------------------------------
from crewai_productfeature_planner.mongodb.working_ideas._sections import (  # noqa: F401
    save_executive_summary,
    save_failed,
    save_finalized_idea,
    save_iteration,
    save_pipeline_step,
    update_executive_summary_critique,
    update_section_critique,
)

__all__ = [
    "WORKING_COLLECTION",
    # _status
    "ensure_section_field",
    "get_jira_epics_stories_output",
    "get_jira_skeleton",
    "get_output_file",
    "mark_archived",
    "mark_completed",
    "mark_paused",
    "save_figma_design",
    "save_jira_epics_stories_output",
    "save_jira_phase",
    "save_jira_skeleton",
    "save_output_file",
    "save_project_ref",
    "save_slack_context",
    # _queries
    "fail_unfinalized_on_startup",
    "find_completed_ideas_by_project",
    "find_completed_without_confluence",
    "find_completed_without_output",
    "find_ideas_by_project",
    "find_run_any_status",
    "find_unfinalized",
    "get_run_documents",
    # _sections
    "save_executive_summary",
    "save_failed",
    "save_finalized_idea",
    "save_iteration",
    "save_pipeline_step",
    "update_executive_summary_critique",
    "update_section_critique",
]
