"""Handler for post-completion delivery action button clicks.

Handles the ``delivery_publish`` and ``delivery_create_jira`` action IDs
that replace the old text-based prompts ("Say *publish*" / "Say *create
jira skeleton*").
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def _handle_delivery_action(
    action_id: str,
    value: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Route a delivery action button click to the correct handler.

    Args:
        action_id: ``delivery_publish`` or ``delivery_create_jira``.
        value: The ``run_id`` of the completed PRD.
        user_id: Slack user who clicked.
        channel: Slack channel.
        thread_ts: Thread timestamp.
    """
    run_id = value

    if action_id == "delivery_publish":
        _do_publish(run_id, user_id, channel, thread_ts)
    elif action_id == "delivery_create_jira":
        _do_create_jira(run_id, user_id, channel, thread_ts)
    else:
        logger.warning("[DeliveryAction] Unknown action_id: %s", action_id)


# ---------------------------------------------------------------------------
# Publish to Confluence
# ---------------------------------------------------------------------------


def _do_publish(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Trigger Confluence publishing via handle_publish_intent."""
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        handle_publish_intent,
    )
    from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool

    send_tool = SlackSendMessageTool()
    handle_publish_intent(channel, thread_ts, user_id, send_tool)


# ---------------------------------------------------------------------------
# Create Jira Tickets (skeleton phase)
# ---------------------------------------------------------------------------


def _do_create_jira(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Trigger the Jira skeleton phase for a specific run_id."""
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackSendMessageTool,
        _get_slack_client,
    )

    send_tool = SlackSendMessageTool()
    client = _get_slack_client()

    # Acknowledge
    ack_text = (
        f"<@{user_id}> :clipboard: Generating Jira skeleton for run "
        f"`{run_id[:8]}…` — I'll post the outline for your review."
    )
    if client:
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts, text=ack_text,
            )
        except Exception as exc:
            logger.debug("Jira skeleton ack failed: %s", exc)

    def _do_skeleton():
        try:
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _run_jira_phase,
            )
            _run_jira_phase(
                run_id, "skeleton", user_id, channel, thread_ts, send_tool,
            )
        except Exception as exc:
            logger.error(
                "[DeliveryAction] Jira skeleton failed for run_id=%s: %s",
                run_id, exc,
            )
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Jira skeleton generation failed: {exc}",
            )

    threading.Thread(target=_do_skeleton, daemon=True).start()
