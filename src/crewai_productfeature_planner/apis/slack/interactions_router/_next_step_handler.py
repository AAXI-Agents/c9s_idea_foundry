"""Handler for next-step suggestion feedback button clicks."""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _handle_next_step_feedback(
    action_id: str,
    value: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a next-step suggestion feedback button click.

    The ``value`` field encodes ``<next_step>|<interaction_id>``.
    Records whether the user accepted or dismissed the suggestion,
    and if accepted, triggers the suggested action.
    """
    from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
        record_next_step_feedback,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()

    # Parse the encoded value
    parts = value.split("|", 1)
    next_step = parts[0] if parts else ""
    interaction_id = parts[1] if len(parts) > 1 and parts[1] else None

    accepted = action_id == "next_step_accept"

    # Record feedback in agentInteraction
    if interaction_id:
        record_next_step_feedback(interaction_id, accepted)

    logger.info(
        "Next-step feedback: action=%s next_step=%s accepted=%s "
        "interaction_id=%s user=%s",
        action_id, next_step, accepted, interaction_id, user_id,
    )

    if not accepted:
        # Dismissed — just acknowledge
        if client and channel:
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=":ok_hand: No problem! Let me know when you need help.",
                )
            except Exception as exc:
                logger.error("Next-step dismiss ack failed: %s", exc)
        return

    # Accepted — trigger the suggested action
    def _post(text: str) -> None:
        if client and channel:
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=text,
                )
            except Exception as exc:
                logger.error("Next-step accept post failed: %s", exc)

    def _post_blocks(text: str, buttons: list[dict]) -> None:
        """Post text with action buttons."""
        if client and channel:
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    blocks=[
                        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                        {"type": "actions", "elements": buttons},
                    ],
                    text=text,
                )
            except Exception as exc:
                logger.error("Next-step accept post failed: %s", exc)
                _post(text)

    from crewai_productfeature_planner.apis.slack.session_manager import (
        get_context_session,
    )

    session = get_context_session(user_id, channel)

    if next_step == "configure_confluence":
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            BTN_CONFIGURE,
        )
        _post_blocks(
            ":confluence: To set the Confluence space key, configure "
            "the project settings.",
            [BTN_CONFIGURE],
        )
    elif next_step == "configure_jira":
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            BTN_CONFIGURE,
        )
        _post_blocks(
            ":jira2: To set the Jira project key, configure "
            "the project settings.",
            [BTN_CONFIGURE],
        )
    elif next_step == "configure_memory":
        from crewai_productfeature_planner.apis.slack.session_manager import (
            can_manage_memory,
        )
        if not can_manage_memory(user_id, channel):
            _post(
                ":lock: Only workspace admins can configure project "
                "memory in a channel. Please ask an admin.",
            )
        elif session and session.get("project_id"):
            from crewai_productfeature_planner.apis.slack._session_handlers import (
                handle_configure_memory,
            )
            handle_configure_memory(channel, thread_ts, user_id, session)
        else:
            _post(":warning: No active project session. Please select a project first.")
    elif next_step == "create_prd":
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            BTN_NEW_IDEA,
        )
        _post_blocks(
            ":rocket: Great! Click below to start a new idea, or "
            "describe your product/feature concept directly.",
            [BTN_NEW_IDEA],
        )
    elif next_step in ("publish", "configure_missing_keys"):
        # Confluence/Jira publishing removed from Slack in v0.71.0
        _post(":info: Publishing to Confluence and Jira is managed "
              "through the web API. Use the API endpoints to publish.")
    elif next_step == "review_prd":
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            check_publish_buttons,
        )
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client
        text = ":mag: You have completed PRDs ready for review!"
        client = _get_slack_client()
        if client:
            try:
                client.chat_postMessage(
                    channel=channel, thread_ts=thread_ts,
                    blocks=[
                        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                        *check_publish_buttons(),
                    ],
                    text=text,
                )
            except Exception:
                _post(text)
        else:
            _post(text)
    elif next_step in ("create_jira_skeleton", "create_jira"):
        # Jira creation removed from Slack in v0.71.0
        _post(":info: Jira ticket creation is managed through the web API. "
              "Use the API endpoints to create Jira tickets.")
    else:
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            BTN_HELP,
        )
        _post_blocks(
            f":bulb: Ready to proceed with _{next_step}_? "
            "Click Help to see available actions.",
            [BTN_HELP],
        )
