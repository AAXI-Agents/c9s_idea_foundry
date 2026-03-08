"""List working ideas for the current project."""

from __future__ import annotations

import logging

from ._session_project import prompt_project_selection
from ._session_reply import reply

logger = logging.getLogger(__name__)


def _backfill_missing_idea_titles(ideas: list[dict]) -> None:
    """Fill empty ``idea`` values from the crew-jobs collection.

    Some legacy working-idea documents were created (via
    ``save_slack_context`` upsert) before the idea text was
    persisted, leaving the ``idea`` field empty.  This helper
    looks up the corresponding crew-job document — which always
    stores the idea — and backfills the text.
    """
    missing = [i for i in ideas if not i.get("idea")]
    if not missing:
        return
    try:
        from crewai_productfeature_planner.mongodb.crew_jobs import find_job

        for idea_doc in missing:
            run_id = idea_doc.get("run_id", "")
            if not run_id:
                continue
            job = find_job(run_id)
            if not job:
                continue
            # Prefer the dedicated idea field; fall back to flow_name
            # which may contain the idea text due to a legacy
            # positional-arg bug in create_job() callers.
            title = job.get("idea") or job.get("flow_name") or ""
            if title and title != "prd":
                idea_doc["idea"] = title
    except Exception:  # noqa: BLE001
        pass  # best-effort — caller will show "Untitled" anyway


def handle_list_ideas(
    channel: str,
    thread_ts: str,
    user: str,
    session: dict | None,
) -> None:
    """List working ideas associated with the user's active project.

    If no project session is active, prompts for project selection.
    Shows ideas in any status — in-progress, paused, failed **and**
    completed ideas that still have pending delivery work (Confluence
    publish, Jira ticketing).  This gives users a single command to
    see everything and resume where they left off.
    """
    project_id = session.get("project_id") if session else None
    project_name = session.get("project_name", "your project") if session else None

    if not project_id:
        prompt_project_selection(channel, thread_ts, user)
        return

    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
        find_completed_ideas_by_project,
        find_ideas_by_project,
    )

    ideas = find_ideas_by_project(project_id, channel=channel)
    products = find_completed_ideas_by_project(project_id, channel=channel)

    if not ideas and not products:
        reply(
            channel, thread_ts,
            f"<@{user}> :page_facing_up: No ideas found for *{project_name}*.\n\n"
            "Would you like to *iterate on a new idea*? Just describe your "
            "product or feature concept and I'll get started!",
        )
        return

    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        reply(
            channel, thread_ts,
            f"<@{user}> No Slack client available to post idea list.",
        )
        return

    # ── In-progress / paused / failed ideas ──
    if ideas:
        _backfill_missing_idea_titles(ideas)

        from crewai_productfeature_planner.apis.slack.blocks import idea_list_blocks

        blocks = idea_list_blocks(
            ideas, user, project_name or "your project", project_id or "",
        )
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                blocks=blocks,
                text=f"Ideas for {project_name}",
            )
        except Exception as exc:
            logger.error("Failed to post idea list blocks: %s", exc)
            reply(channel, thread_ts, f"<@{user}> Failed to list ideas.")

    # ── Completed products with delivery status ──
    if products:
        _backfill_missing_idea_titles(products)

        from crewai_productfeature_planner.apis.slack.blocks import (
            product_list_blocks,
        )

        blocks = product_list_blocks(
            products, user, project_name or "your project", project_id or "",
        )
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
