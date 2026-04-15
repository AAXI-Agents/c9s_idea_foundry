"""Handler for post-completion delivery action button clicks.

.. deprecated::
    Confluence/Jira publishing removed from Slack in v0.71.0.
    The handler now logs a warning and returns without action.
"""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _handle_delivery_action(
    action_id: str,
    value: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """No-op — Confluence/Jira publishing removed from Slack."""
    logger.warning(
        "[DeliveryAction] Ignored deprecated action_id=%s "
        "(Confluence/Jira publishing removed from Slack)",
        action_id,
    )
