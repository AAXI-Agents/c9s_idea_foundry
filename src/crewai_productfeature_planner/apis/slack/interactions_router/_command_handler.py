"""Handler for command-button clicks (cmd_* action IDs).

Routes clickable command buttons to the same handlers that text-based
commands would invoke, providing a type-free UX.
"""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Admin-only actions (channel context only — DMs are always allowed).
_ADMIN_ACTIONS = frozenset({
    "cmd_configure_project",
    "cmd_configure_memory",
    "cmd_switch_project",
    "cmd_create_project",
})

# Config actions blocked while an idea flow is in-progress.
_CONFIG_ACTIONS = frozenset({
    "cmd_configure_project",
    "cmd_configure_memory",
})

# All cmd_* action IDs recognised by this handler.
CMD_ACTIONS = frozenset({
    "cmd_list_ideas",
    "cmd_list_products",
    "cmd_configure_project",
    "cmd_configure_memory",
    "cmd_switch_project",
    "cmd_end_session",
    "cmd_resume_prd",
    "cmd_create_project",
    "cmd_list_projects",
    "cmd_help",
    "cmd_check_publish",
    "cmd_publish",
    "cmd_create_jira",
    "cmd_restart_prd",
    "cmd_current_project",
    "cmd_create_prd",
    "cmd_iterate_idea",
    "cmd_summarize_ideas",
})


def _handle_command_action(
    action_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Dispatch a ``cmd_*`` button click to the appropriate handler."""
    logger.info(
        "Command button clicked: action=%s user=%s channel=%s thread=%s",
        action_id, user_id, channel, thread_ts,
    )

    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
        get_context_session,
    )

    session = get_context_session(user_id, channel)

    # Admin-only actions in channels
    if action_id in _ADMIN_ACTIONS and not can_manage_memory(user_id, channel):
        _deny_non_admin(channel, thread_ts, user_id)
        return

    # Block config changes while an idea flow is in-progress
    if action_id in _CONFIG_ACTIONS:
        project_id = session.get("project_id") if session else None
        if project_id and _is_flow_active(project_id):
            _deny_active_flow(channel, thread_ts, user_id)
            return

    if action_id == "cmd_list_ideas":
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_list_ideas,
        )
        handle_list_ideas(channel, thread_ts, user_id, session)

    elif action_id == "cmd_list_products":
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_list_products,
        )
        handle_list_products(channel, thread_ts, user_id, session)

    elif action_id == "cmd_configure_project":
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_update_config,
        )
        handle_update_config(channel, thread_ts, user_id, session)

    elif action_id == "cmd_configure_memory":
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_configure_memory,
        )
        handle_configure_memory(channel, thread_ts, user_id, session)

    elif action_id == "cmd_switch_project":
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_switch_project,
        )
        handle_switch_project(channel, thread_ts, user_id)

    elif action_id == "cmd_end_session":
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_end_session,
        )
        handle_end_session(channel, thread_ts, user_id)

    elif action_id == "cmd_resume_prd":
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_resume_prd,
        )
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        handle_resume_prd(channel, thread_ts, user_id, SlackSendMessageTool())

    elif action_id == "cmd_create_project":
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_create_project_intent,
        )
        handle_create_project_intent(channel, thread_ts, user_id)

    elif action_id == "cmd_list_projects":
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            prompt_project_selection,
        )
        prompt_project_selection(channel, thread_ts, user_id)

    elif action_id == "cmd_help":
        _handle_help(channel, thread_ts, user_id, session)

    elif action_id == "cmd_check_publish":
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_check_publish_intent,
        )
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        handle_check_publish_intent(channel, thread_ts, user_id, SlackSendMessageTool())

    elif action_id == "cmd_publish":
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_publish_intent,
        )
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        handle_publish_intent(channel, thread_ts, user_id, SlackSendMessageTool())

    elif action_id == "cmd_create_jira":
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_create_jira_intent,
        )
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        handle_create_jira_intent(channel, thread_ts, user_id, SlackSendMessageTool())

    elif action_id == "cmd_restart_prd":
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_restart_prd,
        )
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        handle_restart_prd(
            channel, thread_ts, user_id, SlackSendMessageTool(),
            event_ts=thread_ts,
            project_id=session.get("project_id") if session else None,
        )

    elif action_id == "cmd_current_project":
        from crewai_productfeature_planner.apis.slack._session_project import (
            handle_current_project,
        )
        handle_current_project(channel, thread_ts, user_id, session)

    elif action_id == "cmd_create_prd":
        from crewai_productfeature_planner.apis.slack._session_reply import reply
        reply(
            channel, thread_ts,
            f"<@{user_id}> :bulb: What product or feature idea would you "
            "like to work on? Describe it and I'll start an interactive PRD flow.",
        )

    elif action_id == "cmd_iterate_idea":
        from crewai_productfeature_planner.apis.slack._session_ideas import (
            handle_iterate_idea,
        )
        handle_iterate_idea(channel, thread_ts, user_id, session)

    elif action_id == "cmd_summarize_ideas":
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _handle_summarize_ideas,
        )
        from crewai_productfeature_planner.apis.slack._thread_state import (
            get_thread_history,
        )
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        history = get_thread_history(channel, thread_ts)
        project_id = session.get("project_id") if session else None
        project_name = session.get("project_name") if session else None
        _handle_summarize_ideas(
            channel, thread_ts, user_id,
            "summarize ideas", history,
            project_id, project_name,
            SlackSendMessageTool(),
        )

    else:
        logger.warning("Unknown command action: %s", action_id)


def _deny_non_admin(channel: str, thread_ts: str, user_id: str) -> None:
    """Post an ephemeral-style denial message for non-admin users."""
    from crewai_productfeature_planner.apis.slack._session_reply import reply

    reply(
        channel, thread_ts,
        f"<@{user_id}> :lock: Only workspace admins can manage project "
        "settings in a channel. Please ask an admin.",
    )


def _deny_active_flow(channel: str, thread_ts: str, user_id: str) -> None:
    """Block config changes while an idea flow is in-progress."""
    from crewai_productfeature_planner.apis.slack._session_reply import reply

    reply(
        channel, thread_ts,
        f"<@{user_id}> :warning: Cannot configure project settings while "
        "an idea flow is in progress. Please wait for the current flow to "
        "complete or publish before making changes.",
    )


def _is_flow_active(project_id: str) -> bool:
    """Return ``True`` if the project has any in-progress idea flow."""
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            has_active_idea_flow,
        )
        return has_active_idea_flow(project_id)
    except Exception:  # noqa: BLE001
        return False


def _handle_help(
    channel: str,
    thread_ts: str,
    user_id: str,
    session: dict | None,
) -> None:
    """Post the help message with interactive buttons."""
    from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
        help_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    has_project = bool(session and session.get("project_id"))
    is_admin = can_manage_memory(user_id, channel)
    blocks = help_blocks(user_id, has_project=has_project, is_admin=is_admin)

    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                blocks=blocks,
                text="Here's what I can do:",
            )
        except Exception as exc:
            logger.error("Failed to post help blocks: %s", exc)
