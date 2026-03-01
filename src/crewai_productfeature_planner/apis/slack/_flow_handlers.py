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
# Resume PRD flow from Slack
# ---------------------------------------------------------------------------


def handle_resume_prd(
    channel: str,
    thread_ts: str,
    user: str,
    send_tool,
    project_id: str | None = None,
) -> None:
    """Find the latest resumable PRD run and resume it in a background thread.

    If no resumable run exists, tells the user.
    """
    try:
        from crewai_productfeature_planner.mongodb import find_unfinalized

        unfinalized = find_unfinalized()

        # Filter to the active project if available
        if project_id:
            project_runs = [
                r for r in unfinalized
                if r.get("project_id") == project_id
            ]
            if project_runs:
                unfinalized = project_runs

        if not unfinalized:
            send_tool.run(
                channel=channel,
                text=(
                    f"<@{user}> :no_entry_sign: No paused or resumable PRD "
                    "runs found. Start a new one by telling me your idea!"
                ),
                thread_ts=thread_ts,
            )
            append_to_thread(channel, thread_ts, "assistant",
                             "(no resumable runs)")
            return

        # Pick the most recent run
        run_info = unfinalized[0]
        run_id = run_info["run_id"]
        idea = run_info.get("idea", "(unknown idea)")
        sections_done = run_info.get("sections_done", 0)
        total_sections = run_info.get("total_sections", 10)

        ack = (
            f"<@{user}> :arrows_counterclockwise: Resuming PRD flow "
            f"(run `{run_id}`):\n"
            f"> _{idea}_\n"
            f"Progress: {sections_done}/{total_sections} sections completed. "
            "I'll continue from where it paused."
        )
        send_tool.run(channel=channel, text=ack, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", ack)

        # Run the resume in a background thread
        from crewai_productfeature_planner.apis.prd.service import resume_prd_flow
        from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs
        from crewai_productfeature_planner.tools.slack_tools import (
            SlackPostPRDResultTool,
        )

        if run_id not in runs:
            runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")

        def _resume_and_notify():
            try:
                resume_prd_flow(run_id, auto_approve=True)

                run = runs.get(run_id)
                if run and run.status == FlowStatus.COMPLETED:
                    post_tool = SlackPostPRDResultTool()
                    post_tool.run(
                        channel=channel,
                        idea=idea,
                        output_file=run.output_file,
                        confluence_url=run.confluence_url,
                        jira_output=run.jira_output,
                        thread_ts=thread_ts,
                    )
                elif run and run.status == FlowStatus.PAUSED:
                    send_tool.run(
                        channel=channel,
                        text=(
                            f":pause_button: PRD flow paused again "
                            f"(run `{run_id}`). Resume via the API "
                            "or say *resume prd flow*."
                        ),
                        thread_ts=thread_ts,
                    )
                else:
                    error_msg = run.error if run else "Unknown error"
                    send_tool.run(
                        channel=channel,
                        text=f":x: PRD flow failed: {error_msg}",
                        thread_ts=thread_ts,
                    )
            except Exception as exc:
                logger.error("Resume PRD flow %s failed: %s", run_id, exc)
                try:
                    send_tool.run(
                        channel=channel,
                        text=f":x: Failed to resume PRD flow: {exc}",
                        thread_ts=thread_ts,
                    )
                except Exception:
                    pass

        t = threading.Thread(
            target=_resume_and_notify,
            name=f"slack-prd-resume-{run_id}",
            daemon=True,
        )
        t.start()
        logger.info(
            "Slack PRD resume started for run_id=%s in thread %s/%s",
            run_id, channel, thread_ts,
        )

    except Exception as exc:
        err_msg = f"<@{user}> :x: Failed to resume PRD flow: {exc}"
        send_tool.run(channel=channel, text=err_msg, thread_ts=thread_ts)
        append_to_thread(channel, thread_ts, "assistant", err_msg)
        logger.error("Resume PRD intent failed: %s", exc)


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
