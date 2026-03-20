"""interactive_handlers — Slack interactive flow state & callbacks.

This package was refactored from a single 942-line module into focused
sub-modules.  All public names are re-exported here for backward
compatibility.
"""

# -- run state ---------------------------------------------------------------
from crewai_productfeature_planner.apis.slack.interactive_handlers._run_state import (
    _expire_stale,
    _INTERACTIVE_TTL_SECONDS,
    _interactive_runs,
    _lock,
    _manual_refinement_text,
    _queued_feedback,
    cleanup_interactive_run,
    drain_queued_feedback,
    get_interactive_run,
    queue_feedback,
    register_interactive_run,
)

# -- decisions ---------------------------------------------------------------
from crewai_productfeature_planner.apis.slack.interactive_handlers._decisions import (
    is_manual_refinement_active,
    resolve_interaction,
    submit_manual_refinement,
)

# -- slack helpers -----------------------------------------------------------
from crewai_productfeature_planner.apis.slack.interactive_handlers._slack_helpers import (
    _post_blocks,
    _post_text,
    _wait_for_decision,
)

# -- callbacks ---------------------------------------------------------------
from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
    make_slack_exec_summary_completion_callback,
    make_slack_exec_summary_feedback_callback,
    make_slack_idea_callback,
    make_slack_jira_review_callback,
    make_slack_jira_skeleton_callback,
    make_slack_requirements_callback,
    run_manual_refinement,
    wait_for_refinement_mode,
)

# -- flow runner -------------------------------------------------------------
from crewai_productfeature_planner.apis.slack.interactive_handlers._flow_runner import (
    run_interactive_slack_flow,
)

__all__ = [
    # run state
    "_lock",
    "_interactive_runs",
    "_manual_refinement_text",
    "_queued_feedback",
    "_INTERACTIVE_TTL_SECONDS",
    "_expire_stale",
    "register_interactive_run",
    "get_interactive_run",
    "cleanup_interactive_run",
    "queue_feedback",
    "drain_queued_feedback",
    # decisions
    "resolve_interaction",
    "submit_manual_refinement",
    "is_manual_refinement_active",
    # slack helpers
    "_post_blocks",
    "_post_text",
    "_wait_for_decision",
    # callbacks
    "wait_for_refinement_mode",
    "run_manual_refinement",
    "make_slack_idea_callback",
    "make_slack_requirements_callback",
    "make_slack_exec_summary_feedback_callback",
    "make_slack_exec_summary_completion_callback",
    "make_slack_jira_skeleton_callback",
    "make_slack_jira_review_callback",
    # flow runner
    "run_interactive_slack_flow",
]
