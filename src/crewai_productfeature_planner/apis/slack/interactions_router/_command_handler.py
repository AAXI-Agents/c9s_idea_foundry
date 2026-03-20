"""Handler for command-button clicks (cmd_* action IDs).

Routes clickable command buttons to the same handlers that text-based
commands would invoke, providing a type-free UX.
"""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

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
        get_context_session,
    )

    session = get_context_session(user_id, channel)

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

    else:
        logger.warning("Unknown command action: %s", action_id)


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
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    has_project = bool(session and session.get("project_id"))
    blocks = help_blocks(user_id, has_project=has_project)

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
