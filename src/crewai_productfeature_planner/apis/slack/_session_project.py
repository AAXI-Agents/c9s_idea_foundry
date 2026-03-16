"""Project selection, switching, creation, and setup wizard handlers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def prompt_project_selection(channel: str, thread_ts: str, user: str) -> None:
    """Post the project-selection Block Kit prompt.

    In channels, only admins may select a project.  Non-admins are
    told to ask an admin.
    """
    from crewai_productfeature_planner.apis.slack.blocks import project_selection_blocks
    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
        is_dm,
    )
    from crewai_productfeature_planner.mongodb.project_config import list_projects
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        logger.error(
            "[ProjectSelection] Cannot post project selection for user=%s "
            "channel=%s — no Slack client available (SLACK_ACCESS_TOKEN not set?)",
            user, channel,
        )
        return

    # In channels, non-admins cannot select a project
    if not is_dm(channel) and not can_manage_memory(user, channel):
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=(
                    f"<@{user}> :lock: No project has been configured "
                    "for this channel yet. Please ask a workspace admin "
                    "to select a project first."
                ),
            )
        except Exception as exc:
            logger.error("Failed to post admin-required notice: %s", exc)
        return

    projects = list_projects(limit=20)
    blocks = project_selection_blocks(projects, user)
    msg = (
        f"<@{user}> Before we get started, please select a project "
        "to work on (or create a new one)."
    )
    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=blocks, text=msg,
        )
    except Exception as exc:
        logger.error("Failed to post project selection: %s", exc)


def handle_switch_project(channel: str, thread_ts: str, user: str) -> None:
    """End the current session and show the project picker."""
    from crewai_productfeature_planner.apis.slack.session_manager import (
        deactivate_channel_session,
        deactivate_session,
        is_dm,
    )

    if is_dm(channel):
        deactivate_session(user)
    else:
        deactivate_channel_session(channel)
    prompt_project_selection(channel, thread_ts, user)


def handle_end_session(channel: str, thread_ts: str, user: str) -> None:
    """End the user's active session and confirm."""
    from crewai_productfeature_planner.apis.slack.blocks import session_ended_blocks
    from crewai_productfeature_planner.apis.slack.session_manager import (
        deactivate_channel_session,
        deactivate_session,
        is_dm,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    if is_dm(channel):
        deactivate_session(user)
    else:
        deactivate_channel_session(channel)
    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                blocks=session_ended_blocks(),
                text="Session ended",
            )
        except Exception as exc:
            logger.error("Failed to post session-ended: %s", exc)


def handle_current_project(
    channel: str, thread_ts: str, user: str, session: dict | None,
) -> None:
    """Tell the user which project they're in (or that they have none)."""
    from crewai_productfeature_planner.apis.slack.blocks import active_session_blocks
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    if session and session.get("project_name"):
        blocks = active_session_blocks(
            session["project_name"],
            session.get("project_id", ""),
            user,
        )
        text = f"Current project: {session['project_name']}"
    else:
        prompt_project_selection(channel, thread_ts, user)
        return

    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=blocks, text=text,
        )
    except Exception as exc:
        logger.error("Failed to post current-project: %s", exc)


def handle_create_project_intent(
    channel: str, thread_ts: str, user: str,
) -> None:
    """Directly prompt the user for a project name (skipping the picker)."""
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_create_prompt_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
        is_dm,
        mark_pending_create,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        logger.error(
            "[CreateProject] No Slack client available for user=%s channel=%s",
            user, channel,
        )
        return

    # In channels, only admins may create projects
    if not is_dm(channel) and not can_manage_memory(user, channel):
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=(
                    f"<@{user}> :lock: Only workspace admins can create "
                    "a project for this channel. Please ask an admin."
                ),
            )
        except Exception as exc:
            logger.error("Failed to post admin-required notice: %s", exc)
        return

    mark_pending_create(user, channel, thread_ts)
    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=project_create_prompt_blocks(user),
            text="What would you like to name the new project? Reply in this thread.",
        )
        logger.info(
            "Prompted user=%s in channel=%s for new project name", user, channel,
        )
    except Exception as exc:
        logger.error("Failed to post create-project prompt: %s", exc)


def handle_project_name_reply(
    channel: str, thread_ts: str, user: str, project_name: str,
) -> None:
    """Create a new project from a thread reply and enter setup wizard."""
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_setup_step_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        mark_pending_setup,
    )
    from crewai_productfeature_planner.mongodb.project_config import create_project
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    project_id = create_project(name=project_name)
    if not project_id:
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=":x: Failed to create the project. Please try again.",
            )
        except Exception:
            pass
        return

    # Enter the project-setup wizard
    mark_pending_setup(user, channel, thread_ts, project_id, project_name)

    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=project_setup_step_blocks(project_name, "confluence_space_key", 1, 3),
            text="Enter the Confluence space key (or type 'skip').",
        )
        logger.info(
            "Project '%s' (id=%s) created — starting setup wizard for user=%s",
            project_name, project_id, user,
        )
    except Exception as exc:
        logger.error("Failed to post setup step prompt: %s", exc)


def handle_project_setup_reply(
    channel: str, thread_ts: str, user: str, text: str,
) -> None:
    """Process a single setup-wizard reply and advance to the next step."""
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_setup_complete_blocks,
        project_setup_step_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        _SETUP_STEPS,
        activate_channel_project,
        activate_project,
        advance_pending_setup,
        get_pending_setup,
        is_dm,
    )
    from crewai_productfeature_planner.mongodb.project_config import update_project
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    # "skip" / "s" / empty -> store as empty string (keep existing for project_name)
    value = text.strip()
    is_skip = value.lower() in ("skip", "s", "-")
    if is_skip:
        # For project_name, "skip" means keep the current name
        pending = get_pending_setup(user)
        if pending and pending.get("step") == "project_name":
            value = pending.get("project_name", "")
        else:
            value = ""

    entry = advance_pending_setup(user, value)
    if entry is None:
        return

    step = entry["step"]
    project_id = entry["project_id"]
    project_name = entry["project_name"]

    if step == "done":
        # Finalise: persist keys and activate session
        update_fields: dict[str, str] = {}
        for key in (
            "project_name",
            "confluence_space_key",
            "jira_project_key",
            "figma_api_key",
            "figma_team_id",
        ):
            if key == "project_name":
                # The wizard stores the resolved name; persist as "name"
                if entry.get("project_name"):
                    update_fields["name"] = entry["project_name"]
                continue
            if entry.get(key):
                update_fields[key] = entry[key]
        if update_fields:
            update_project(project_id, **update_fields)
            logger.info(
                "Updated project %s with setup fields: %s",
                project_id, list(update_fields.keys()),
            )

        if is_dm(channel):
            activate_project(
                user_id=user,
                channel=channel,
                project_id=project_id,
                project_name=project_name,
            )
        else:
            activate_channel_project(
                channel_id=channel,
                project_id=project_id,
                project_name=project_name,
                activated_by=user,
            )

        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                blocks=project_setup_complete_blocks(project_name, entry),
                text=f"Project '{project_name}' configured and session started!",
            )
        except Exception as exc:
            logger.error("Failed to post setup-complete: %s", exc)

        # Proactive next-step suggestion after project setup
        from crewai_productfeature_planner.apis.slack._next_step import (
            predict_and_post_next_step,
        )
        predict_and_post_next_step(
            channel=channel,
            thread_ts=thread_ts,
            user=user,
            project_id=project_id,
            trigger_action="project_setup_complete",
            project_config=entry,
        )
        return

    # Post prompt for the next step, showing current value if reconfiguring
    step_idx = _SETUP_STEPS.index(step) + 1
    total = len(_SETUP_STEPS)
    current_entry = get_pending_setup(user)
    current_value = current_entry.get(step, "") if current_entry else ""
    try:
        client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=project_setup_step_blocks(
                project_name, step, step_idx, total,
                current_value=current_value,
            ),
            text=f"Enter {step.replace('_', ' ')} (or type 'skip').",
        )
    except Exception as exc:
        logger.error("Failed to post setup step prompt: %s", exc)
