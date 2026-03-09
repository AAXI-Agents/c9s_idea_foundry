"""Handler for product-list delivery action button clicks.

Handles buttons from the product list (``list products`` intent):

* ``product_confluence_<N>``    — Publish to Confluence
* ``product_jira_skeleton_<N>`` — Generate/review Jira skeleton
* ``product_jira_epics_<N>``    — Create Jira Epics & Stories
* ``product_jira_subtasks_<N>`` — Create Jira Sub-tasks
* ``product_view_<N>``          — View delivery details
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def _handle_product_list_action(
    action_id: str,
    value: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a delivery action button click from the product list.

    The button ``value`` is ``<project_id>|<idea_number>|<run_id>``.
    """
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackSendMessageTool,
        _get_slack_client,
    )

    # Parse value: "project_id|idea_number|run_id"
    parts = value.split("|", 2)
    if len(parts) != 3:
        logger.warning("Invalid product list action value: %s", value)
        return

    project_id, idea_num_str, run_id = parts
    try:
        idea_number = int(idea_num_str)
    except ValueError:
        logger.warning("Invalid idea number in product value: %s", value)
        return

    send_tool = SlackSendMessageTool()
    client = _get_slack_client()

    if action_id.startswith("product_confluence_"):
        _handle_confluence_publish(
            run_id, idea_number, user_id, channel, thread_ts,
            send_tool, client,
        )
    elif action_id.startswith("product_jira_skeleton_"):
        _handle_jira_skeleton(
            run_id, idea_number, user_id, channel, thread_ts,
            send_tool, client,
        )
    elif action_id.startswith("product_jira_epics_"):
        _handle_jira_epics(
            run_id, idea_number, user_id, channel, thread_ts,
            send_tool, client,
        )
    elif action_id.startswith("product_jira_subtasks_"):
        _handle_jira_subtasks(
            run_id, idea_number, user_id, channel, thread_ts,
            send_tool, client,
        )
    elif action_id.startswith("product_view_"):
        _handle_view_details(
            run_id, idea_number, user_id, channel, thread_ts,
            send_tool, client,
        )
    else:
        logger.warning("Unknown product action_id: %s", action_id)


# ---------------------------------------------------------------------------
# Individual action handlers
# ---------------------------------------------------------------------------


def _handle_confluence_publish(
    run_id: str,
    idea_number: int,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Publish a completed PRD to Confluence."""
    _ack(client, channel, thread_ts, user_id,
         f":globe_with_meridians: Publishing product #{idea_number} to Confluence…")

    def _do_publish():
        try:
            from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                find_run_any_status,
            )
            doc = find_run_any_status(run_id)
            if not doc:
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=f"<@{user_id}> :x: Could not find product (run `{run_id[:8]}…`).",
                )
                return

            from crewai_productfeature_planner.apis.prd.service import (
                restore_prd_state,
            )
            from crewai_productfeature_planner.flows.prd_flow import PRDFlow

            flow = PRDFlow()
            flow.state.run_id = run_id
            flow.state.idea = doc.get("idea", "")

            restored = restore_prd_state(run_id)
            if restored:
                idea, draft, exec_summary, requirements_breakdown, breakdown_history, refinement_history = restored
                flow.state.idea = idea
                flow.state.draft = draft
                flow.state.iteration = max(
                    (s.iteration for s in draft.sections), default=0,
                )
                flow.state.executive_summary = exec_summary
                flow.state.requirements_breakdown = requirements_breakdown
                flow.state.breakdown_history = breakdown_history
                if requirements_breakdown:
                    flow.state.requirements_broken_down = True
                if exec_summary.latest_content:
                    flow.state.finalized_idea = exec_summary.latest_content
                if refinement_history:
                    flow.state.idea_refined = True
                    flow.state.refinement_history = refinement_history
                    latest = refinement_history[-1]
                    if latest.get("idea"):
                        flow.state.idea = latest["idea"]
                elif exec_summary.iterations:
                    flow.state.idea_refined = True
                flow.state.final_prd = draft.assemble()

            # Fallback: if MongoDB sections were empty (older runs
            # stored content only on disk), try the on-disk output file.
            if len(flow.state.final_prd) < 100:
                import os
                output_file = doc.get("output_file", "")
                if output_file and os.path.isfile(output_file):
                    try:
                        prd_text = open(output_file, encoding="utf-8").read()  # noqa: SIM115
                        if prd_text:
                            flow.state.final_prd = prd_text
                    except OSError:
                        pass

            from crewai_productfeature_planner.orchestrator import (
                build_post_completion_crew,
            )
            from crewai_productfeature_planner.scripts.retry import (
                crew_kickoff_with_retry,
            )
            from crewai_productfeature_planner.orchestrator._helpers import (
                _has_confluence_credentials,
                _has_gemini_credentials,
            )

            if not (_has_confluence_credentials() and _has_gemini_credentials()):
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=(
                        f"<@{user_id}> :warning: Missing Confluence or Gemini "
                        "credentials. Please configure them first."
                    ),
                )
                return

            # Heartbeat: post crew step progress to Slack thread.
            def _progress(step_msg: str) -> None:
                try:
                    send_tool.run(
                        channel=channel, thread_ts=thread_ts,
                        text=f":gear: {step_msg}",
                    )
                except Exception:  # noqa: BLE001
                    pass

            crew = build_post_completion_crew(
                flow, progress_callback=_progress, confluence_only=True,
            )
            if crew is None:
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=f"<@{user_id}> :warning: Could not build Confluence publish crew.",
                )
                return

            result = crew_kickoff_with_retry(crew, step_label="confluence_publish")

            from crewai_productfeature_planner.flows._finalization import (
                persist_post_completion,
            )
            persist_post_completion(flow, result)

            conf_url = getattr(flow.state, "confluence_url", "")
            if conf_url:
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=(
                        f"<@{user_id}> :white_check_mark: Published to Confluence!\n"
                        f"<{conf_url}|View on Confluence>"
                    ),
                )
            else:
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=f"<@{user_id}> :white_check_mark: Confluence publish completed for product #{idea_number}.",
                )

            # Offer Jira skeleton creation as the next step.
            from crewai_productfeature_planner.orchestrator._helpers import (
                _has_jira_credentials,
            )
            if _has_jira_credentials():
                from crewai_productfeature_planner.apis.slack.blocks import (
                    jira_only_blocks,
                )
                jira_blocks = jira_only_blocks(run_id)
                if client and jira_blocks:
                    try:
                        client.chat_postMessage(
                            channel=channel,
                            thread_ts=thread_ts,
                            blocks=jira_blocks,
                            text="Create Jira Skeleton",
                        )
                    except Exception as exc:
                        logger.debug(
                            "Jira next-step button post failed: %s", exc,
                        )
        except Exception as exc:
            logger.error("Confluence publish failed for run_id=%s: %s", run_id, exc)
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Confluence publish failed: {exc}",
            )

    threading.Thread(target=_do_publish, daemon=True).start()


def _handle_jira_skeleton(
    run_id: str,
    idea_number: int,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Generate and present Jira skeleton for review.

    If the skeleton has already been generated and is awaiting approval
    (``jira_phase == "skeleton_pending"``), show the existing skeleton
    with approval + regenerate buttons instead of re-running the LLM.
    """
    # Check if a skeleton already exists and is pending approval.
    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
        find_run_any_status,
        get_jira_skeleton,
    )

    doc = find_run_any_status(run_id)
    jira_phase = (doc.get("jira_phase") or "") if doc else ""

    if jira_phase == "skeleton_pending":
        existing_skeleton = get_jira_skeleton(run_id)
        if existing_skeleton:
            logger.info(
                "[JiraSkeleton] Showing existing skeleton for run_id=%s (%d chars)",
                run_id, len(existing_skeleton),
            )
            _ack(client, channel, thread_ts, user_id,
                 f":clipboard: Here's the Jira skeleton for product #{idea_number} — review and approve or regenerate.")

            from crewai_productfeature_planner.apis.slack.blocks import (
                jira_skeleton_approval_blocks,
            )
            blocks = jira_skeleton_approval_blocks(run_id, existing_skeleton)
            if client:
                try:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        blocks=blocks,
                        text="Jira skeleton ready for review",
                    )
                except Exception as exc:
                    logger.error("Failed to post skeleton blocks: %s", exc)
                    send_tool.run(
                        channel=channel, thread_ts=thread_ts,
                        text=(
                            f"<@{user_id}> :clipboard: *Jira Skeleton:*\n"
                            f"{existing_skeleton[:2800]}\n\n"
                            "Approve or regenerate via the buttons above."
                        ),
                    )
            return

    # No existing skeleton — generate a new one.
    if jira_phase == "skeleton_pending":
        logger.warning(
            "[JiraSkeleton] jira_phase=skeleton_pending but no skeleton in MongoDB "
            "for run_id=%s — regenerating",
            run_id,
        )
        _ack(client, channel, thread_ts, user_id,
             f":clipboard: Jira skeleton for product #{idea_number} needs to be regenerated — starting now…")
    else:
        _ack(client, channel, thread_ts, user_id,
             f":clipboard: Generating Jira skeleton for product #{idea_number}…")

    def _do_skeleton():
        try:
            _run_jira_phase(
                run_id, "skeleton", user_id, channel, thread_ts, send_tool,
            )
        except Exception as exc:
            logger.error("Jira skeleton failed for run_id=%s: %s", run_id, exc)
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Jira skeleton generation failed: {exc}",
            )

    threading.Thread(target=_do_skeleton, daemon=True).start()


def _handle_jira_epics(
    run_id: str,
    idea_number: int,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Create Jira Epics & Stories."""
    _ack(client, channel, thread_ts, user_id,
         f":jigsaw: Creating Jira Epics & Stories for product #{idea_number}…")

    def _do_epics():
        try:
            _run_jira_phase(
                run_id, "epics_stories", user_id, channel, thread_ts, send_tool,
            )
        except Exception as exc:
            logger.error("Jira epics/stories failed for run_id=%s: %s", run_id, exc)
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Jira Epics & Stories creation failed: {exc}",
            )

    threading.Thread(target=_do_epics, daemon=True).start()


def _handle_jira_subtasks(
    run_id: str,
    idea_number: int,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Create Jira Sub-tasks."""
    _ack(client, channel, thread_ts, user_id,
         f":hammer_and_wrench: Creating Jira Sub-tasks for product #{idea_number}…")

    def _do_subtasks():
        try:
            _run_jira_phase(
                run_id, "subtasks", user_id, channel, thread_ts, send_tool,
            )
        except Exception as exc:
            logger.error("Jira subtasks failed for run_id=%s: %s", run_id, exc)
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Jira Sub-task creation failed: {exc}",
            )

    threading.Thread(target=_do_subtasks, daemon=True).start()


# ---------------------------------------------------------------------------
# Jira ticket type resolution
# ---------------------------------------------------------------------------

# Jira issue type names vary slightly between Jira Cloud and Server.
# This map normalises known variants to the canonical display names.
_JIRA_TYPE_NORMALISE: dict[str, str] = {
    "Task": "Sub-task",
    "task": "Sub-task",
    "sub-task": "Sub-task",
    "subtask": "Sub-task",
    "Sub-Task": "Sub-task",
    "story": "Story",
    "epic": "Epic",
}


def _resolve_unknown_ticket_types(
    run_id: str,
    tickets: list[dict],
) -> list[dict]:
    """If any tickets have ``"unknown"`` type, look up actual types from
    Jira and update both the in-memory list and the delivery record.

    Also normalises known type variants (e.g. ``"Task"`` → ``"Sub-task"``).
    """
    # Check if any tickets need resolution
    needs_lookup = any(
        (t.get("type") or "").strip().lower() in ("unknown", "")
        for t in tickets
    )

    type_map: dict[str, str] = {}
    if needs_lookup:
        try:
            from crewai_productfeature_planner.tools.jira import (
                search_jira_issues,
            )
            for issue in search_jira_issues(run_id):
                type_map[issue["issue_key"]] = issue["issue_type"]
            logger.info(
                "[ViewDetails] Jira lookup for run_id=%s returned %d issues "
                "with types: %s",
                run_id, len(type_map),
                {k: v for k, v in type_map.items()},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[ViewDetails] Jira type lookup failed for run_id=%s: %s",
                run_id, exc,
            )

    # Apply resolved types + normalisation
    updated = False
    for t in tickets:
        raw_type = (t.get("type") or "Other").strip()
        key = t.get("key", "")

        # First try live Jira lookup
        if raw_type.lower() in ("unknown", "") and key in type_map:
            resolved = type_map[key]
            t["type"] = _JIRA_TYPE_NORMALISE.get(resolved, resolved)
            updated = True
        elif raw_type in _JIRA_TYPE_NORMALISE:
            t["type"] = _JIRA_TYPE_NORMALISE[raw_type]
            updated = True

    # Persist corrected types back to MongoDB
    if updated:
        try:
            from crewai_productfeature_planner.mongodb.product_requirements import (
                upsert_delivery_record,
            )
            upsert_delivery_record(run_id, jira_tickets=tickets)
            logger.info(
                "[ViewDetails] Updated ticket types in delivery record "
                "for run_id=%s",
                run_id,
            )
        except Exception:  # noqa: BLE001
            pass

    return tickets


def _handle_view_details(
    run_id: str,
    idea_number: int,
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
    client,
) -> None:
    """Show delivery details for a fully-delivered product."""
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_run_any_status,
        )
        from crewai_productfeature_planner.mongodb.product_requirements import (
            get_delivery_record,
        )

        doc = find_run_any_status(run_id)
        record = get_delivery_record(run_id)

        if not doc:
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :x: Could not find product (run `{run_id[:8]}…`).",
            )
            return

        idea_text = doc.get("idea", "Untitled")

        # ── Confluence URL — pull directly from productRequirements ──
        doc_conf_url = (doc.get("confluence_url") or "").strip()
        rec_conf_url = ((record.get("confluence_url") if record else "") or "").strip()
        conf_url = doc_conf_url or rec_conf_url
        conf_published = bool(
            (record and record.get("confluence_published"))
            or conf_url
        )
        logger.info(
            "[ViewDetails] run_id=%s doc_conf_url=%r rec_conf_url=%r "
            "conf_url=%r conf_published=%s record_exists=%s",
            run_id, doc_conf_url, rec_conf_url,
            conf_url, conf_published, record is not None,
        )

        # ── Jira tickets — resolve unknown types from Jira API ──
        jira_tickets = list((record.get("jira_tickets") or []) if record else [])
        jira_tickets = _resolve_unknown_ticket_types(run_id, jira_tickets)

        lines = [f"<@{user_id}> :package: *Product #{idea_number} Details*\n"]
        lines.append(f"> _{idea_text}_\n")

        if conf_url:
            lines.append(
                f":globe_with_meridians: *Confluence:* <{conf_url}|{conf_url}>"
            )
        elif conf_published:
            lines.append(":globe_with_meridians: *Confluence:* Published (URL not available)")
        else:
            lines.append(":globe_with_meridians: *Confluence:* Not published")

        if jira_tickets:
            type_counts: dict[str, int] = {}
            for t in jira_tickets:
                ticket_type = (t.get("type") or "Other").strip()
                type_counts[ticket_type] = type_counts.get(ticket_type, 0) + 1

            # Build readable summary with counts
            _PLURALS = {"Epic": "Epics", "Story": "Stories", "Sub-task": "Sub-tasks"}
            count_parts: list[str] = []
            for label in ("Epic", "Story", "Sub-task"):
                if label in type_counts:
                    c = type_counts[label]
                    plural = _PLURALS[label] if c != 1 else label
                    count_parts.append(f"{c} {plural}")
            # Include any remaining types not in the standard list
            for label, count in type_counts.items():
                if label not in ("Epic", "Story", "Sub-task"):
                    count_parts.append(f"{count} {label.rstrip('s')}{'s' if count != 1 else ''}")

            total = len(jira_tickets)
            summary_text = ", ".join(count_parts) if count_parts else f"{total} ticket{'s' if total != 1 else ''}"
            lines.append(f":ticket: *Jira Tickets:* {total} total ({summary_text})")
        else:
            lines.append(":ticket: *Jira Tickets:* No tickets created")

        send_tool.run(
            channel=channel, thread_ts=thread_ts,
            text="\n".join(lines),
        )
    except Exception as exc:
        logger.error("View details failed for run_id=%s: %s", run_id, exc)
        send_tool.run(
            channel=channel, thread_ts=thread_ts,
            text=f"<@{user_id}> :x: Failed to load product details: {exc}",
        )


# ---------------------------------------------------------------------------
# Shared Jira phase runner
# ---------------------------------------------------------------------------


def _run_jira_phase(
    run_id: str,
    phase: str,  # "skeleton" | "epics_stories" | "subtasks"
    user_id: str,
    channel: str,
    thread_ts: str,
    send_tool,
) -> None:
    """Run a specific Jira phase for a completed product.

    Reconstructs the minimal PRD flow state from MongoDB and executes
    the requested Jira stage.
    """
    from crewai_productfeature_planner.apis.prd.service import restore_prd_state
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow
    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
        find_run_any_status,
    )
    from crewai_productfeature_planner.orchestrator._jira import (
        _check_jira_prerequisites,
        _persist_jira_phase,
        build_jira_epics_stories_stage,
        build_jira_skeleton_stage,
        build_jira_subtasks_stage,
    )
    from crewai_productfeature_planner.scripts.retry import (
        crew_kickoff_with_retry,
    )

    doc = find_run_any_status(run_id)
    if not doc:
        send_tool.run(
            channel=channel, thread_ts=thread_ts,
            text=f"<@{user_id}> :x: Could not find product (run `{run_id[:8]}…`).",
        )
        return

    # Reconstruct flow state from MongoDB.
    # ``restore_prd_state`` returns a 6-tuple; we unpack it and apply
    # each field individually because ``Flow.state`` is a read-only
    # property (no setter).
    flow = PRDFlow()
    flow.state.run_id = run_id
    flow.state.idea = doc.get("idea", "")

    restored = restore_prd_state(run_id)
    if restored:
        idea, draft, exec_summary, requirements_breakdown, breakdown_history, refinement_history = restored
        flow.state.idea = idea
        flow.state.draft = draft
        flow.state.iteration = max(
            (s.iteration for s in draft.sections), default=0,
        )
        flow.state.executive_summary = exec_summary
        flow.state.requirements_breakdown = requirements_breakdown
        flow.state.breakdown_history = breakdown_history
        if requirements_breakdown:
            flow.state.requirements_broken_down = True
        if exec_summary.latest_content:
            flow.state.finalized_idea = exec_summary.latest_content
        if refinement_history:
            flow.state.idea_refined = True
            flow.state.refinement_history = refinement_history
            latest = refinement_history[-1]
            if latest.get("idea"):
                flow.state.idea = latest["idea"]
        elif exec_summary.iterations:
            flow.state.idea_refined = True
        # Assemble the final PRD from the restored draft so that
        # ``_check_jira_prerequisites`` sees a non-empty ``final_prd``.
        flow.state.final_prd = draft.assemble()

    # Fallback: if MongoDB sections were empty (older completed runs
    # stored content only on disk), try the on-disk output file.
    if len(flow.state.final_prd) < 100:
        import os
        output_file = doc.get("output_file", "")
        if output_file and os.path.isfile(output_file):
            try:
                prd_text = open(output_file, encoding="utf-8").read()   # noqa: SIM115
                if prd_text:
                    flow.state.final_prd = prd_text
                    logger.info(
                        "[JiraPhase] Loaded PRD from disk: %s (%d chars)",
                        output_file, len(prd_text),
                    )
            except OSError as exc:
                logger.warning("[JiraPhase] Failed to read output file: %s", exc)

    # Restore delivery-related fields from the MongoDB document.
    flow.state.confluence_url = doc.get("confluence_url") or ""
    flow.state.jira_phase = doc.get("jira_phase") or ""

    # The interactive Jira flow should not require Confluence — a user
    # can create Jira tickets for a PRD that was never published.
    skip_reason = _check_jira_prerequisites(flow, require_confluence=False)
    if skip_reason:
        send_tool.run(
            channel=channel, thread_ts=thread_ts,
            text=f"<@{user_id}> :warning: Cannot create Jira tickets: {skip_reason}",
        )
        return

    if phase == "skeleton":
        flow.state.jira_phase = ""  # Reset to allow skeleton generation
        stage = build_jira_skeleton_stage(flow, require_confluence=False)
        if not stage.should_skip():
            result = stage.run()
            stage.apply(result)

            skeleton = flow.state.jira_skeleton
            if skeleton:
                # Post skeleton for review using Block Kit
                from crewai_productfeature_planner.apis.slack.blocks import (
                    jira_skeleton_approval_blocks,
                )
                blocks = jira_skeleton_approval_blocks(run_id, skeleton)
                from crewai_productfeature_planner.tools.slack_tools import (
                    _get_slack_client,
                )
                client = _get_slack_client()
                if client:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        blocks=blocks,
                        text="Jira skeleton ready for review",
                    )
                else:
                    send_tool.run(
                        channel=channel, thread_ts=thread_ts,
                        text=(
                            f"<@{user_id}> :clipboard: *Jira Skeleton:*\n"
                            f"{skeleton[:2800]}\n\n"
                            "Approve or reject via the buttons above."
                        ),
                    )
            else:
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=f"<@{user_id}> :warning: Skeleton generation produced no output.",
                )
        else:
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :information_source: Jira skeleton stage was skipped (prerequisites not met).",
            )

    elif phase == "epics_stories":
        if flow.state.jira_phase != "skeleton_approved":
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=(
                    f"<@{user_id}> :warning: Cannot create Epics & Stories — "
                    "the skeleton must be approved first. "
                    "Current phase: *" + (flow.state.jira_phase or "not started") + "*"
                ),
            )
            return

        stage = build_jira_epics_stories_stage(flow, require_confluence=False)
        if not stage.should_skip():
            result = stage.run()
            stage.apply(result)

            output = flow.state.jira_epics_stories_output
            if output:
                from crewai_productfeature_planner.apis.slack.blocks import (
                    jira_review_blocks,
                )
                blocks = jira_review_blocks(run_id, output)
                from crewai_productfeature_planner.tools.slack_tools import (
                    _get_slack_client,
                )
                client = _get_slack_client()
                if client:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        blocks=blocks,
                        text="Jira Epics & Stories created — review before sub-tasks",
                    )
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=(
                        f"<@{user_id}> :white_check_mark: Jira Epics & Stories created! "
                        "Review the output above. When ready, click "
                        "*Publish Sub-tasks* from the product list."
                    ),
                )
            else:
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=f"<@{user_id}> :warning: Epics & Stories stage produced no output.",
                )
        else:
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :information_source: Epics & Stories stage was skipped.",
            )

    elif phase == "subtasks":
        if flow.state.jira_phase not in ("epics_stories_done", "subtasks_ready"):
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=(
                    f"<@{user_id}> :warning: Cannot create Sub-tasks — "
                    "Epics & Stories must be created first. "
                    "Current phase: *" + (flow.state.jira_phase or "not started") + "*"
                ),
            )
            return

        # Mark subtasks as ready
        flow.state.jira_phase = "subtasks_ready"
        _persist_jira_phase(run_id, "subtasks_ready")

        stage = build_jira_subtasks_stage(flow, require_confluence=False)
        if not stage.should_skip():
            result = stage.run()
            # Capture raw subtask output before apply merges it
            subtasks_output = result.output
            stage.apply(result)

            # Override phase to subtasks_pending (stage.apply sets subtasks_done)
            flow.state.jira_phase = "subtasks_pending"
            _persist_jira_phase(run_id, "subtasks_pending")

            if subtasks_output:
                from crewai_productfeature_planner.apis.slack.blocks import (
                    jira_subtask_review_blocks,
                )
                blocks = jira_subtask_review_blocks(run_id, subtasks_output)
                from crewai_productfeature_planner.tools.slack_tools import (
                    _get_slack_client,
                )
                client = _get_slack_client()
                if client:
                    client.chat_postMessage(
                        channel=channel,
                        thread_ts=thread_ts,
                        blocks=blocks,
                        text="Jira Sub-tasks created — review before finalising",
                    )
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=(
                        f"<@{user_id}> :hammer_and_wrench: Jira Sub-tasks created! "
                        "Review the output above and approve or regenerate."
                    ),
                )
            else:
                send_tool.run(
                    channel=channel, thread_ts=thread_ts,
                    text=f"<@{user_id}> :warning: Sub-tasks stage produced no output.",
                )
        else:
            send_tool.run(
                channel=channel, thread_ts=thread_ts,
                text=f"<@{user_id}> :information_source: Sub-tasks stage was skipped.",
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ack(client, channel: str, thread_ts: str, user_id: str, text: str) -> None:
    """Post a quick acknowledgement message."""
    if client and channel:
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"<@{user_id}> {text}",
            )
        except Exception as exc:
            logger.error("Product action ack failed: %s", exc)
