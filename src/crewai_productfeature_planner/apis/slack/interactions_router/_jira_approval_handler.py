"""Handler for Jira phased-approval button clicks from product list.

Handles the approval/rejection buttons that appear after skeleton
generation, Epics & Stories creation, and Sub-task creation:

* ``jira_skeleton_approve``  — Approve skeleton → create Epics & Stories
* ``jira_skeleton_reject``   — Regenerate a new skeleton version
* ``jira_review_approve``    — Approve Epics & Stories → create sub-tasks
* ``jira_review_skip``       — Skip sub-tasks (mark Jira as complete with E&S only)
* ``jira_subtask_approve``   — Approve sub-tasks → finalise Jira ticketing
* ``jira_subtask_reject``    — Regenerate sub-tasks
"""

from __future__ import annotations

import logging
import threading

from crewai_productfeature_planner.orchestrator._jira import _persist_jira_phase
from crewai_productfeature_planner.tools.slack_tools import (
    SlackSendMessageTool,
    _get_slack_client,
)

logger = logging.getLogger(__name__)


def _handle_jira_approval_action(
    action_id: str,
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a Jira approval/rejection button click.

    The ``value`` on these buttons is just the ``run_id``.
    """
    send_tool = SlackSendMessageTool()
    client = _get_slack_client()

    if action_id == "jira_skeleton_approve":
        _handle_skeleton_approve(run_id, user_id, channel, thread_ts, send_tool, client)
    elif action_id == "jira_skeleton_reject":
        _handle_skeleton_reject(run_id, user_id, channel, thread_ts, send_tool, client)
    elif action_id == "jira_review_approve":
        _handle_review_approve(run_id, user_id, channel, thread_ts, send_tool, client)
    elif action_id == "jira_review_skip":
        _handle_review_skip(run_id, user_id, channel, thread_ts, send_tool, client)
    elif action_id == "jira_subtask_approve":
        _handle_subtask_approve(run_id, user_id, channel, thread_ts, send_tool, client)
    elif action_id == "jira_subtask_reject":
        _handle_subtask_reject(run_id, user_id, channel, thread_ts, send_tool, client)
    else:
        logger.warning("Unknown Jira approval action: %s", action_id)


# ---------------------------------------------------------------------------
# Skeleton approve / reject
# ---------------------------------------------------------------------------


def _handle_skeleton_approve(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Approve the Jira skeleton → immediately create Epics & Stories.

    Persists ``skeleton_approved`` phase and launches the Epics & Stories
    stage in a background thread.
    """
    _persist_jira_phase(run_id, "skeleton_approved")

    send_tool.run(
        channel=channel,
        thread_ts=thread_ts,
        text=(
            f"<@{user_id}> :white_check_mark: Jira skeleton approved! "
            "Creating Epics & User Stories now…"
        ),
    )
    logger.info("[JiraApproval] Skeleton approved for run_id=%s — creating Epics & Stories", run_id)

    def _do_epics():
        try:
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _run_jira_phase,
            )
            _run_jira_phase(
                run_id, "epics_stories", user_id, channel, thread_ts, send_tool,
            )
        except Exception as exc:
            logger.error("Epics & Stories creation failed for run_id=%s: %s", run_id, exc)
            send_tool.run(
                channel=channel,
                thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Epics & Stories creation failed: {exc}",
            )

    threading.Thread(target=_do_epics, daemon=True).start()


def _handle_skeleton_reject(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Reject the current skeleton → regenerate a new version.

    Resets ``jira_phase`` to empty and re-runs the skeleton stage so the
    user gets a fresh skeleton to review.
    """
    _persist_jira_phase(run_id, "")

    send_tool.run(
        channel=channel,
        thread_ts=thread_ts,
        text=(
            f"<@{user_id}> :arrows_counterclockwise: Regenerating Jira skeleton…"
        ),
    )
    logger.info("[JiraApproval] Skeleton rejected for run_id=%s — regenerating", run_id)

    def _do_regenerate():
        try:
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _run_jira_phase,
            )
            _run_jira_phase(
                run_id, "skeleton", user_id, channel, thread_ts, send_tool,
            )
        except Exception as exc:
            logger.error("Skeleton regeneration failed for run_id=%s: %s", run_id, exc)
            send_tool.run(
                channel=channel,
                thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Skeleton regeneration failed: {exc}",
            )

    threading.Thread(target=_do_regenerate, daemon=True).start()


# ---------------------------------------------------------------------------
# Epics & Stories review approve / skip
# ---------------------------------------------------------------------------


def _handle_review_approve(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Approve Epics & Stories → create sub-tasks in background."""
    send_tool.run(
        channel=channel,
        thread_ts=thread_ts,
        text=(
            f"<@{user_id}> :white_check_mark: Epics & Stories approved! "
            "Creating sub-tasks now…"
        ),
    )

    def _do_subtasks():
        try:
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _run_jira_phase,
            )
            _run_jira_phase(
                run_id, "subtasks", user_id, channel, thread_ts, send_tool,
            )
        except Exception as exc:
            logger.error("Sub-task creation failed for run_id=%s: %s", run_id, exc)
            send_tool.run(
                channel=channel,
                thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Sub-task creation failed: {exc}",
            )

    threading.Thread(target=_do_subtasks, daemon=True).start()
    logger.info("[JiraApproval] Review approved for run_id=%s — creating sub-tasks", run_id)


def _handle_review_skip(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Skip sub-task creation — mark Jira as complete with Epics & Stories only."""
    from crewai_productfeature_planner.mongodb.product_requirements import (
        upsert_delivery_record,
    )

    _persist_jira_phase(run_id, "subtasks_done")
    upsert_delivery_record(run_id, jira_completed=True)

    send_tool.run(
        channel=channel,
        thread_ts=thread_ts,
        text=(
            f"<@{user_id}> :white_check_mark: Jira ticketing marked complete "
            "(Epics & Stories only, no sub-tasks).\n"
            "You can view details from the product list."
        ),
    )
    logger.info("[JiraApproval] Sub-tasks skipped for run_id=%s — marked complete", run_id)


# ---------------------------------------------------------------------------
# Sub-task review approve / reject
# ---------------------------------------------------------------------------


def _handle_subtask_approve(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Approve sub-tasks → finalise Jira ticketing.

    Persists ``subtasks_done`` phase and marks Jira as complete.
    """
    from crewai_productfeature_planner.mongodb.product_requirements import (
        upsert_delivery_record,
    )

    _persist_jira_phase(run_id, "subtasks_done")
    upsert_delivery_record(run_id, jira_completed=True)

    send_tool.run(
        channel=channel,
        thread_ts=thread_ts,
        text=(
            f"<@{user_id}> :white_check_mark: Jira Sub-tasks approved! "
            "All Jira phases are now complete."
        ),
    )
    logger.info("[JiraApproval] Sub-tasks approved for run_id=%s — marked complete", run_id)


def _handle_subtask_reject(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Reject sub-tasks → regenerate with a fresh attempt.

    Resets ``jira_phase`` to ``epics_stories_done`` and re-runs the
    sub-task stage so the user gets fresh sub-tasks to review.
    """
    _persist_jira_phase(run_id, "epics_stories_done")

    send_tool.run(
        channel=channel,
        thread_ts=thread_ts,
        text=(
            f"<@{user_id}> :arrows_counterclockwise: Regenerating Jira Sub-tasks…"
        ),
    )
    logger.info("[JiraApproval] Sub-tasks rejected for run_id=%s — regenerating", run_id)

    def _do_regenerate_subtasks():
        try:
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _run_jira_phase,
            )
            _run_jira_phase(
                run_id, "subtasks", user_id, channel, thread_ts, send_tool,
            )
        except Exception as exc:
            logger.error("Sub-task regeneration failed for run_id=%s: %s", run_id, exc)
            send_tool.run(
                channel=channel,
                thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Sub-task regeneration failed: {exc}",
            )

    threading.Thread(target=_do_regenerate_subtasks, daemon=True).start()
