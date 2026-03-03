"""Executive-summary feedback Block Kit builders."""

from __future__ import annotations


def exec_summary_completion_blocks(
    run_id: str,
    content: str,
    total_iterations: int,
) -> list[dict]:
    """Show the finalized executive summary and ask for approval to continue.

    Displayed after all executive-summary iterations complete (either
    READY_FOR_DEV or max iterations reached) to give the user a final
    review gate before proceeding to section-level PRD drafting.
    """
    # Slack has a 3000-char limit per text block
    if len(content) > 2800:
        content_preview = content[:2800] + f"\n\n_… ({len(content) - 2800} more chars)_"
    else:
        content_preview = content

    return [
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
) -> list[dict]:
    """Show the current executive summary and ask for feedback.

    Shown after each executive summary iteration completes.
    """
    # Slack has a 3000-char limit per text block
    if len(content) > 2800:
        content_preview = content[:2800] + f"\n\n_… ({len(content) - 2800} more chars)_"
    else:
        content_preview = content

    return [
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
