"""Post-completion delivery action Block Kit builders.

Provides action buttons for "Publish to Confluence" and
"Create Jira Skeleton" that replace the old text-based prompts
("Say *publish*" / "Say *create jira tickets*").
"""

from __future__ import annotations


def delivery_next_step_blocks(
    run_id: str,
    *,
    show_publish: bool = True,
    show_jira: bool = True,
) -> list[dict]:
    """Build Block Kit blocks with delivery action buttons.

    Args:
        run_id: The PRD run identifier (encoded in button values).
        show_publish: Include the "Publish to Confluence" button.
        show_jira: Include the "Create Jira Skeleton" button.

    Returns:
        A list of Block Kit block dicts.  Empty when neither action
        is applicable.
    """
    if not show_publish and not show_jira:
        return []

    elements: list[dict] = []

    if show_publish:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": ":outbox_tray:  Publish to Confluence"},
            "style": "primary",
            "action_id": "delivery_publish",
            "value": run_id,
        })

    if show_jira:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": ":jira:  Create Jira Skeleton"},
            "action_id": "delivery_create_jira",
            "value": run_id,
        })

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":bulb: *Next steps:*",
            },
        },
        {
            "type": "actions",
            "block_id": f"delivery_actions_{run_id}",
            "elements": elements,
        },
    ]


def jira_only_blocks(run_id: str) -> list[dict]:
    """Convenience: build blocks with only the Create Jira button."""
    return delivery_next_step_blocks(run_id, show_publish=False, show_jira=True)


def publish_only_blocks(run_id: str) -> list[dict]:
    """Convenience: build blocks with only the Publish button."""
    return delivery_next_step_blocks(run_id, show_publish=True, show_jira=False)
