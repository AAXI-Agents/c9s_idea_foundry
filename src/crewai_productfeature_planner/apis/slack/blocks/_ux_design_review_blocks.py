"""UX Design Review (Senior Designer findings) Block Kit builders."""

from __future__ import annotations

from crewai_productfeature_planner.apis.slack._slack_file_helper import (
    truncate_with_file_hint,
)


def ux_design_review_blocks(
    run_id: str,
    content: str,
) -> tuple[list[dict], bool]:
    """Show the finalized UX Design and ask for approval.

    Presents the Senior Designer's 7-pass review output for user
    review before appending to the final PRD.

    Returns ``(blocks, was_truncated)``.  When *was_truncated* is True
    the caller should upload the full content as a file attachment.
    """
    content_preview, was_truncated = truncate_with_file_hint(content, 2700)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "\U0001f3a8 UX Design Review — Summary",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "The *Senior Designer* has completed a 7-pass review "
                    "of the UX specification.\n\n"
                    f"{content_preview}"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Review the UX Design above.\n\n"
                    ":white_check_mark: *Approve* \u2014 accept and "
                    "append to the final PRD\n"
                    ":no_entry_sign: *Skip* \u2014 skip UX Design "
                    "(will not be included in the PRD)"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"ux_design_review_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":white_check_mark: Approve",
                    },
                    "style": "primary",
                    "action_id": "ux_design_review_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":no_entry_sign: Skip",
                    },
                    "style": "danger",
                    "action_id": "ux_design_review_reject",
                    "value": run_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": (
                    "_This UX specification will be appended to the PRD "
                    "and saved as a standalone design document. "
                    "Click Approve to continue._"
                ),
            }],
        },
    ]

    return blocks, was_truncated
