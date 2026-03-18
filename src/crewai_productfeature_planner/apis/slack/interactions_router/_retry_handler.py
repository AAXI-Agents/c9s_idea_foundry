"""Handler for flow-retry button clicks (resume a paused PRD flow)."""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _handle_flow_retry(
    run_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Resume a paused PRD flow triggered by the *Retry* button.

    Delegates to :func:`handle_resume_prd` which finds the run in
    MongoDB, recovers Slack context, and launches a background thread.
    """
    try:
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_resume_prd,
        )
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_context_session,
        )
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool

        send_tool = SlackSendMessageTool()
        session = get_context_session(user_id, channel)
        project_id = session.get("project_id") if session else None

        logger.info(
            "Flow retry button clicked: run_id=%s user=%s channel=%s",
            run_id, user_id, channel,
        )

        handle_resume_prd(
            channel=channel,
            thread_ts=thread_ts,
            user=user_id,
            send_tool=send_tool,
            project_id=project_id,
        )
    except Exception as exc:
        logger.error(
            "Flow retry handler failed for run_id=%s: %s", run_id, exc,
        )
        try:
            from crewai_productfeature_planner.tools.slack_tools import _get_slack_client
            client = _get_slack_client()
            if client and channel:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=(
                        f":x: Failed to retry PRD flow: {exc}\n"
                        "Please say *resume prd flow* to try again."
                    ),
                )
        except Exception:  # noqa: BLE001
            pass
