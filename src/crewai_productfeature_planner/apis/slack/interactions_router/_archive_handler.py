"""Handler for archive-idea confirmation button clicks."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _handle_archive_action(
    action_id: str,
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process an archive idea confirmation/cancel button click.

    On confirm: archives the working idea and its crew job.
    On cancel: posts a cancellation message.
    """
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()

    if action_id == "archive_idea_cancel":
        logger.info(
            "Archive idea cancelled by user=%s for run_id=%s",
            user_id, run_id,
        )
        if client and channel:
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=(
                        f"<@{user_id}> :no_entry_sign: Archive cancelled. "
                        "The idea remains in your list."
                    ),
                )
            except Exception as exc:
                logger.error("Archive cancel ack failed: %s", exc)
        return

    # action_id == "archive_idea_confirm"
    logger.info(
        "Archive idea confirmed by user=%s for run_id=%s",
        user_id, run_id,
    )

    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        execute_archive_idea,
    )

    execute_archive_idea(
        run_id=run_id,
        channel=channel,
        thread_ts=thread_ts,
        user=user_id,
    )
