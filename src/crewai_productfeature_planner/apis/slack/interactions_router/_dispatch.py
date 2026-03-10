"""Slack interactions dispatch — router, endpoint, constants, helpers."""

from __future__ import annotations

import json
import logging
from functools import partial
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from crewai_productfeature_planner.apis.slack.verify import verify_slack_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Slack Interactions"])


def _with_team(team_id: str, fn, *args, **kwargs):
    """Run *fn* with :data:`current_team_id` set so downstream
    ``_get_slack_client()`` calls resolve the correct OAuth token.
    """
    from crewai_productfeature_planner.tools.slack_tools import current_team_id
    current_team_id.set(team_id)
    return fn(*args, **kwargs)


# Action IDs we handle (must match blocks.py)
_KNOWN_ACTIONS = frozenset({
    "refinement_agent",
    "refinement_manual",
    "idea_approve",
    "idea_cancel",
    "requirements_approve",
    "requirements_cancel",
    "flow_cancel",
    "exec_summary_approve",
    "exec_summary_skip",
    "exec_summary_continue",
    "exec_summary_stop",
})

# Project session action IDs — handled by the session manager
_SESSION_ACTIONS = frozenset({
    "project_create",
    "project_continue",
    "project_switch",
    "session_end",
})

# Memory configuration action IDs
_MEMORY_ACTIONS = frozenset({
    "memory_configure",
    "memory_idea",
    "memory_knowledge",
    "memory_tools",
    "memory_view",
    "memory_done",
})

# Next-step suggestion feedback action IDs
_NEXT_STEP_ACTIONS = frozenset({
    "next_step_accept",
    "next_step_dismiss",
})

# Restart PRD confirmation action IDs
_RESTART_PRD_ACTIONS = frozenset({
    "restart_prd_confirm",
    "restart_prd_cancel",
})

# Archive idea confirmation action IDs
_ARCHIVE_ACTIONS = frozenset({
    "archive_idea_confirm",
    "archive_idea_cancel",
})

# Flow retry (resume paused flow from Retry button)
_RETRY_ACTIONS = frozenset({
    "flow_retry",
})

# Jira phased-approval actions (from product list skeleton / review blocks)
_JIRA_APPROVAL_ACTIONS = frozenset({
    "jira_skeleton_approve",
    "jira_skeleton_reject",
    "jira_review_approve",
    "jira_review_skip",
    "jira_subtask_approve",
    "jira_subtask_reject",
})

# Post-completion delivery actions (Publish / Create Jira buttons)
_DELIVERY_ACTIONS = frozenset({
    "delivery_publish",
    "delivery_create_jira",
})


def _extract_payload(body: bytes) -> dict | None:
    """Parse the ``payload`` field from a Slack interaction POST.

    Slack sends ``application/x-www-form-urlencoded`` with a single
    ``payload`` key whose value is a JSON-encoded string.
    """
    try:
        parsed = parse_qs(body.decode("utf-8", errors="replace"))
        raw = parsed.get("payload", [None])[0]
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.error("Failed to parse Slack interaction payload: %s", exc)
    return None


def _ack_action(action_id: str, user_name: str) -> str:
    """Return a human-friendly acknowledgement for an action."""
    labels = {
        "refinement_agent": ":robot_face: Agent refinement selected",
        "refinement_manual": ":pencil2: Manual refinement selected",
        "idea_approve": ":white_check_mark: Idea approved",
        "idea_cancel": ":no_entry_sign: Flow cancelled",
        "requirements_approve": ":white_check_mark: Requirements approved",
        "requirements_cancel": ":no_entry_sign: Flow cancelled",
        "flow_cancel": ":no_entry_sign: Flow cancelled",
        "exec_summary_approve": ":white_check_mark: Executive summary approved",
        "exec_summary_skip": ":fast_forward: Initial guidance skipped",
        "exec_summary_continue": ":arrow_forward: Continuing to section drafting",
        "exec_summary_stop": ":stop_button: Stopped after executive summary",
        "project_create": ":heavy_plus_sign: Creating new project",
        "project_continue": ":arrow_forward: Continuing with project",
        "project_switch": ":twisted_rightwards_arrows: Switching project",
        "session_end": ":stop_button: Session ended",
        "memory_configure": ":brain: Configuring project memory",
        "memory_idea": ":bulb: Adding idea & iteration guardrails",
        "memory_knowledge": ":books: Adding knowledge entries",
        "memory_tools": ":wrench: Adding tool entries",
        "memory_view": ":mag: Viewing project memory",
        "memory_done": ":white_check_mark: Memory configuration done",
        "next_step_accept": ":white_check_mark: Suggestion accepted",
        "next_step_dismiss": ":x: Suggestion dismissed",
        "restart_prd_confirm": ":arrows_counterclockwise: PRD restart confirmed",
        "restart_prd_cancel": ":no_entry_sign: PRD restart cancelled",
        "archive_idea_confirm": ":file_folder: Idea archived",
        "archive_idea_cancel": ":no_entry_sign: Archive cancelled",
        "flow_retry": ":arrows_counterclockwise: Retrying PRD flow",
        "jira_skeleton_approve": ":white_check_mark: Jira skeleton approved — creating Epics & Stories",
        "jira_skeleton_reject": ":arrows_counterclockwise: Regenerating Jira skeleton",
        "jira_review_approve": ":white_check_mark: Epics & Stories approved — creating sub-tasks",
        "jira_review_skip": ":fast_forward: Sub-tasks skipped",
        "jira_subtask_approve": ":white_check_mark: Sub-tasks approved — Jira ticketing complete",
        "jira_subtask_reject": ":arrows_counterclockwise: Regenerating Jira sub-tasks",
        "delivery_publish": ":outbox_tray: Publishing to Confluence",
        "delivery_create_jira": ":jira: Creating Jira skeleton",
    }
    label = labels.get(action_id, action_id)
    # Dynamic action IDs for idea list buttons
    if action_id.startswith("idea_resume_"):
        label = f":arrow_forward: Resuming idea #{action_id.removeprefix('idea_resume_')}"
    elif action_id.startswith("idea_restart_"):
        label = f":arrows_counterclockwise: Restarting idea #{action_id.removeprefix('idea_restart_')}"
    elif action_id.startswith("idea_archive_"):
        label = f":file_folder: Archiving idea #{action_id.removeprefix('idea_archive_')}"
    elif action_id.startswith("product_confluence_"):
        label = ":confluence: Publishing to Confluence"
    elif action_id.startswith("product_jira_skeleton_"):
        label = ":jira: Reviewing Jira skeleton"
    elif action_id.startswith("product_jira_epics_"):
        label = ":jira: Publishing Jira epics & stories"
    elif action_id.startswith("product_jira_subtasks_"):
        label = ":jira: Publishing Jira sub-tasks"
    elif action_id.startswith("product_view_"):
        label = ":mag: Viewing product details"
    elif action_id.startswith("product_archive_"):
        label = ":file_folder: Archiving product"
    return f"{label} by {user_name}"


def _post_ack(channel: str, thread_ts: str, text: str) -> None:
    """Post a brief acknowledgement message to Slack."""
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if client and channel:
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text,
            )
        except Exception as exc:
            logger.error("Ack post failed: %s", exc)


@router.post(
    "/slack/interactions",
    tags=["Slack Interactions"],
    summary="Slack Interactivity webhook",
    response_description="Interaction acknowledged",
    description=(
        "Handles inbound interactive payloads from Slack — button clicks, "
        "menu selections, and modal submissions.\n\n"
        "This is the **Request URL** configured under *Interactivity & "
        "Shortcuts* in the Slack app settings.\n\n"
        "Slack sends ``application/x-www-form-urlencoded`` with a single "
        "``payload`` field containing a JSON-encoded interaction payload.\n\n"
        "**Supported payload types:**\n\n"
        "- ``block_actions`` — Button clicks on Block Kit messages. Routes "
        "decisions (refinement mode, idea approval, requirements approval, "
        "cancellation) to the interactive flow handler.\n"
        "- ``view_submission`` — Modal form submissions (reserved for "
        "future use).\n\n"
        "**Action IDs:**\n\n"
        "| Action ID | Description |\n"
        "|---|---|\n"
        "| ``refinement_agent`` | Choose agent-driven idea refinement |\n"
        "| ``refinement_manual`` | Choose manual idea refinement (user types feedback in thread) |\n"
        "| ``idea_approve`` | Approve the refined idea and proceed to requirements |\n"
        "| ``idea_cancel`` | Cancel the flow after idea refinement |\n"
        "| ``requirements_approve`` | Approve the requirements breakdown and start PRD generation |\n"
        "| ``requirements_cancel`` | Cancel the flow after requirements breakdown |\n"
        "| ``flow_cancel`` | Cancel the flow at any point |\n\n"
        "Each button's ``value`` field carries the ``run_id`` to correlate "
        "the click with the correct interactive flow session.\n\n"
        "All payloads are verified using ``verify_slack_request`` "
        "(HMAC-SHA256 signing secret). Slack requires a response within "
        "3 seconds — processing happens asynchronously."
    ),
    dependencies=[Depends(verify_slack_request)],
    responses={
        200: {
            "description": "Interaction acknowledged.",
            "content": {
                "application/json": {
                    "example": {"ok": True}
                }
            },
        },
        400: {"description": "Invalid or unparseable payload."},
    },
)
async def slack_interactions(request: Request) -> JSONResponse:
    """Handle inbound interactive payloads from Slack.

    Parses the ``payload`` field, routes ``block_actions`` to the
    interactive handler, and returns an immediate 200 acknowledgement
    (Slack requires a response within 3 seconds).
    """
    body = await request.body()
    payload = _extract_payload(body)
    if not payload:
        return JSONResponse({"error": "invalid payload"}, status_code=400)

    payload_type = payload.get("type", "")

    # Resolve the workspace team_id so downstream Slack API calls use
    # the correct OAuth token from MongoDB.
    _team_id = payload.get("team", {}).get("id", "")

    # ------------------------------------------------------------------
    # block_actions — button clicks
    # ------------------------------------------------------------------
    if payload_type == "block_actions":
        actions = payload.get("actions", [])
        if not actions:
            return JSONResponse({"ok": True})

        action = actions[0]
        action_id = action.get("action_id", "")
        run_id = action.get("value", "")
        user_info = payload.get("user", {})
        user_id = user_info.get("id", "")
        user_name = user_info.get("username", user_id)

        # ── Project session actions ──
        is_project_select = action_id.startswith("project_select_")
        if action_id in _SESSION_ACTIONS or is_project_select:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack project action: action=%s user=%s value=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._project_handler import (
                _handle_project_action,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_project_action,
                    action_id, run_id, user_id, channel_id, thread_ts,
                ),
            )

            if channel_id:
                ack_text = _ack_action(action_id, user_name)
                loop.run_in_executor(
                    None,
                    partial(_with_team, _team_id, _post_ack, channel_id, thread_ts, ack_text),
                )

            return JSONResponse({"ok": True})

        # ── Memory configuration actions ──
        if action_id in _MEMORY_ACTIONS:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack memory action: action=%s user=%s",
                action_id, user_name,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._memory_handler import (
                _handle_memory_action,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_memory_action,
                    action_id, user_id, channel_id, thread_ts,
                ),
            )

            return JSONResponse({"ok": True})

        # ── Next-step suggestion feedback actions ──
        if action_id in _NEXT_STEP_ACTIONS:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack next-step feedback: action=%s user=%s value=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._next_step_handler import (
                _handle_next_step_feedback,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_next_step_feedback,
                    action_id, run_id, user_id, channel_id, thread_ts,
                ),
            )

            return JSONResponse({"ok": True})

        # ── Idea list resume / restart / archive actions ──
        is_idea_resume = action_id.startswith("idea_resume_")
        is_idea_restart = action_id.startswith("idea_restart_")
        is_idea_archive = action_id.startswith("idea_archive_")
        if is_idea_resume or is_idea_restart or is_idea_archive:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack idea list action: action=%s user=%s value=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._idea_list_handler import (
                _handle_idea_list_action,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_idea_list_action,
                    action_id, run_id, user_id, channel_id, thread_ts,
                ),
            )

            return JSONResponse({"ok": True})

        # ── Product list delivery actions ──
        _PRODUCT_PREFIXES = (
            "product_confluence_", "product_jira_skeleton_",
            "product_jira_epics_", "product_jira_subtasks_",
            "product_view_", "product_archive_",
        )
        if any(action_id.startswith(p) for p in _PRODUCT_PREFIXES):
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack product list action: action=%s user=%s value=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_product_list_action,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_product_list_action,
                    action_id, run_id, user_id, channel_id, thread_ts,
                ),
            )

            return JSONResponse({"ok": True})

        # ── Jira phased-approval actions (skeleton / review) ──
        if action_id in _JIRA_APPROVAL_ACTIONS:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack Jira approval action: action=%s user=%s run_id=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler import (
                _handle_jira_approval_action,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_jira_approval_action,
                    action_id, run_id, user_id, channel_id, thread_ts,
                ),
            )

            if channel_id:
                ack_text = _ack_action(action_id, user_name)
                loop.run_in_executor(
                    None,
                    partial(_with_team, _team_id, _post_ack, channel_id, thread_ts, ack_text),
                )

            return JSONResponse({"ok": True})

        # ── Restart PRD confirmation actions ──
        if action_id in _RESTART_PRD_ACTIONS:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack restart PRD action: action=%s user=%s run_id=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._restart_handler import (
                _handle_restart_prd_action,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_restart_prd_action,
                    action_id, run_id, user_id, channel_id, thread_ts,
                ),
            )

            if channel_id:
                ack_text = _ack_action(action_id, user_name)
                loop.run_in_executor(
                    None,
                    partial(_with_team, _team_id, _post_ack, channel_id, thread_ts, ack_text),
                )

            return JSONResponse({"ok": True})

        # ── Archive idea confirmation actions ──
        if action_id in _ARCHIVE_ACTIONS:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack archive idea action: action=%s user=%s run_id=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._archive_handler import (
                _handle_archive_action,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_archive_action,
                    action_id, run_id, user_id, channel_id, thread_ts,
                ),
            )

            if channel_id:
                ack_text = _ack_action(action_id, user_name)
                loop.run_in_executor(
                    None,
                    partial(_with_team, _team_id, _post_ack, channel_id, thread_ts, ack_text),
                )

            return JSONResponse({"ok": True})

        # ── Flow retry (resume paused flow) ──
        if action_id in _RETRY_ACTIONS:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack flow retry action: action=%s user=%s run_id=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._retry_handler import (
                _handle_flow_retry,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_flow_retry,
                    run_id, user_id, channel_id, thread_ts,
                ),
            )

            if channel_id:
                ack_text = _ack_action(action_id, user_name)
                loop.run_in_executor(
                    None,
                    partial(_with_team, _team_id, _post_ack, channel_id, thread_ts, ack_text),
                )

            return JSONResponse({"ok": True})

        # ── Delivery actions (Publish / Create Jira buttons) ──
        if action_id in _DELIVERY_ACTIONS:
            channel_info = payload.get("channel", {})
            channel_id = channel_info.get("id", "")
            message = payload.get("message", {})
            thread_ts = message.get("thread_ts") or message.get("ts", "")

            logger.info(
                "Slack delivery action: action=%s user=%s run_id=%s",
                action_id, user_name, run_id,
            )

            import asyncio

            from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
                _handle_delivery_action,
            )

            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _handle_delivery_action,
                    action_id, run_id, user_id, channel_id, thread_ts,
                ),
            )

            if channel_id:
                ack_text = _ack_action(action_id, user_name)
                loop.run_in_executor(
                    None,
                    partial(_with_team, _team_id, _post_ack, channel_id, thread_ts, ack_text),
                )

            return JSONResponse({"ok": True})

        # ── Flow actions ──
        if action_id not in _KNOWN_ACTIONS:
            logger.debug("Unknown action_id: %s", action_id)
            return JSONResponse({"ok": True})

        if not run_id:
            logger.warning("Action %s missing run_id in value", action_id)
            return JSONResponse({"ok": True})

        logger.info(
            "Slack interaction: action=%s run_id=%s user=%s",
            action_id, run_id, user_name,
        )

        # Check non-interactive exec summary feedback gate first
        if action_id == "exec_summary_approve":
            from crewai_productfeature_planner.apis.slack._flow_handlers import (
                resolve_exec_feedback,
            )
            if resolve_exec_feedback(run_id, "approve"):
                channel_info = payload.get("channel", {})
                channel_id = channel_info.get("id", "")
                message = payload.get("message", {})
                thread_ts = message.get("thread_ts") or message.get("ts", "")
                if channel_id:
                    ack_text = _ack_action(action_id, user_name)
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(
                        None,
                        partial(
                            _with_team, _team_id,
                            _post_ack, channel_id, thread_ts, ack_text,
                        ),
                    )
                return JSONResponse({"ok": True})

        # Check exec summary completion gate (Phase 1 → Phase 2 pause)
        if action_id in ("exec_summary_continue", "exec_summary_stop"):
            from crewai_productfeature_planner.apis.slack._flow_handlers import (
                resolve_exec_completion,
            )
            if resolve_exec_completion(run_id, action_id):
                channel_info = payload.get("channel", {})
                channel_id = channel_info.get("id", "")
                message = payload.get("message", {})
                thread_ts = message.get("thread_ts") or message.get("ts", "")
                if channel_id:
                    ack_text = _ack_action(action_id, user_name)
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(
                        None,
                        partial(
                            _with_team, _team_id,
                            _post_ack, channel_id, thread_ts, ack_text,
                        ),
                    )
                return JSONResponse({"ok": True})

        # Check non-interactive requirements approval gate
        if action_id in ("requirements_approve", "requirements_cancel"):
            from crewai_productfeature_planner.apis.slack._flow_handlers import (
                resolve_requirements_approval,
            )
            if resolve_requirements_approval(run_id, action_id):
                channel_info = payload.get("channel", {})
                channel_id = channel_info.get("id", "")
                message = payload.get("message", {})
                thread_ts = message.get("thread_ts") or message.get("ts", "")
                if channel_id:
                    ack_text = _ack_action(action_id, user_name)
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(
                        None,
                        partial(
                            _with_team, _team_id,
                            _post_ack, channel_id, thread_ts, ack_text,
                        ),
                    )
                return JSONResponse({"ok": True})

        # Route to the interactive handler
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            resolve_interaction,
        )

        resolved = resolve_interaction(run_id, action_id, user_id)

        if not resolved:
            logger.warning(
                "No pending interactive run for run_id=%s (action=%s)",
                run_id, action_id,
            )
            # Still acknowledge to avoid Slack retries
            return JSONResponse({"ok": True})

        # Post an acknowledgement to the channel/thread
        channel_info = payload.get("channel", {})
        channel_id = channel_info.get("id", "")
        message = payload.get("message", {})
        thread_ts = message.get("thread_ts") or message.get("ts", "")

        if channel_id:
            ack_text = _ack_action(action_id, user_name)
            import asyncio
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    _with_team, _team_id,
                    _post_ack, channel_id, thread_ts, ack_text,
                ),
            )

        return JSONResponse({"ok": True})

    # ------------------------------------------------------------------
    # view_submission — modal forms (future)
    # ------------------------------------------------------------------
    if payload_type == "view_submission":
        logger.debug("view_submission received (not yet implemented)")
        return JSONResponse({"response_action": "clear"})

    logger.debug("Unhandled interaction type: %s", payload_type)
    return JSONResponse({"ok": True})
