"""Idea-list Block Kit builder with interactive per-idea buttons."""

from __future__ import annotations

_IDEA_STATUS_EMOJI: dict[str, str] = {
    "inprogress": ":arrows_counterclockwise:",
    "paused": ":double_vertical_bar:",
    "completed": ":white_check_mark:",
    "failed": ":warning:",
}


def idea_list_blocks(
    ideas: list[dict],
    user: str,
    project_name: str,
    project_id: str,
) -> list[dict]:
    """Build Block Kit blocks for listing ideas with action buttons.

    Each idea gets a *Resume* and/or *Restart* button so the user can
    act on it with a single click instead of typing a command.  The
    button ``value`` carries ``<project_id>|<idea_number>`` so the
    interactions router can resolve the idea.

    Action IDs follow the pattern ``idea_resume_<N>``,
    ``idea_restart_<N>``, and ``idea_archive_<N>`` where *N* is the
    1-based index.
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":page_facing_up: Ideas for {project_name}",
            },
        },
    ]

    for idx, idea_doc in enumerate(ideas, 1):
        idea_text = idea_doc.get("idea") or "Untitled"
        if len(idea_text) > 120:
            idea_text = idea_text[:117] + "\u2026"
        status = idea_doc.get("status", "unknown")
        emoji = _IDEA_STATUS_EMOJI.get(status, ":question:")
        sections_done = idea_doc.get("sections_done", 0)
        total_sections = idea_doc.get("total_sections", 12)
        iteration = idea_doc.get("iteration", 0)

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{idx}.* {emoji} _{idea_text}_\n"
                        f"Status: *{status}* \u00b7 Iteration: {iteration} \u00b7 "
                        f"Sections: {sections_done}/{total_sections}"
                    ),
                },
            }
        )

        # Build action buttons — Resume, Rescan, and Archive
        btn_value = f"{project_id}|{idx}"
        blocks.append(
            {
                "type": "actions",
                "block_id": f"idea_actions_{project_id}_{idx}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": f":arrow_forward: Resume #{idx}"},
                        "action_id": f"idea_resume_{idx}",
                        "value": btn_value,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": f":arrows_counterclockwise: Rescan #{idx}"},
                        "action_id": f"idea_restart_{idx}",
                        "value": btn_value,
                        "style": "danger",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": f":file_folder: Archive #{idx}"},
                        "action_id": f"idea_archive_{idx}",
                        "value": btn_value,
                    },
                ],
            }
        )

        blocks.append({"type": "divider"})

    # Footer hint
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Or just describe a new idea to start fresh!",
                }
            ],
        }
    )

    return blocks
