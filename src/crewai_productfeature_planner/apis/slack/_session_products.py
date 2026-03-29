"""List completed products (ready for delivery) for the current project."""

from __future__ import annotations

from ._session_project import prompt_project_selection
from ._session_reply import reply

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def handle_list_products(
    channel: str,
    thread_ts: str,
    user: str,
    session: dict | None,
) -> None:
    """List completed working ideas for the user's active project.

    Shows only ideas with ``status == "completed"`` (not archived).
    Each product is enriched with delivery status (Confluence published,
    Jira phase) and action buttons for the delivery manager to resume
    or start delivery actions.

    If no project session is active, prompts for project selection.
    """
    project_id = session.get("project_id") if session else None
    project_name = session.get("project_name", "your project") if session else None

    if not project_id:
        prompt_project_selection(channel, thread_ts, user)
        return

    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
        find_completed_ideas_by_project,
    )

    products = find_completed_ideas_by_project(project_id, channel=channel)

    if not products:
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            no_products_buttons,
        )
        from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

        client = _get_slack_client()
        text = (
            f"<@{user}> :package: No completed products found for *{project_name}*.\n\n"
            "Completed ideas will appear here once a PRD flow finishes."
        )
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            *no_products_buttons(),
        ]
        if client:
            try:
                client.chat_postMessage(
                    channel=channel, thread_ts=thread_ts,
                    blocks=blocks, text=text,
                )
            except Exception:
                reply(channel, thread_ts, text)
        else:
            reply(channel, thread_ts, text)
        return

    # Enrich products that are missing a title
    from ._session_ideas import _backfill_missing_idea_titles
    _backfill_missing_idea_titles(products)

    from crewai_productfeature_planner.apis.slack.blocks import product_list_blocks
    from crewai_productfeature_planner.apis.slack.session_manager import can_manage_memory
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    blocks = product_list_blocks(
        products, user, project_name or "your project", project_id or "",
        is_admin=can_manage_memory(user, channel),
    )

    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                blocks=blocks,
                text=f"Products for {project_name}",
            )
        except Exception as exc:
            logger.error("Failed to post product list blocks: %s", exc)
            reply(channel, thread_ts, f"<@{user}> Failed to list products.")
    else:
        reply(
            channel, thread_ts,
            f"<@{user}> No Slack client available to post product list.",
        )
