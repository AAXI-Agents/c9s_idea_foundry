"""Slack message helpers and wait-for-decision utility."""

from __future__ import annotations

from crewai_productfeature_planner.apis.slack.interactive_handlers._run_state import (
    _lock,
    get_interactive_run,
)

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _post_blocks(channel: str, thread_ts: str, blocks: list[dict], text: str = "") -> None:
    """Post a Block Kit message to Slack."""
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        logger.warning("Cannot post blocks — no Slack client available")
        return
    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=blocks,
            text=text or "PRD Flow update",
        )
    except Exception as exc:
        logger.error("Failed to post blocks to %s: %s", channel, exc)


def _post_text(channel: str, thread_ts: str, text: str) -> None:
    """Post a plain text message to Slack."""
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return
    try:
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
    except Exception as exc:
        logger.error("Failed to post text to %s: %s", channel, exc)


def _wait_for_decision(
    run_id: str,
    action_type: str,
    timeout: float = 600.0,
) -> str | None:
    """Block until the user makes a decision or timeout expires.

    Args:
        run_id: The flow run identifier.
        action_type: Label for the pending action (for logging).
        timeout: Max seconds to wait.

    Returns:
        The ``action_id`` string chosen by the user, or ``None`` on
        timeout.
    """
    info = get_interactive_run(run_id)
    if not info:
        return None

    with _lock:
        info["pending_action"] = action_type
        info["decision"] = None
        info["event"].clear()

    logger.info(
        "Waiting for Slack interaction: run_id=%s action=%s",
        run_id, action_type,
    )

    signalled = info["event"].wait(timeout=timeout)
    if not signalled:
        logger.warning("Timeout waiting for interaction: run_id=%s", run_id)
        return None

    return info.get("decision")
