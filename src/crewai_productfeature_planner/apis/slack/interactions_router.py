"""Slack Interactions API router.

Handles inbound interactive payloads from Slack — button clicks, menu
selections, and modal submissions.  This is the ``Request URL`` configured
under *Interactivity & Shortcuts* in the Slack app settings.

Slack sends a ``POST`` with ``Content-Type: application/x-www-form-urlencoded``
containing a single ``payload`` field whose value is a JSON string.

Supported payload types:

* **block_actions** — Button clicks on Block Kit messages.  Action IDs
  are mapped to flow decisions (refinement mode, idea approval,
  requirements approval, cancellation).
* **view_submission** — Modal form submissions (reserved for future use).

All payloads are verified using ``verify_slack_request`` (HMAC-SHA256
signing secret).
"""

from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from crewai_productfeature_planner.apis.slack.verify import verify_slack_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Slack Interactions"])

# Action IDs we handle (must match blocks.py)
_KNOWN_ACTIONS = frozenset({
    "refinement_agent",
    "refinement_manual",
    "idea_approve",
    "idea_cancel",
    "requirements_approve",
    "requirements_cancel",
    "flow_cancel",
})

# Project session action IDs — handled by the session manager
_SESSION_ACTIONS = frozenset({
    "project_create",
    "project_continue",
    "project_switch",
    "session_end",
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
        "project_create": ":heavy_plus_sign: Creating new project",
        "project_continue": ":arrow_forward: Continuing with project",
        "project_switch": ":twisted_rightwards_arrows: Switching project",
        "session_end": ":stop_button: Session ended",
    }
    label = labels.get(action_id, action_id)
    return f"{label} by {user_name}"


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
        "Each button’s ``value`` field carries the ``run_id`` to correlate "
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
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                _handle_project_action,
                action_id, run_id, user_id, channel_id, thread_ts,
            )

            if channel_id:
                ack_text = _ack_action(action_id, user_name)
                loop.run_in_executor(None, _post_ack, channel_id, thread_ts, ack_text)

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
                _post_ack,
                channel_id,
                thread_ts,
                ack_text,
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


def _handle_project_action(
    action_id: str,
    value: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a project-session button click in a background thread.

    Delegates to the session manager and posts Block Kit feedback.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_create_prompt_blocks,
        project_selection_blocks,
        session_ended_blocks,
        session_started_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        activate_project,
        deactivate_session,
        mark_pending_create,
    )
    from crewai_productfeature_planner.mongodb.project_config import (
        create_project,
        get_project,
        list_projects,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    def _post(blocks=None, text=""):
        try:
            kwargs: dict = {"channel": channel, "thread_ts": thread_ts, "text": text or "Project update"}
            if blocks:
                kwargs["blocks"] = blocks
            client.chat_postMessage(**kwargs)
        except Exception as exc:
            logger.error("Project action post failed: %s", exc)

    try:
        if action_id.startswith("project_select_"):
            # User selected an existing project
            project_id = action_id.removeprefix("project_select_")
            proj = get_project(project_id)
            if not proj:
                _post(text=":warning: Project not found. Please try again.")
                return
            pname = proj.get("name", "Unnamed")
            activate_project(
                user_id=user_id,
                channel=channel,
                project_id=project_id,
                project_name=pname,
            )
            _post(blocks=session_started_blocks(pname), text=f"Session started: {pname}")

        elif action_id == "project_create":
            # Prompt user for project name via thread reply
            mark_pending_create(user_id, channel, thread_ts)
            _post(
                blocks=project_create_prompt_blocks(user_id),
                text="Type the new project name in this thread",
            )

        elif action_id == "project_continue":
            # User chose to keep the current project — nothing to do
            _post(text=":arrow_forward: Continuing with your current project. What would you like to do?")

        elif action_id == "project_switch":
            # End current session and show project picker
            deactivate_session(user_id)
            projects = list_projects(limit=20)
            _post(
                blocks=project_selection_blocks(projects, user_id),
                text="Select a project",
            )

        elif action_id == "session_end":
            deactivate_session(user_id)
            _post(blocks=session_ended_blocks(), text="Session ended")

    except Exception as exc:
        logger.error("_handle_project_action failed: %s", exc, exc_info=True)
        _post(text=f":x: Something went wrong: {exc}")
