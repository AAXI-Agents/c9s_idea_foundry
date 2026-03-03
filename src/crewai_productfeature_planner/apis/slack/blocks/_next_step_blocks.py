"""Next-step suggestion Block Kit builder."""

from __future__ import annotations

# Emoji mapping for next-step categories
_NEXT_STEP_EMOJI = {
    "configure_confluence": ":confluence:",
    "configure_jira": ":jira2:",
    "configure_memory": ":brain:",
    "configure_missing_keys": ":key:",
    "create_prd": ":rocket:",
    "publish": ":outbox_tray:",
    "review_prd": ":mag:",
}


def next_step_suggestion_blocks(
    next_step: str,
    message: str,
    user_id: str,
    interaction_id: str | None = None,
) -> list[dict]:
    """Build a proactive next-step suggestion block.

    Shown after key actions (project selection, PRD completion, etc.)
    to guide the user toward the most useful next action.

    The ``interaction_id`` is encoded in the button values so the
    feedback loop can update the correct ``agentInteraction`` document.
    """
    emoji = _NEXT_STEP_EMOJI.get(next_step, ":bulb:")
    # Encode interaction_id in button value for feedback tracking
    accept_value = f"{next_step}|{interaction_id or ''}"
    dismiss_value = f"dismiss|{interaction_id or ''}"

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *Suggested next step:*\n"
                    f"{message}"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"next_step_{user_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":white_check_mark: Let's do it",
                    },
                    "style": "primary",
                    "action_id": "next_step_accept",
                    "value": accept_value,
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":x: Not now",
                    },
                    "action_id": "next_step_dismiss",
                    "value": dismiss_value,
                },
            ],
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": "_This suggestion is based on your project's current state._",
            }],
        },
    ]
