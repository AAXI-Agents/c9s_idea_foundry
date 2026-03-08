"""Slack Block Kit message builders for interactive PRD flow prompts.

Each builder returns a list of Block Kit block dicts suitable for use
with ``chat.postMessage`` or ``chat.update``.  Every actionable block
encodes the ``run_id`` in the button ``value`` so the interactions
router can route decisions back to the correct flow run.

Action ID conventions (used in :mod:`interactions_router`):

    refinement_agent   – Choose agent-driven idea refinement
    refinement_manual  – Choose manual idea refinement
    idea_approve       – Approve the refined idea
    idea_cancel        – Cancel the flow after idea refinement
    requirements_approve – Approve requirements breakdown
    requirements_cancel  – Cancel the flow after requirements breakdown
    flow_cancel        – Cancel an in-progress flow at any point

    exec_summary_approve  – Approve the executive summary and continue
    exec_summary_skip     – Skip initial guidance (pre-draft prompt)
    exec_summary_continue – Continue to section drafting after exec summary
    exec_summary_stop     – Stop after exec summary (don't draft sections)

    project_select_<project_id> – Continue with an existing project
    project_create     – Create a new project
    project_switch     – Switch away from the current project
    project_continue   – Continue with the current project
    session_end        – Explicitly end the current session

    memory_configure   – Open the project memory configuration menu
    memory_idea        – Add idea & iteration guardrails
    memory_knowledge   – Add knowledge links / documents
    memory_tools       – Add implementation tools
    memory_view        – View current project memory
    memory_done        – Finish memory configuration

    idea_resume_<N>    – Resume idea #N from the list
    idea_restart_<N>   – Restart idea #N from the list
    idea_archive_<N>   – Archive idea #N from the list

    archive_idea_confirm – Confirm archiving an idea
    archive_idea_cancel  – Cancel archiving an idea

    flow_retry         – Retry / resume a paused PRD flow

    product_confluence_<N>     – Publish idea #N to Confluence
    product_jira_skeleton_<N>  – Review Jira skeleton for idea #N
    product_jira_epics_<N>     – Publish Jira epics & stories for idea #N
    product_jira_subtasks_<N>  – Publish Jira sub-tasks for idea #N
    product_view_<N>           – View delivery details for idea #N

Sub-modules
-----------
_flow_blocks         – Refinement mode, idea/requirements approval, flow status
_session_blocks      – Project selection, setup, session start/end
_memory_blocks       – Project memory configuration & viewing
_next_step_blocks    – Proactive next-step suggestion
_exec_summary_blocks – Executive summary pre-feedback & feedback
_jira_blocks         – Jira phased approval (skeleton, review)
_idea_list_blocks    – Idea listing with interactive per-idea buttons
_product_list_blocks – Product listing for delivery manager actions
_retry_blocks        – Flow-paused notification with retry button
"""

from crewai_productfeature_planner.apis.slack.blocks._flow_blocks import (
    flow_cancelled_blocks,
    flow_started_blocks,
    idea_approval_blocks,
    manual_refinement_prompt_blocks,
    refinement_mode_blocks,
    requirements_approval_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._session_blocks import (
    active_session_blocks,
    project_create_prompt_blocks,
    project_selection_blocks,
    project_setup_complete_blocks,
    project_setup_step_blocks,
    session_ended_blocks,
    session_started_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._memory_blocks import (
    memory_category_prompt_blocks,
    memory_configure_blocks,
    memory_saved_blocks,
    memory_view_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._next_step_blocks import (
    next_step_suggestion_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._exec_summary_blocks import (
    exec_summary_completion_blocks,
    exec_summary_feedback_blocks,
    exec_summary_pre_feedback_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._jira_blocks import (
    jira_review_blocks,
    jira_skeleton_approval_blocks,
    jira_subtask_review_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._idea_list_blocks import (
    _IDEA_STATUS_EMOJI,
    idea_list_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._product_list_blocks import (
    product_list_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._retry_blocks import (
    flow_paused_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._delivery_action_blocks import (
    delivery_next_step_blocks,
    jira_only_blocks,
    publish_only_blocks,
)

__all__ = [
    # Flow
    "refinement_mode_blocks",
    "idea_approval_blocks",
    "requirements_approval_blocks",
    "flow_started_blocks",
    "flow_cancelled_blocks",
    "manual_refinement_prompt_blocks",
    # Session
    "project_selection_blocks",
    "active_session_blocks",
    "project_create_prompt_blocks",
    "project_setup_step_blocks",
    "project_setup_complete_blocks",
    "session_started_blocks",
    "session_ended_blocks",
    # Memory
    "memory_configure_blocks",
    "memory_category_prompt_blocks",
    "memory_saved_blocks",
    "memory_view_blocks",
    # Next-step
    "next_step_suggestion_blocks",
    # Executive summary
    "exec_summary_completion_blocks",
    "exec_summary_pre_feedback_blocks",
    "exec_summary_feedback_blocks",
    # Jira
    "jira_skeleton_approval_blocks",
    "jira_review_blocks",
    "jira_subtask_review_blocks",
    # Idea list
    "_IDEA_STATUS_EMOJI",
    "idea_list_blocks",
    # Product list
    "product_list_blocks",
    # Retry / resume
    "flow_paused_blocks",
    # Delivery actions (post-completion)
    "delivery_next_step_blocks",
    "jira_only_blocks",
    "publish_only_blocks",
]
