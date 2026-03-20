"""Shared Slack reply helper and bot intro message."""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def reply(channel: str, thread_ts: str, text: str) -> None:
    """Post a threaded reply in Slack."""
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
        except Exception as exc:
            logger.error("Slack reply failed: %s", exc)
    else:
        logger.error(
            "Cannot reply in %s — no Slack client available", channel,
        )


INTRO_MESSAGE = (
    ":wave: *Hey there!* I'm the *CrewAI Product Feature Planner Bot*.\n\n"
    "I can help you iterate on product ideas and generate comprehensive "
    "Product Requirements Documents (PRDs). "
    "Just @mention me with your product idea:\n\n"
    ">  `@crewai-prd-bot iterate an idea for a mobile fitness tracking app`\n"
    ">  `@crewai-prd-bot plan a feature for user onboarding flow`\n\n"
    "I'll kick off an idea iteration flow that:\n"
    ":one:  Refines your idea\n"
    ":two:  Breaks down requirements\n"
    ":three:  Drafts an executive summary and all PRD sections\n"
    ":four:  Posts a summary right here in this channel\n\n"
    "If I need more info, I'll ask you in a thread. :thread:\n\n"
    "_Click *Help* anytime to see what I can do._"
)


def post_intro(channel_id: str, team_id: str | None = None) -> None:
    """Post the bot introduction message to a channel."""
    from crewai_productfeature_planner.tools.slack_tools import (
        _get_slack_client,
        current_team_id,
    )

    if team_id:
        current_team_id.set(team_id)

    client = _get_slack_client()
    if not client:
        logger.warning("Cannot post intro – no Slack client available")
        return
    try:
        client.chat_postMessage(channel=channel_id, text=INTRO_MESSAGE)
        logger.info("Posted intro message to channel %s", channel_id)
    except Exception as exc:
        logger.error("Failed to post intro to %s: %s", channel_id, exc)
