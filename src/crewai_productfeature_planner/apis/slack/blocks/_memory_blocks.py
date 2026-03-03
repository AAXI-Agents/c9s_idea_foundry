"""Project-memory Block Kit builders — configure, prompt, view."""

from __future__ import annotations


def memory_configure_blocks(project_name: str, user_id: str) -> list[dict]:
    """Offer memory-configuration options for the active project.

    Shown after a session starts or when the user says
    "configure memory" / "project memory".
    """
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":brain: Project Memory — {project_name}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Project Memory stores guardrails and context that "
                    "all agents recall during every PRD run.\n\n"
                    "*Choose a category to configure:*"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"memory_menu_{user_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":bulb: Idea & Iteration"},
                    "action_id": "memory_idea",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":books: Knowledge"},
                    "action_id": "memory_knowledge",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":wrench: Tools"},
                    "action_id": "memory_tools",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":mag: View Memory"},
                    "action_id": "memory_view",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Done"},
                    "action_id": "memory_done",
                    "value": user_id,
                    "style": "primary",
                },
            ],
        },
    ]


def memory_category_prompt_blocks(
    category: str,
    category_label: str,
    help_text: str,
) -> list[dict]:
    """Prompt the user to type entries for a memory category.

    The user replies in the thread; each line becomes a separate entry.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":pencil: *Configure {category_label}*\n\n"
                    f"{help_text}\n\n"
                    "Reply in this thread with your entries — "
                    "*one per line*.  When you're finished, I'll "
                    "save them all."
                ),
            },
        },
    ]


def memory_saved_blocks(
    category_label: str,
    count: int,
) -> list[dict]:
    """Confirm that memory entries have been saved."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":white_check_mark: Saved *{count}* "
                    f"{category_label} "
                    f"{'entry' if count == 1 else 'entries'}.\n\n"
                    "Say *configure memory* to add more, or start "
                    "creating PRDs!"
                ),
            },
        },
    ]


def memory_view_blocks(
    project_name: str,
    idea_entries: list[dict],
    knowledge_entries: list[dict],
    tools_entries: list[dict],
) -> list[dict]:
    """Display all stored project memory entries."""
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":brain: Project Memory — {project_name}",
            },
        },
    ]

    def _section(label: str, emoji: str, entries: list[dict]) -> None:
        if entries:
            lines = "\n".join(
                f"• {e.get('content', '')}" for e in entries
            )
            text = f"{emoji} *{label}* ({len(entries)}):\n{lines}"
        else:
            text = f"{emoji} *{label}*: _none configured_"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        })

    _section("Idea & Iteration", ":bulb:", idea_entries)
    _section("Knowledge", ":books:", knowledge_entries)
    _section("Tools", ":wrench:", tools_entries)

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "Say *configure memory* to update.",
        }],
    })
    return blocks
