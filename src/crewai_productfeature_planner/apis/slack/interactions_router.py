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
        "memory_configure": ":brain: Configuring project memory",
        "memory_idea": ":bulb: Adding idea & iteration guardrails",
        "memory_knowledge": ":books: Adding knowledge entries",
        "memory_tools": ":wrench: Adding tool entries",
        "memory_view": ":mag: Viewing project memory",
        "memory_done": ":white_check_mark: Memory configuration done",
        "next_step_accept": ":white_check_mark: Suggestion accepted",
        "next_step_dismiss": ":x: Suggestion dismissed",
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

    In DMs, the project is scoped to the user.
    In channels, the project is scoped to the channel (admin-only).
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        project_create_prompt_blocks,
        project_selection_blocks,
        session_ended_blocks,
        session_started_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        activate_channel_project,
        activate_project,
        can_manage_memory,
        deactivate_channel_session,
        deactivate_session,
        is_dm,
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

    # In channels, only admins may select or switch projects
    if not is_dm(channel) and action_id not in ("project_continue",):
        if not can_manage_memory(user_id, channel):
            _post(
                text=(
                    ":lock: Only workspace admins can select or change "
                    "the project for this channel."
                ),
            )
            return

    try:
        if action_id.startswith("project_select_"):
            # User selected an existing project
            project_id = action_id.removeprefix("project_select_")
            proj = get_project(project_id)
            if not proj:
                _post(text=":warning: Project not found. Please try again.")
                return
            pname = proj.get("name", "Unnamed")
            if is_dm(channel):
                activate_project(
                    user_id=user_id,
                    channel=channel,
                    project_id=project_id,
                    project_name=pname,
                )
            else:
                activate_channel_project(
                    channel_id=channel,
                    project_id=project_id,
                    project_name=pname,
                    activated_by=user_id,
                )
            _post(blocks=session_started_blocks(pname), text=f"Session started: {pname}")

            # Proactively suggest next step after project selection
            try:
                from crewai_productfeature_planner.apis.slack._next_step import (
                    predict_and_post_next_step,
                )
                predict_and_post_next_step(
                    channel=channel,
                    thread_ts=thread_ts,
                    user=user_id,
                    project_id=project_id,
                    trigger_action="project_selected",
                    project_config=proj,
                )
            except Exception as ns_exc:
                logger.warning("Next-step after project select failed: %s", ns_exc)

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
            if is_dm(channel):
                deactivate_session(user_id)
            else:
                deactivate_channel_session(channel)
            projects = list_projects(limit=20)
            _post(
                blocks=project_selection_blocks(projects, user_id),
                text="Select a project",
            )

        elif action_id == "session_end":
            if is_dm(channel):
                deactivate_session(user_id)
            else:
                deactivate_channel_session(channel)
            _post(blocks=session_ended_blocks(), text="Session ended")

    except Exception as exc:
        logger.error("_handle_project_action failed: %s", exc, exc_info=True)
        _post(text=f":x: Something went wrong: {exc}")


def _handle_memory_action(
    action_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a memory-configuration button click in a background thread.

    In channels only workspace admins may modify memory.
    ``memory_view`` is allowed for all users.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        memory_category_prompt_blocks,
        memory_configure_blocks,
        memory_saved_blocks,
        memory_view_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
        get_context_session,
        mark_pending_memory,
    )
    from crewai_productfeature_planner.mongodb.project_memory import (
        MemoryCategory,
        get_project_memory,
        upsert_project_memory,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    def _post(blocks=None, text=""):
        try:
            kwargs: dict = {
                "channel": channel,
                "thread_ts": thread_ts,
                "text": text or "Memory update",
            }
            if blocks:
                kwargs["blocks"] = blocks
            client.chat_postMessage(**kwargs)
        except Exception as exc:
            logger.error("Memory action post failed: %s", exc)

    # Admin gate — memory_view is read-only so anyone can use it
    if action_id != "memory_view" and not can_manage_memory(user_id, channel):
        _post(
            text=(
                ":lock: Only workspace admins can configure project "
                "memory in a channel."
            ),
        )
        return

    session = get_context_session(user_id, channel)
    if not session or not session.get("project_id"):
        _post(text=":warning: No active project session. Please select a project first.")
        return

    project_id = session["project_id"]
    project_name = session.get("project_name", "Unknown")

    # Ensure the memory document scaffold exists
    upsert_project_memory(project_id)

    _CATEGORY_MAP = {
        "memory_idea": (
            MemoryCategory.IDEA_ITERATION,
            "Idea & Iteration Guardrails",
            (
                "Describe how agents should behave when iterating "
                "through ideas.  Examples:\n"
                "• _Focus on MVP features only_\n"
                "• _Keep iterations concise, max 3 rounds_\n"
                "• _Prioritise user-facing value over technical debt_\n"
                "• _Follow lean startup methodology_"
            ),
        ),
        "memory_knowledge": (
            MemoryCategory.KNOWLEDGE,
            "Knowledge Links & Documents",
            (
                "Provide links, document references, or notes that "
                "serve as guidelines.  Examples:\n"
                "• _https://wiki.example.com/api-design-guide_\n"
                "• _See the brand guidelines PDF uploaded last week_\n"
                "• _Our API versioning strategy: URI-based /v1/_\n"
                "• _Competitor analysis: https://docs.example.com/competitor_"
            ),
        ),
        "memory_tools": (
            MemoryCategory.TOOLS,
            "Implementation Tools & Technologies",
            (
                "List the tools, databases, frameworks, and algorithms "
                "the team uses.  Examples:\n"
                "• _MongoDB Atlas for persistence_\n"
                "• _FastAPI for REST endpoints_\n"
                "• _React + TypeScript for frontend_\n"
                "• _Redis for caching and pub/sub_\n"
                "• _OpenAI GPT-4o for embeddings_"
            ),
        ),
    }

    try:
        if action_id == "memory_configure":
            _post(
                blocks=memory_configure_blocks(project_name, user_id),
                text="Configure project memory",
            )

        elif action_id in _CATEGORY_MAP:
            cat_enum, cat_label, help_text = _CATEGORY_MAP[action_id]
            mark_pending_memory(
                user_id=user_id,
                channel=channel,
                thread_ts=thread_ts,
                category=cat_enum.value,
                project_id=project_id,
            )
            _post(
                blocks=memory_category_prompt_blocks(
                    cat_enum.value, cat_label, help_text,
                ),
                text=f"Configure {cat_label}",
            )

        elif action_id == "memory_view":
            doc = get_project_memory(project_id) or {}
            _post(
                blocks=memory_view_blocks(
                    project_name,
                    doc.get("idea_iteration", []),
                    doc.get("knowledge", []),
                    doc.get("tools", []),
                ),
                text="Project memory",
            )

        elif action_id == "memory_done":
            _post(
                text=(
                    ":white_check_mark: Memory configuration complete! "
                    "All agents will now recall these guardrails "
                    "during PRD runs."
                ),
            )

    except Exception as exc:
        logger.error("_handle_memory_action failed: %s", exc, exc_info=True)
        _post(text=f":x: Something went wrong: {exc}")


def _handle_next_step_feedback(
    action_id: str,
    value: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a next-step suggestion feedback button click.

    The ``value`` field encodes ``<next_step>|<interaction_id>``.
    Records whether the user accepted or dismissed the suggestion,
    and if accepted, triggers the suggested action.
    """
    from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
        record_next_step_feedback,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()

    # Parse the encoded value
    parts = value.split("|", 1)
    next_step = parts[0] if parts else ""
    interaction_id = parts[1] if len(parts) > 1 and parts[1] else None

    accepted = action_id == "next_step_accept"

    # Record feedback in agentInteraction
    if interaction_id:
        record_next_step_feedback(interaction_id, accepted)

    logger.info(
        "Next-step feedback: action=%s next_step=%s accepted=%s "
        "interaction_id=%s user=%s",
        action_id, next_step, accepted, interaction_id, user_id,
    )

    if not accepted:
        # Dismissed — just acknowledge
        if client and channel:
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=":ok_hand: No problem! Let me know when you need help.",
                )
            except Exception as exc:
                logger.error("Next-step dismiss ack failed: %s", exc)
        return

    # Accepted — trigger the suggested action
    def _post(text: str) -> None:
        if client and channel:
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=text,
                )
            except Exception as exc:
                logger.error("Next-step accept post failed: %s", exc)

    from crewai_productfeature_planner.apis.slack.session_manager import (
        get_context_session,
    )

    session = get_context_session(user_id, channel)

    if next_step == "configure_confluence":
        _post(
            ":confluence: To configure the Confluence space key, say "
            "*configure memory* or update the project settings."
        )
    elif next_step == "configure_jira":
        _post(
            ":jira2: To configure the Jira project key, say "
            "*configure memory* or update the project settings."
        )
    elif next_step == "configure_memory":
        if session and session.get("project_id"):
            from crewai_productfeature_planner.apis.slack._session_handlers import (
                handle_configure_memory,
            )
            handle_configure_memory(channel, thread_ts, user_id, session)
        else:
            _post(":warning: No active project session. Please select a project first.")
    elif next_step == "create_prd":
        _post(
            ":rocket: Great! Just tell me your product or feature idea "
            "and I'll start planning it. For example:\n"
            ">  _Create a PRD for a mobile fitness tracking app_"
        )
    elif next_step == "publish":
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_publish_intent,
        )
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        handle_publish_intent(channel, thread_ts, user_id, SlackSendMessageTool())
    elif next_step == "configure_missing_keys":
        _post(
            ":key: Before publishing, you'll need to configure your "
            "Confluence and Jira keys. Say *configure memory* or update "
            "the project settings to add them."
        )
    elif next_step == "review_prd":
        _post(
            ":mag: You have completed PRDs ready for review! Say "
            "*check publish* to see what's pending."
        )
    else:
        _post(
            f":bulb: To proceed with _{next_step}_, just tell me "
            "what you'd like to do!"
        )
