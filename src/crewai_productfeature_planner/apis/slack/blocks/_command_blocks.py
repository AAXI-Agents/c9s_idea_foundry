"""Reusable Block Kit command buttons for common bot actions.

Instead of asking users to type commands like "Say *list ideas*",
these builders produce clickable Slack buttons that fire the same
intent through the interactions router.

Action ID convention: ``cmd_<intent>``
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Individual button dicts (reusable in any actions block)
# ---------------------------------------------------------------------------

def _btn(label: str, action_id: str, *, style: str | None = None) -> dict:
    """Build a single Slack button element."""
    btn: dict = {
        "type": "button",
        "text": {"type": "plain_text", "text": label, "emoji": True},
        "action_id": action_id,
        "value": action_id,
    }
    if style:
        btn["style"] = style
    return btn


BTN_LIST_IDEAS = _btn(":bulb: List Ideas", "cmd_list_ideas")
BTN_LIST_PRODUCTS = _btn(":package: List Products", "cmd_list_products")
BTN_CONFIGURE = _btn(":gear: Configure Project", "cmd_configure_project")
BTN_CONFIGURE_MEMORY = _btn(":brain: Configure Memory", "cmd_configure_memory")
BTN_SWITCH_PROJECT = _btn(":arrows_counterclockwise: Switch Project", "cmd_switch_project")
BTN_END_SESSION = _btn(":stop_button: End Session", "cmd_end_session")
BTN_RESUME_PRD = _btn(":arrow_forward: Resume PRD", "cmd_resume_prd", style="primary")
BTN_CREATE_PROJECT = _btn(":heavy_plus_sign: Create Project", "cmd_create_project")
BTN_LIST_PROJECTS = _btn(":file_folder: List Projects", "cmd_list_projects")
BTN_HELP = _btn(":question: Help", "cmd_help")
BTN_CHECK_PUBLISH = _btn(":mag: Check Publish Status", "cmd_check_publish")
BTN_PUBLISH = _btn(":outbox_tray: Publish to Confluence", "cmd_publish", style="primary")
BTN_CREATE_JIRA = _btn(":ticket: Create Jira Tickets", "cmd_create_jira")
BTN_RESTART_PRD = _btn(":rewind: Restart PRD", "cmd_restart_prd")
BTN_CURRENT_PROJECT = _btn(":pushpin: Current Project", "cmd_current_project")
BTN_NEW_IDEA = _btn(":sparkles: New Idea", "cmd_create_prd")
BTN_ITERATE_IDEA = _btn(":repeat: Iterate Idea", "cmd_iterate_idea")
BTN_SUMMARIZE_IDEAS = _btn(":memo: Summarize Ideas", "cmd_summarize_ideas")


# ---------------------------------------------------------------------------
# Composite block builders
# ---------------------------------------------------------------------------

def help_blocks(
    user: str, has_project: bool = False, is_admin: bool = True,
) -> list[dict]:
    """Build the help response as Block Kit with clickable buttons.

    When *is_admin* is ``False`` the admin-only buttons (Configure
    Project, Configure Memory, Switch Project, Create Project) are
    hidden so non-admin channel users only see actions they can perform.
    """
    desc_lines = (
        "*Idea Iteration & PRD Generation*\n"
        "\u2022 Describe a product idea to start a PRD flow\n"
        "\u2022 List ideas, products & delivery status\n"
        "\u2022 Publish PRDs to Confluence & create Jira tickets"
    )
    if is_admin:
        desc_lines = (
            "*Project Management*\n"
            "\u2022 Create or switch projects\n"
            "\u2022 Configure project settings & memory\n\n"
            + desc_lines
        )

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<@{user}> Here's what I can do:",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": desc_lines},
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                BTN_NEW_IDEA,
                BTN_ITERATE_IDEA,
                BTN_LIST_IDEAS,
                BTN_SUMMARIZE_IDEAS,
                BTN_LIST_PRODUCTS,
            ],
        },
        {
            "type": "actions",
            "elements": [
                BTN_RESUME_PRD,
                BTN_PUBLISH,
                BTN_CREATE_JIRA,
                BTN_CHECK_PUBLISH,
                BTN_RESTART_PRD,
            ],
        },
    ]

    # Project management row — admin-only buttons conditionally included
    if is_admin:
        blocks.append({
            "type": "actions",
            "elements": [
                BTN_CREATE_PROJECT,
                BTN_LIST_PROJECTS,
                BTN_SWITCH_PROJECT,
                BTN_CURRENT_PROJECT,
            ],
        })
        blocks.append({
            "type": "actions",
            "elements": [
                BTN_CONFIGURE,
                BTN_CONFIGURE_MEMORY,
                BTN_END_SESSION,
            ],
        })
    else:
        blocks.append({
            "type": "actions",
            "elements": [
                BTN_LIST_PROJECTS,
                BTN_CURRENT_PROJECT,
                BTN_END_SESSION,
            ],
        })

    if not has_project:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": ":point_right: *To get started, select a project first.*",
            }],
        })
    return blocks


def session_action_buttons() -> list[dict]:
    """Buttons for session management (switch / end)."""
    return [
        {
            "type": "actions",
            "elements": [
                BTN_SWITCH_PROJECT,
                BTN_END_SESSION,
            ],
        },
    ]


def resume_prd_button() -> dict:
    """Single 'Resume PRD' button element for inline use."""
    return BTN_RESUME_PRD


def post_memory_saved_buttons() -> list[dict]:
    """Action buttons after memory entries are saved."""
    return [
        {
            "type": "actions",
            "elements": [
                BTN_CONFIGURE_MEMORY,
                BTN_LIST_IDEAS,
            ],
        },
    ]


def post_memory_view_buttons() -> list[dict]:
    """Action buttons below the memory view."""
    return [
        {
            "type": "actions",
            "elements": [
                BTN_CONFIGURE_MEMORY,
            ],
        },
    ]


def no_products_buttons() -> list[dict]:
    """Action buttons when no completed products are found."""
    return [
        {
            "type": "actions",
            "elements": [
                BTN_LIST_IDEAS,
            ],
        },
    ]


def product_list_footer_buttons() -> list[dict]:
    """Action buttons at the bottom of the product list."""
    return [
        {
            "type": "actions",
            "elements": [
                BTN_LIST_IDEAS,
            ],
        },
    ]


def missing_keys_buttons() -> list[dict]:
    """Action buttons when Confluence/Jira keys are not configured."""
    return [
        {
            "type": "actions",
            "elements": [
                BTN_CONFIGURE,
            ],
        },
    ]


def check_publish_buttons() -> list[dict]:
    """Action buttons suggesting publish status check."""
    return [
        {
            "type": "actions",
            "elements": [
                BTN_CHECK_PUBLISH,
            ],
        },
    ]


def restart_cancelled_buttons() -> list[dict]:
    """Action buttons after a restart is cancelled."""
    return [
        {
            "type": "actions",
            "elements": [
                BTN_RESUME_PRD,
            ],
        },
    ]
