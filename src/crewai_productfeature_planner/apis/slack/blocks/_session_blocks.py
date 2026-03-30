"""Project-session Block Kit builders — selection, setup, status."""

from __future__ import annotations


def project_selection_blocks(
    projects: list[dict],
    user_id: str,
) -> list[dict]:
    """Prompt the user to select an existing project or create a new one.

    *projects* is a list of project-config dicts (from
    ``list_projects()``).  Up to 5 are shown as buttons; the rest are
    mentioned in a context line.
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":file_folder: Select a Project",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Which project would you like to work on?\n"
                    "Choose an existing project or create a new one."
                ),
            },
        },
        {"type": "divider"},
    ]

    # Show up to 5 project buttons
    buttons: list[dict] = []
    shown = projects[:5]
    for proj in shown:
        pid = proj.get("project_id", "")
        pname = proj.get("name", "Unnamed")
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": f":bookmark: {pname}"[:75]},
            "action_id": f"project_select_{pid}",
            "value": pid,
        })

    # Always offer "Create New"
    buttons.append({
        "type": "button",
        "text": {"type": "plain_text", "text": ":heavy_plus_sign: Create New Project"},
        "style": "primary",
        "action_id": "project_create",
        "value": user_id,
    })

    blocks.append({
        "type": "actions",
        "block_id": f"project_select_{user_id}",
        "elements": buttons,
    })

    if len(projects) > 5:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"_Showing first 5 of {len(projects)} projects._",
            }],
        })

    return blocks


def active_session_blocks(
    project_name: str,
    project_id: str,
    user_id: str,
) -> list[dict]:
    """Remind the user of their active project session.

    Offers to continue with the current project or switch to a
    different one.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":file_folder: You're currently working on "
                    f"*{project_name}*.\n\n"
                    "Continue with this project or switch to a different one."
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"session_status_{user_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":arrow_forward: Continue"},
                    "style": "primary",
                    "action_id": "project_continue",
                    "value": project_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":twisted_rightwards_arrows: Switch Project"},
                    "action_id": "project_switch",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":stop_button: End Session"},
                    "style": "danger",
                    "action_id": "session_end",
                    "value": user_id,
                },
            ],
        },
    ]


def project_create_prompt_blocks(user_id: str) -> list[dict]:
    """Tell the user to type the new project name."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":pencil: *Create a New Project*\n\n"
                    "Reply in this thread with the project name and I'll "
                    "set it up for you."
                ),
            },
        },
    ]


def project_setup_step_blocks(
    project_name: str, step: str, step_number: int, total_steps: int,
    current_value: str = "",
) -> list[dict]:
    """Prompt for the next project-setup field.

    Each step collects one optional configuration value.
    The user may reply with the value or type ``skip`` to leave it blank.
    """
    _STEP_LABELS = {
        "project_name": (
            ":pencil: *Project Name*\n\n"
            "Enter the name for this project, or click *Skip* to "
            "keep the current name."
        ),
        "confluence_space_key": (
            ":confluence: *Confluence Space Key*\n\n"
            "Enter the Confluence space key for this project "
            "(e.g. `ENG`, `PROD`).  This is used when publishing PRDs.\n\n"
            "_Or click *Skip* to leave blank and use the default._"
        ),
        "jira_project_key": (
            ":jira2: *Jira Project Key*\n\n"
            "Enter the Jira project key (e.g. `MYPROJ`, `FEAT`).  "
            "This is used when creating Jira tickets for PRDs.\n\n"
            "_Or click *Skip* to leave blank and use the default._"
        ),
    }
    label = _STEP_LABELS.get(step, f"*{step}*")
    current_hint = ""
    if current_value:
        display_val = current_value
        current_hint = f"\n_Current value:_ `{display_val}`"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":gear: *Setting up project:* {project_name} "
                    f"(step {step_number}/{total_steps})\n\n"
                    f"{label}{current_hint}"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":fast_forward: Skip", "emoji": True},
                    "action_id": "setup_skip",
                    "value": step,
                },
            ],
        },
    ]


def project_setup_complete_blocks(project_name: str, details: dict) -> list[dict]:
    """Show the completed project setup summary."""
    lines = [
        f":white_check_mark: *Project '{project_name}' is set up and ready!*\n",
    ]
    csk = details.get("confluence_space_key", "")
    jpk = details.get("jira_project_key", "")
    cpid = details.get("confluence_parent_id", "")
    if csk:
        lines.append(f"• Confluence space key: `{csk}`")
    if jpk:
        lines.append(f"• Jira project key: `{jpk}`")
    if cpid:
        lines.append(f"• Confluence parent ID: `{cpid}`")
    if not (csk or jpk or cpid):
        lines.append("_No extra keys configured — defaults will be used._")
    lines.append(
        "\nYou can now start iterating ideas!"
    )
    from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
        BTN_CONFIGURE_MEMORY,
        BTN_HELP,
        BTN_NEW_IDEA,
    )
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(lines),
            },
        },
        {
            "type": "actions",
            "elements": [BTN_NEW_IDEA, BTN_CONFIGURE_MEMORY, BTN_HELP],
        },
    ]


def session_started_blocks(project_name: str) -> list[dict]:
    """Confirm that a project session has been activated."""
    from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
        session_action_buttons,
    )
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":white_check_mark: *Project session started:* {project_name}\n\n"
                    "All PRD flows will be linked to this project."
                ),
            },
        },
        *session_action_buttons(),
    ]


def session_ended_blocks() -> list[dict]:
    """Confirm that the project session has been ended."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":stop_button: *Project session ended.*\n\n"
                    "Mention me again to start a new session with a project."
                ),
            },
        },
    ]
