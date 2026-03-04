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
    """Update project configuration with Confluence/Jira keys.

    If no key values are provided, prompt the user to supply them.
    """
    from crewai_productfeature_planner.mongodb.project_config import update_project

    project_id = session.get("project_id") if session else None
    project_name = session.get("project_name", "your project") if session else None

    if not project_id:
        reply(
            channel, thread_ts,
            f"<@{user}> :warning: No active project session. "
            "Please select a project first.",
        )
        return

    fields: dict[str, str] = {}
    if confluence_space_key:
        fields["confluence_space_key"] = confluence_space_key
    if jira_project_key:
        fields["jira_project_key"] = jira_project_key

    if not fields:
        reply(
            channel, thread_ts,
            f"<@{user}> I can update your project configuration. "
            "Please provide the values, for example:\n"
            ">  _\"set confluence key MYSPACE and jira key PROJ\"_",
        )
        return

    count = update_project(project_id, **fields)

    if count:
        parts = []
        if confluence_space_key:
            parts.append(f"Confluence space key → `{confluence_space_key}`")
        if jira_project_key:
            parts.append(f"Jira project key → `{jira_project_key}`")
        summary = "\n".join(f"• {p}" for p in parts)
        reply(
            channel, thread_ts,
            f"<@{user}> :white_check_mark: Updated *{project_name}* config:\n{summary}",
        )
    else:
        reply(
            channel, thread_ts,
            f"<@{user}> :warning: Could not update the project configuration. "
            "Please check the project ID and try again.",
        )
