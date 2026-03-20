"""Handler for restart-PRD confirmation button clicks."""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _handle_restart_prd_action(
    action_id: str,
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a restart PRD confirmation/cancel button click.

    On confirm: archives the old run and starts a fresh PRD flow.
    On cancel: posts a cancellation message.
    """
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()

    if action_id == "restart_prd_cancel":
        logger.info(
            "Restart PRD cancelled by user=%s for run_id=%s",
            user_id, run_id,
        )
        if client and channel:
            from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
                restart_cancelled_buttons,
            )
            text = (
                f"<@{user_id}> :no_entry_sign: Restart cancelled. "
                "Your current PRD run is unchanged."
            )
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    blocks=[
                        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                        *restart_cancelled_buttons(),
                    ],
                    text=text,
                )
            except Exception as exc:
                logger.error("Restart cancel ack failed: %s", exc)
        return

    # action_id == "restart_prd_confirm"
    logger.info(
        "Restart PRD confirmed by user=%s for run_id=%s",
        user_id, run_id,
    )

    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        execute_restart_prd,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        get_context_session,
    )

    session = get_context_session(user_id, channel)
    project_id = session.get("project_id") if session else None

    execute_restart_prd(
        run_id=run_id,
        channel=channel,
        thread_ts=thread_ts,
        user=user_id,
        project_id=project_id,
    )
