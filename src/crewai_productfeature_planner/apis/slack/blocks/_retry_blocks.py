"""Flow-paused / retry Block Kit builders.

Shown when a PRD flow pauses due to an error (LLM / billing / internal)
or a user-initiated pause.  Presents a *Retry* button that triggers
``handle_resume_prd`` for the same run.
"""

from __future__ import annotations


def flow_paused_blocks(
    run_id: str,
    reason: str = "",
    *,
    show_retry: bool = True,
) -> list[dict]:
    """Build blocks for a paused-flow notification with an optional Retry button.

    Parameters
    ----------
    run_id:
        The ``run_id`` of the paused flow.
    reason:
        A short human-readable reason for the pause (e.g.
        ``"LLM error: Invalid response"``).  Shown in the message body.
    show_retry:
        When *True* (default) a retry button is included.
    """
    reason_text = f"\n> {reason}" if reason else ""

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":pause_button: *PRD flow paused* (`{run_id}`)"
                    f"{reason_text}"
                ),
            },
        },
    ]

    if show_retry:
        blocks.append(
            {
                "type": "actions",
                "block_id": f"flow_paused_{run_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":arrows_counterclockwise: Retry",
                        },
                        "style": "primary",
                        "action_id": "flow_retry",
                        "value": run_id,
                    },
                ],
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "_Click Retry to resume from where it stopped, "
                        "or say *resume prd flow*._"
                    ),
                },
            ],
        }
    )

    return blocks
