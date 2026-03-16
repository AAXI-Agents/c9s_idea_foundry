"""Memory configuration and project config update handlers."""

from __future__ import annotations

import logging

from ._session_reply import reply

logger = logging.getLogger(__name__)


def handle_configure_memory(
    channel: str,
    thread_ts: str,
    user: str,
    session: dict | None,
) -> None:
    """Show the project memory configuration menu."""
    from crewai_productfeature_planner.apis.slack.blocks import memory_configure_blocks
    from crewai_productfeature_planner.mongodb.project_memory import upsert_project_memory
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    if not session or not session.get("project_id"):
        reply(channel, thread_ts, ":warning: No active project session. Please select a project first.")
        return

    project_id = session["project_id"]
    project_name = session.get("project_name", "Unknown")

    # Ensure memory scaffold exists
    upsert_project_memory(project_id)

    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=memory_configure_blocks(project_name, user),
            text=f"Configure memory for {project_name}",
        )
    except Exception as exc:
        logger.error("Failed to post memory config menu: %s", exc)


def handle_memory_reply(
    user_id: str,
    channel: str,
    thread_ts: str,
    text: str,
    category: str,
    project_id: str,
) -> None:
    """Save memory entries typed by the user in a thread reply."""
    from crewai_productfeature_planner.apis.slack.blocks import memory_saved_blocks
    from crewai_productfeature_planner.mongodb.project_memory import (
        MemoryCategory,
        add_memory_entry,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    cat_enum = MemoryCategory(category)
    cat_labels = {
        MemoryCategory.IDEA_ITERATION: "Idea & Iteration",
        MemoryCategory.KNOWLEDGE: "Knowledge",
        MemoryCategory.TOOLS: "Tools",
    }
    cat_label = cat_labels.get(cat_enum, category)

    # Split multi-line reply into individual entries
    lines = [line.strip().lstrip("•-*").strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    if not lines:
        reply(channel, thread_ts, ":warning: No entries found. Please try again.")
        return

    saved = 0
    for line in lines:
        # Infer kind for knowledge entries
        kind = None
        if cat_enum == MemoryCategory.KNOWLEDGE:
            if line.startswith("http://") or line.startswith("https://"):
                kind = "link"
            else:
                kind = "note"

        ok = add_memory_entry(
            project_id,
            cat_enum,
            line,
            added_by=user_id,
            kind=kind,
        )
        if ok:
            saved += 1

    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=memory_saved_blocks(cat_label, saved),
            text=f"Saved {saved} {cat_label} entries",
        )
    except Exception as exc:
        logger.error("Failed to post memory-saved confirmation: %s", exc)


def handle_update_config(
    channel: str,
    thread_ts: str,
    user: str,
    session: dict | None,
    *,
    confluence_space_key: str | None = None,
    jira_project_key: str | None = None,
) -> None:
    """Launch the project configuration wizard for the active project.

    Walks the user through all configuration fields (project name,
    Confluence key, Jira key, Figma API key, Figma team ID) with
    current values shown so the user can update or skip each one.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_setup_step_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        _SETUP_STEPS,
        mark_pending_reconfig,
    )
    from crewai_productfeature_planner.mongodb.project_config import get_project

    project_id = session.get("project_id") if session else None
    project_name = session.get("project_name", "your project") if session else None

    if not project_id:
        reply(
            channel, thread_ts,
            f"<@{user}> :warning: No active project session. "
            "Please select a project first.",
        )
        return

    # Load current config from MongoDB
    project_config = get_project(project_id) or {}

    # Start the reconfigure wizard
    mark_pending_reconfig(
        user_id=user,
        channel=channel,
        thread_ts=thread_ts,
        project_id=project_id,
        project_config=project_config,
    )

    # Post the first step prompt with current value
    first_step = _SETUP_STEPS[0]
    current_value = project_config.get("name", "") if first_step == "project_name" else project_config.get(first_step, "")
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                blocks=project_setup_step_blocks(
                    project_name or "your project",
                    first_step,
                    1,
                    len(_SETUP_STEPS),
                    current_value=current_value,
                ),
                text=f"Configure {first_step.replace('_', ' ')} (or type 'skip').",
            )
        except Exception as exc:
            logger.error("Failed to post reconfig step: %s", exc)
