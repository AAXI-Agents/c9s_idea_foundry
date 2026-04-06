"""Handler for idea-list resume/restart/archive button clicks."""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _handle_idea_list_action(
    action_id: str,
    value: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a resume/restart/archive button click from the idea list.

    The button ``value`` is ``<project_id>|<idea_number>``.
    Action IDs follow the pattern ``idea_resume_<N>``,
    ``idea_restart_<N>``, or ``idea_archive_<N>``.
    """
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        handle_archive_idea,
        handle_restart_prd,
        handle_resume_prd,
    )
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackSendMessageTool,
        _get_slack_client,
    )

    # Parse value: "project_id|idea_number"
    parts = value.split("|", 1)
    if len(parts) != 2:
        logger.warning("Invalid idea list action value: %s", value)
        return

    project_id, idea_num_str = parts
    try:
        idea_number = int(idea_num_str)
    except ValueError:
        logger.warning("Invalid idea number in value: %s", value)
        return

    send_tool = SlackSendMessageTool()
    is_resume = action_id.startswith("idea_resume_")
    is_archive = action_id.startswith("idea_archive_")

    if is_resume:
        # Post acknowledgement
        client = _get_slack_client()
        if client and channel:
            try:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=(
                        f"<@{user_id}> :arrow_forward: Resuming idea "
                        f"#{idea_number}…"
                    ),
                )
            except Exception as exc:
                logger.error("Idea resume ack failed: %s", exc)

        handle_resume_prd(
            channel=channel,
            thread_ts=thread_ts,
            user=user_id,
            send_tool=send_tool,
            project_id=project_id,
            idea_number=idea_number,
        )
    elif is_archive:
        # Archive — posts a confirmation prompt
        handle_archive_idea(
            channel=channel,
            thread_ts=thread_ts,
            user=user_id,
            send_tool=send_tool,
            project_id=project_id,
            idea_number=idea_number,
        )
    else:
        # Restart — this posts its own confirmation prompt
        handle_restart_prd(
            channel=channel,
            thread_ts=thread_ts,
            user=user_id,
            send_tool=send_tool,
            event_ts="",
            project_id=project_id,
            idea_number=idea_number,
        )


def _handle_idea_iterate_action(
    action_id: str,
    value: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process an iterate button click — re-refine an existing idea.

    Resolves the idea from the list, then kicks off a new PRD flow
    using the existing idea text as the starting point so the Idea
    Refinement agent can re-refine it with fresh context.
    """
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        _resolve_idea_by_number,
    )
    from crewai_productfeature_planner.apis.slack._session_reply import reply
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackSendMessageTool,
        _get_slack_client,
    )

    # Parse value: "project_id|idea_number"
    parts = value.split("|", 1)
    if len(parts) != 2:
        logger.warning("Invalid iterate action value: %s", value)
        return

    project_id, idea_num_str = parts
    try:
        idea_number = int(idea_num_str)
    except ValueError:
        logger.warning("Invalid idea number in iterate value: %s", value)
        return

    send_tool = SlackSendMessageTool()

    # Resolve the idea document
    run = _resolve_idea_by_number(
        project_id, idea_number, channel, thread_ts, user_id, send_tool,
    )
    if run is None:
        return

    idea_text = run.get("idea") or run.get("finalized_idea") or ""
    if not idea_text:
        reply(
            channel, thread_ts,
            f"<@{user_id}> :warning: Idea #{idea_number} has no text to iterate on.",
        )
        return

    # Acknowledge and kick off a new interactive PRD flow with the idea
    client = _get_slack_client()
    if client:
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=(
                    f"<@{user_id}> :repeat: Re-refining idea #{idea_number}… "
                    "Starting an interactive PRD flow with the original idea."
                ),
            )
        except Exception as exc:
            logger.error("Iterate ack failed: %s", exc)

    # Import and trigger the flow
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        kick_off_prd_flow,
    )

    kick_off_prd_flow(
        channel=channel,
        thread_ts=thread_ts,
        user=user_id,
        idea=idea_text,
        event_ts=thread_ts,
        interactive=True,
        project_id=project_id,
    )
