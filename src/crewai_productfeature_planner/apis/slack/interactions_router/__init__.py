"""Slack Interactions API router.

Handles inbound interactive payloads from Slack — button clicks, menu
selections, and modal submissions.  This is the ``Request URL`` configured
under *Interactivity & Shortcuts* in the Slack app settings.

Sub-modules
-----------
_dispatch            – Router, endpoint, constants, helpers
_project_handler     – Project-session button handler
_memory_handler      – Memory-configuration button handler
_next_step_handler   – Next-step suggestion feedback handler
_restart_handler     – Restart PRD confirmation handler
_archive_handler     – Archive idea confirmation handler
_idea_list_handler   – Idea list resume/restart/archive handler
_jira_approval_handler – Jira skeleton/review approval handler
"""

from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
    _ARCHIVE_ACTIONS,
    _JIRA_APPROVAL_ACTIONS,
    _KNOWN_ACTIONS,
    _MEMORY_ACTIONS,
    _NEXT_STEP_ACTIONS,
    _RESTART_PRD_ACTIONS,
    _SESSION_ACTIONS,
    _ack_action,
    _extract_payload,
    _post_ack,
    _with_team,
    router,
    slack_interactions,
)
from crewai_productfeature_planner.apis.slack.interactions_router._archive_handler import (
    _handle_archive_action,
)
from crewai_productfeature_planner.apis.slack.interactions_router._idea_list_handler import (
    _handle_idea_list_action,
)
from crewai_productfeature_planner.apis.slack.interactions_router._memory_handler import (
    _handle_memory_action,
)
from crewai_productfeature_planner.apis.slack.interactions_router._next_step_handler import (
    _handle_next_step_feedback,
)
from crewai_productfeature_planner.apis.slack.interactions_router._project_handler import (
    _handle_project_action,
)
from crewai_productfeature_planner.apis.slack.interactions_router._restart_handler import (
    _handle_restart_prd_action,
)
from crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler import (
    _handle_jira_approval_action,
)

__all__ = [
    # Core
    "router",
    "slack_interactions",
    "_KNOWN_ACTIONS",
    "_SESSION_ACTIONS",
    "_MEMORY_ACTIONS",
    "_NEXT_STEP_ACTIONS",
    "_RESTART_PRD_ACTIONS",
    "_ARCHIVE_ACTIONS",
    "_JIRA_APPROVAL_ACTIONS",
    "_extract_payload",
    "_with_team",
    "_ack_action",
    "_post_ack",
    # Handlers
    "_handle_project_action",
    "_handle_memory_action",
    "_handle_next_step_feedback",
    "_handle_restart_prd_action",
    "_handle_archive_action",
    "_handle_idea_list_action",
    "_handle_jira_approval_action",
]
