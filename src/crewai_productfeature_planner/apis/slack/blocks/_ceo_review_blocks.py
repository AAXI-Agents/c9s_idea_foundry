"""CEO review (Executive Product Summary) Block Kit builders."""

from __future__ import annotations

from crewai_productfeature_planner.apis.slack._slack_file_helper import (
    truncate_with_file_hint,
)


def ceo_review_blocks(
    run_id: str,
    content: str,
) -> tuple[list[dict], bool]:
    """Show the Executive Product Summary and ask for approval.

    Returns ``(blocks, was_truncated)``.  When *was_truncated* is True
    the caller should upload the full content as a file attachment.
    """
    content_preview, was_truncated = truncate_with_file_hint(content, 2700)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "\u2b50 Executive Product Summary — CEO Review",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "The *CEO Reviewer* has generated a 10-star vision "
                    "for this product.\n\n"
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
                    "Review the Executive Product Summary above.\n\n"
                    ":white_check_mark: *Approve* \u2014 accept as-is and "
                    "continue to Engineering Plan\n"
                    ":pencil2: *Edit* \u2014 approve with modifications "
                    "(opens a dialog)\n"
                    ":no_entry_sign: *Skip* \u2014 skip the EPS and use "
                    "only the executive summary"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"ceo_review_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":white_check_mark: Approve",
                    },
                    "style": "primary",
                    "action_id": "ceo_review_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":no_entry_sign: Skip",
                    },
                    "style": "danger",
                    "action_id": "ceo_review_reject",
                    "value": run_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": (
                    "_This vision statement guides the Engineering Plan "
                    "and section drafting. Click Approve to continue._"
                ),
            }],
        },
    ]

    return blocks, was_truncated
