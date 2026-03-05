"""Jira phased-approval Block Kit builders."""

from __future__ import annotations


def jira_skeleton_approval_blocks(
    run_id: str,
    skeleton: str,
) -> list[dict]:
    """Show the Jira skeleton (Epics & Stories titles) for user approval.

    The user can approve to proceed with ticket creation, or reject
    to regenerate a new version of the skeleton.
    """
    if len(skeleton) > 2800:
        skeleton_preview = skeleton[:2800] + f"\n\n_… ({len(skeleton) - 2800} more chars)_"
    else:
        skeleton_preview = skeleton

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":clipboard: Jira Ticket Skeleton Ready",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "Review the proposed Epics and Stories below. "
                        "Approve to create the tickets in Jira."
                    ),
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": skeleton_preview},
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": f"jira_skeleton_approval_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Approve"},
                    "style": "primary",
                    "action_id": "jira_skeleton_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":arrows_counterclockwise: Regenerate"},
                    "style": "danger",
                    "action_id": "jira_skeleton_reject",
                    "value": run_id,
                },
            ],
        },
    ]


def jira_review_blocks(
    run_id: str,
    epics_stories_output: str,
) -> list[dict]:
    """Show created Epics & Stories for user review before sub-tasks.

    The user can proceed to create sub-tasks or skip them.
    """
    if len(epics_stories_output) > 2800:
        preview = (
            epics_stories_output[:2800]
            + f"\n\n_… ({len(epics_stories_output) - 2800} more chars)_"
        )
    else:
        preview = epics_stories_output

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":white_check_mark: Jira Epics & Stories Created",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "Review the Epics and Stories above. "
                        "Approve to create detailed sub-tasks, or skip."
                    ),
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": preview},
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": f"jira_review_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":gear: Create Sub-Tasks"},
                    "style": "primary",
                    "action_id": "jira_review_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":stop_sign: Skip Sub-Tasks"},
                    "action_id": "jira_review_skip",
                    "value": run_id,
                },
            ],
        },
    ]


def jira_subtask_review_blocks(
    run_id: str,
    subtasks_output: str,
) -> list[dict]:
    """Show created Sub-tasks for user review before marking complete.

    The user can approve to finalise Jira ticketing, or reject to
    regenerate sub-tasks with a fresh attempt.
    """
    if len(subtasks_output) > 2800:
        preview = (
            subtasks_output[:2800]
            + f"\n\n_… ({len(subtasks_output) - 2800} more chars)_"
        )
    else:
        preview = subtasks_output

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":hammer_and_wrench: Jira Sub-Tasks Created",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "Review the sub-tasks below. "
                        "Approve to finalise Jira ticketing, or regenerate."
                    ),
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": preview},
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": f"jira_subtask_review_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Approve Sub-Tasks"},
                    "style": "primary",
                    "action_id": "jira_subtask_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":arrows_counterclockwise: Regenerate"},
                    "style": "danger",
                    "action_id": "jira_subtask_reject",
                    "value": run_id,
                },
            ],
        },
    ]
