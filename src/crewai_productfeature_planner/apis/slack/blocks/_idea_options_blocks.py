"""Block Kit builder for presenting 3 alternative idea directions.

Used during idea refinement when a trigger condition is met (after 3
auto cycles, low confidence, or direction change).
"""

from __future__ import annotations


def idea_options_blocks(
    options: list[str],
    run_id: str,
    iteration: int,
    trigger: str,
) -> list[dict]:
    """Build Block Kit blocks presenting 3 alternative directions.

    Args:
        options: List of 3 option descriptions.
        run_id: The flow run identifier (encoded in button values).
        iteration: Current refinement iteration.
        trigger: Trigger reason (``auto_cycles_complete``,
            ``low_confidence``, ``direction_change``).

    Returns:
        List of Block Kit block dicts.
    """
    trigger_labels = {
        "auto_cycles_complete": "Auto-refinement complete",
        "low_confidence": "Confidence dropped — consider a new direction",
        "direction_change": "Significant direction change detected",
    }
    header = trigger_labels.get(trigger, "Decision point reached")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":compass: {header}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"After *{iteration}* refinement cycles, here are 3 "
                    "alternative directions. Choose one to continue refining:"
                ),
            },
        },
    ]

    for idx, option_text in enumerate(options[:3]):
        # Truncate long options for Block Kit limits (3000 chars)
        display = option_text[:2900] if len(option_text) > 2900 else option_text
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Option {idx + 1}*\n{display}",
            },
        })

    # Action buttons
    buttons = []
    for idx in range(min(3, len(options))):
        btn: dict = {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": f"Option {idx + 1}",
                "emoji": True,
            },
            "action_id": f"idea_option_{idx + 1}",
            "value": run_id,
        }
        if idx == 0:
            btn["style"] = "primary"
        buttons.append(btn)

    blocks.append({"type": "actions", "elements": buttons})
    return blocks
