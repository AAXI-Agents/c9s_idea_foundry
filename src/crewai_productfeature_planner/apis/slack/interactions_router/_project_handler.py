"""Handler for project-session button clicks."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


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
