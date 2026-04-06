"""Block Kit builder for the persistent flow control panel."""

from __future__ import annotations


def flow_control_panel_blocks(run_id: str) -> list[dict]:
    """Build a persistent control panel with [Pause Flow] and [Cancel] buttons.

    Posted once when the PRD flow starts.  The user can click either
    button at any time; the flow checks the corresponding signal
    between phases.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":control_knobs: *Flow Control Panel*",
            },
        },
        {
            "type": "actions",
            "block_id": f"flow_control_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":double_vertical_bar: Pause Flow"},
                    "action_id": "flow_pause",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":no_entry_sign: Cancel"},
                    "style": "danger",
                    "action_id": "flow_cancel",
                    "value": run_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_Pause saves progress and stops. Cancel aborts the entire flow._",
                },
            ],
        },
    ]
