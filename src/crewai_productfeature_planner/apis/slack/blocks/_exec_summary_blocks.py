"""Executive-summary feedback Block Kit builders."""

from __future__ import annotations

from crewai_productfeature_planner.apis.slack._slack_file_helper import (
    truncate_with_file_hint,
)


def exec_summary_completion_blocks(
    run_id: str,
    content: str,
    total_iterations: int,
) -> tuple[list[dict], bool]:
    """Show the finalized executive summary and ask for approval to continue.

    Returns ``(blocks, was_truncated)``.  When *was_truncated* is True the
    caller should upload the full content as a file attachment.
    """
    # Leave room for the prefix text that wraps content_preview (~100 chars).
    content_preview, was_truncated = truncate_with_file_hint(content, 2700)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":white_check_mark: Executive Summary — Finalized",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"The executive summary was refined over "
                    f"*{total_iterations}* iteration(s) and is ready for "
                    "review.\n\n"
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
                    "Would you like to proceed to *section-level PRD drafting*?\n\n"
                    ":arrow_forward: *Continue* — start drafting individual "
                    "PRD sections\n"
                    ":no_entry_sign: *Stop* — finish here with only the "
                    "executive summary"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"exec_summary_complete_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":arrow_forward: Continue to Sections",
                    },
                    "style": "primary",
                    "action_id": "exec_summary_continue",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":no_entry_sign: Stop"},
                    "style": "danger",
                    "action_id": "exec_summary_stop",
                    "value": run_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": (
                    "_Click Continue to start section drafting, or Stop to "
                    "finish with only the executive summary._"
                ),
            }],
        },
    ]

    return blocks, was_truncated


def exec_summary_pre_feedback_blocks(run_id: str, idea: str) -> list[dict]:
    """Ask the user if they want to provide initial guidance before the exec summary draft.

    Shown before the first executive summary iteration runs.
    """
    idea_preview = idea[:300] + ("…" if len(idea) > 300 else "")
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":memo: Executive Summary — Initial Guidance",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Idea:*\n> _{idea_preview}_\n\n"
                    "Before the AI drafts the executive summary, would you "
                    "like to provide any initial guidance or focus areas?\n\n"
                    "Reply in this thread with your guidance, or click "
                    "*Skip* to let the AI draft freely."
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"exec_summary_pre_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":fast_forward: Skip"},
                    "action_id": "exec_summary_skip",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x: Cancel"},
                    "style": "danger",
                    "action_id": "flow_cancel",
                    "value": run_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": "_Reply in this thread with guidance, or click Skip._",
            }],
        },
    ]


def exec_summary_feedback_blocks(
    run_id: str,
    content: str,
    iteration: int,
) -> tuple[list[dict], bool]:
    """Show the current executive summary and ask for feedback.

    Returns ``(blocks, was_truncated)``.  When *was_truncated* is True the
    caller should upload the full content as a file attachment.
    """
    content_preview, was_truncated = truncate_with_file_hint(content)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":page_facing_up: Executive Summary — Iteration {iteration}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": content_preview,
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Are you satisfied with this executive summary?\n\n"
                    ":white_check_mark: *Approve* — accept and continue "
                    "to section drafting\n"
                    ":speech_balloon: *Reply in thread* — provide feedback "
                    "for another iteration"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"exec_summary_feedback_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":white_check_mark: Approve",
                    },
                    "style": "primary",
                    "action_id": "exec_summary_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x: Cancel"},
                    "style": "danger",
                    "action_id": "flow_cancel",
                    "value": run_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": (
                    "_Reply in this thread with your feedback to trigger "
                    "another iteration, or click Approve._"
                ),
            }],
        },
    ]

    return blocks, was_truncated
