"""PRD flow kickoff and publishing handlers for Slack.

Extracted from ``events_router.py`` to keep the router slim.
Handles:
* PRD flow kickoff (interactive and auto-approve modes)
* Publishing to Confluence + Jira
* Publishing status checks
"""

from __future__ import annotations

import logging
import threading
import uuid

from crewai_productfeature_planner.apis.slack._thread_state import append_to_thread

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Publish intent handlers
# ---------------------------------------------------------------------------


def handle_publish_intent(channel: str, thread_ts: str, user: str, send_tool) -> None:
    """Publish all pending PRDs to Confluence and create Jira tickets."""
    ack = (
        f"<@{user}> :gear: Publishing all pending PRDs to Confluence and "
        "creating Jira tickets… I'll post the results shortly."
    )
    send_tool.run(channel=channel, text=ack, thread_ts=thread_ts)
    append_to_thread(channel, thread_ts, "assistant", ack)

    try:
        from crewai_productfeature_planner.apis.publishing.service import (
            publish_all_and_create_tickets,
        )

        result = publish_all_and_create_tickets()

        conf = result.get("confluence", {})
        jira = result.get("jira", {})

        lines = [f"<@{user}> :white_check_mark: *Publishing complete!*\n"]

        # Confluence summary
        pub_count = conf.get("published", 0)
        pub_fail = conf.get("failed", 0)
        if pub_count or pub_fail:
            lines.append(f"*Confluence:* {pub_count} published, {pub_fail} failed")
            for r in conf.get("results", []):
                lines.append(f"  • _{r.get('title', '')}_ → <{r.get('url', '')}|View>")
        else:
            msg = conf.get("message", "No pending PRDs to publish")
            lines.append(f"*Confluence:* {msg}")

        # Jira summary
        jira_count = jira.get("completed", 0)
        jira_fail = jira.get("failed", 0)
        if jira_count or jira_fail:
            lines.append(f"*Jira:* {jira_count} completed, {jira_fail} failed")
            for r in jira.get("results", []):
                keys = r.get("ticket_keys", [])
                if keys:
                    lines.append(f"  • run `{r.get('run_id', '')[:8]}…` → {', '.join(keys)}")
        else:
            msg = jira.get("message", "No pending Jira deliveries")
            lines.append(f"*Jira:* {msg}")

        summary = "\n".join(lines)
        send_tool.run(channel=channel, text=summary, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", summary)

    except Exception as exc:
        err_msg = f"<@{user}> :x: Publishing failed: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Publish intent failed: %s", exc)


def handle_check_publish_intent(channel: str, thread_ts: str, user: str, send_tool) -> None:
    """Check and report the publishing status of pending PRDs."""
    try:
        from crewai_productfeature_planner.apis.publishing.service import (
            list_pending_prds,
        )

        items = list_pending_prds()

        if not items:
            msg = (
                f"<@{user}> :white_check_mark: All clear! "
                "No PRDs pending Confluence publishing or Jira ticket creation."
            )
            send_tool.run(channel=channel, text=msg, thread_ts=thread_ts)
            append_to_thread(channel, thread_ts, "assistant", msg)
            return

        lines = [f"<@{user}> :clipboard: *Pending PRD Deliveries* ({len(items)} total)\n"]
        for item in items:
            rid = item.get("run_id", "disk")[:8]
            title = item.get("title", "Untitled")
            conf = ":white_check_mark:" if item.get("confluence_published") else ":x:"
            jira = ":white_check_mark:" if item.get("jira_completed") else ":x:"
            lines.append(f"  • `{rid}…` _{title}_ — Confluence {conf}  Jira {jira}")

        lines.append(
            "\n_Say *publish* to publish all pending PRDs and create Jira tickets._"
        )

        msg = "\n".join(lines)
        send_tool.run(channel=channel, text=msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", msg)

    except Exception as exc:
        err_msg = f"<@{user}> :x: Failed to check publishing status: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Check publish intent failed: %s", exc)


# ---------------------------------------------------------------------------
# PRD flow kickoff
# ---------------------------------------------------------------------------


def kick_off_prd_flow(
    *,
    channel: str,
    thread_ts: str,
    user: str,
    idea: str,
    event_ts: str,
    interactive: bool = False,
    project_id: str | None = None,
) -> None:
    """Start a PRD flow from a Slack interaction.

    When *interactive* is ``True``, the flow mirrors the CLI experience:
    refinement mode choice, idea approval, and requirements approval are
    all presented as Block Kit button prompts in the thread before
    sections are auto-generated.

    When ``False`` (the default), the flow runs with ``auto_approve=True``
    as before.

    If *project_id* is provided the working-idea document will be linked
    to the project so publishing can resolve project-level keys.
    """
    from crewai_productfeature_planner.apis.slack.router import _run_slack_prd_flow
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if client:
        try:
            client.reactions_add(channel=channel, timestamp=event_ts, name="eyes")
        except Exception:
            pass

    run_id = uuid.uuid4().hex[:12]

    if interactive:
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            run_interactive_slack_flow,
        )
        t = threading.Thread(
            target=run_interactive_slack_flow,
            args=(run_id, idea, channel, thread_ts, user),
            kwargs={"project_id": project_id},
            name=f"slack-prd-interactive-{run_id}",
            daemon=True,
        )
    else:
        t = threading.Thread(
            target=_run_slack_prd_flow,
            args=(run_id, idea, channel, thread_ts),
            kwargs={"project_id": project_id} if project_id else {},
            name=f"slack-prd-{run_id}",
            daemon=True,
        )
    t.start()
