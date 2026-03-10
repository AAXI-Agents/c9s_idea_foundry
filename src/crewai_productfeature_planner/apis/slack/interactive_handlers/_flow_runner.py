"""Full interactive Slack PRD flow runner."""

from __future__ import annotations

import logging

from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
    make_slack_exec_summary_completion_callback,
    make_slack_exec_summary_feedback_callback,
    make_slack_idea_callback,
    make_slack_jira_review_callback,
    make_slack_jira_skeleton_callback,
    make_slack_requirements_callback,
    run_manual_refinement,
    wait_for_refinement_mode,
)
from crewai_productfeature_planner.apis.slack.interactive_handlers._run_state import (
    _interactive_runs,
    _lock,
    cleanup_interactive_run,
    get_interactive_run,
    register_interactive_run,
)
from crewai_productfeature_planner.apis.slack.interactive_handlers._slack_helpers import (
    _post_blocks,
    _post_text,
)

logger = logging.getLogger(__name__)


def run_interactive_slack_flow(
    run_id: str,
    idea: str,
    channel: str,
    thread_ts: str,
    user: str,
    notify: bool = True,
    webhook_url: str | None = None,
    project_id: str | None = None,
) -> None:
    """Execute the PRD flow with full Slack interactive support.

    Mirrors the CLI ``_run_single_flow()`` experience:
    1. Ask refinement mode (agent vs manual) via buttons
    2. If manual: run thread-based refinement loop
    3. Approve refined idea via buttons
    4. Approve requirements via buttons
    5. Auto-generate sections (like CLI after requirements approve)
    6. Post results to Slack

    If *project_id* is provided, the working-idea document is linked
    to the project **before** the flow starts (via upsert) so
    in-progress runs are visible to ``find_ideas_by_project``.
    A safety-net re-apply is performed after the flow completes.

    This runs in a background thread and communicates with the user
    exclusively through Slack interactive messages.
    """
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow
    from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs
    from crewai_productfeature_planner.apis.slack.blocks import (
        flow_cancelled_blocks,
        flow_started_blocks,
    )
    from crewai_productfeature_planner.apis.slack.router import _deliver_webhook
    from crewai_productfeature_planner.mongodb.crew_jobs import create_job
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackPostPRDResultTool,
        SlackSendMessageTool,
    )

    send_tool = SlackSendMessageTool()

    # Register interactive state
    register_interactive_run(run_id, channel, thread_ts, user, idea)

    # Create the FlowRun record and crew job
    runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")
    create_job(run_id, "prd", idea=idea, slack_channel=channel, slack_thread_ts=thread_ts)

    # Persist Slack context so channel-based orphan detection works
    # and auto-resume can notify the same thread.
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_slack_context,
        )
        save_slack_context(run_id, channel, thread_ts, idea=idea)
    except Exception:  # noqa: BLE001
        logger.debug("save_slack_context failed for %s", run_id, exc_info=True)

    # Link working idea to project early so in-progress runs appear in
    # find_ideas_by_project queries (e.g. "list ideas").
    if project_id:
        try:
            from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                save_project_ref,
            )
            save_project_ref(run_id, project_id, idea=idea)
        except Exception:  # noqa: BLE001
            logger.debug("early save_project_ref failed for %s", run_id, exc_info=True)

    try:
        # Step 1: Ask refinement mode
        mode = wait_for_refinement_mode(run_id)

        info = get_interactive_run(run_id)
        if not info or info.get("cancelled") or mode == "cancel":
            blocks = flow_cancelled_blocks(run_id, "refinement mode selection")
            _post_blocks(channel, thread_ts, blocks, text="PRD flow cancelled")
            runs[run_id].status = FlowStatus.FAILED
            runs[run_id].error = "Cancelled by user at refinement mode"
            return

        if mode is None:
            # Timeout — default to agent mode
            _post_text(
                channel, thread_ts,
                ":hourglass: No response received — defaulting to agent refinement.",
            )
            mode = "agent"

        # Step 2: Manual refinement (if chosen)
        if mode == "manual":
            refined_idea, history = run_manual_refinement(run_id)
            info = get_interactive_run(run_id)
            if info and info.get("cancelled"):
                blocks = flow_cancelled_blocks(run_id, "manual idea refinement")
                _post_blocks(channel, thread_ts, blocks, text="PRD flow cancelled")
                runs[run_id].status = FlowStatus.FAILED
                runs[run_id].error = "Cancelled by user during manual refinement"
                return
            idea = refined_idea
            # Update the registered idea
            with _lock:
                if run_id in _interactive_runs:
                    _interactive_runs[run_id]["idea"] = idea

        # Step 3: Start the PRD flow with Slack-aware callbacks
        if notify:
            blocks = flow_started_blocks(run_id, idea)
            _post_blocks(channel, thread_ts, blocks,
                         text=f"PRD flow started for: {idea[:80]}")

        # Run the PRD flow — use Slack callbacks for idea/requirements approval
        # The flow will call these callbacks at the appropriate points
        from crewai_productfeature_planner.flows.prd_flow import (
            ExecutiveSummaryCompleted,
            IdeaFinalized,
            PauseRequested,
            PRDFlow,
            RequirementsFinalized,
        )
        from crewai_productfeature_planner.mongodb.crew_jobs import (
            update_job_completed,
            update_job_started,
        )
        from crewai_productfeature_planner.scripts.retry import (
            BillingError, LLMError, ModelBusyError,
        )

        runs[run_id].status = FlowStatus.RUNNING
        update_job_started(run_id)

        flow = PRDFlow()
        flow.state.idea = idea
        flow.state.run_id = run_id

        # If mode was manual, the idea is already refined
        if mode == "manual":
            flow.state.idea_refined = True
            flow.state.original_idea = get_interactive_run(run_id).get("idea", idea)
        else:
            # Agent mode: set callbacks for interactive approval gates
            flow.idea_approval_callback = make_slack_idea_callback(run_id)

        flow.requirements_approval_callback = make_slack_requirements_callback(run_id)
        flow.exec_summary_user_feedback_callback = (
            make_slack_exec_summary_feedback_callback(run_id)
        )
        flow.executive_summary_callback = (
            make_slack_exec_summary_completion_callback(run_id)
        )
        flow.jira_skeleton_approval_callback = (
            make_slack_jira_skeleton_callback(run_id)
        )
        flow.jira_review_callback = make_slack_jira_review_callback(run_id)

        # Progress heartbeat — posts section-by-section updates to Slack
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            make_progress_poster,
        )
        progress_cb = make_progress_poster(
            channel, thread_ts, user, send_tool, run_id=run_id,
        )
        flow.progress_callback = progress_cb

        # Register callbacks in the module-level registry so they
        # survive CrewAI's asyncio.to_thread (which can lose instance
        # attributes set after __init__).
        from crewai_productfeature_planner.flows.prd_flow import (
            register_callbacks,
            cleanup_callbacks,
        )
        _cb_kwargs: dict = {
            "requirements_approval_callback": flow.requirements_approval_callback,
            "exec_summary_user_feedback_callback": flow.exec_summary_user_feedback_callback,
            "executive_summary_callback": flow.executive_summary_callback,
            "jira_skeleton_approval_callback": flow.jira_skeleton_approval_callback,
            "jira_review_callback": flow.jira_review_callback,
            "progress_callback": progress_cb,
        }
        if flow.idea_approval_callback is not None:
            _cb_kwargs["idea_approval_callback"] = flow.idea_approval_callback
        register_callbacks(run_id, **_cb_kwargs)

        try:
            result = flow.kickoff()

            # Link working idea to project (safety-net re-apply after
            # kickoff in case the early upsert was overwritten)
            if project_id:
                try:
                    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                        save_project_ref,
                    )
                    save_project_ref(run_id, project_id, idea=idea)
                except Exception:  # noqa: BLE001
                    logger.debug("save_project_ref failed for %s", run_id, exc_info=True)

            run = runs.get(run_id)
            if run:
                run.result = result
                run.status = FlowStatus.COMPLETED
                # Sync state
                from crewai_productfeature_planner.apis.prd.service import _sync_flow_state_to_run
                _sync_flow_state_to_run(run_id, flow)

            update_job_completed(run_id, status="completed")

            if notify:
                post_tool = SlackPostPRDResultTool()
                run = runs.get(run_id)
                post_tool.run(
                    channel=channel,
                    idea=idea,
                    output_file=run.output_file if run else "",
                    confluence_url=run.confluence_url if run else "",
                    jira_output=run.jira_output if run else "",
                    thread_ts=thread_ts,
                )
            logger.info("Interactive Slack PRD flow %s completed", run_id)

            # Proactively suggest next step after PRD completion
            try:
                from crewai_productfeature_planner.apis.slack._next_step import (
                    predict_and_post_next_step,
                )
                predict_and_post_next_step(
                    channel=channel,
                    thread_ts=thread_ts,
                    user=user,
                    trigger_action="prd_completed",
                )
            except Exception as ns_exc:
                logger.warning("Next-step after PRD completion failed: %s", ns_exc)

        except IdeaFinalized:
            update_job_completed(run_id, status="completed")
            if notify:
                blocks = flow_cancelled_blocks(run_id, "idea approval")
                _post_blocks(channel, thread_ts, blocks, text="PRD flow cancelled at idea approval")
            runs[run_id].status = FlowStatus.COMPLETED

        except RequirementsFinalized:
            update_job_completed(run_id, status="completed")
            if notify:
                blocks = flow_cancelled_blocks(run_id, "requirements approval")
                _post_blocks(channel, thread_ts, blocks,
                             text="PRD flow cancelled at requirements approval")
            runs[run_id].status = FlowStatus.COMPLETED

        except ExecutiveSummaryCompleted:
            update_job_completed(run_id, status="completed")
            if notify:
                _post_text(
                    channel, thread_ts,
                    ":white_check_mark: PRD flow completed — stopped "
                    "after executive summary.",
                )
            runs[run_id].status = FlowStatus.COMPLETED

        except PauseRequested:
            update_job_completed(run_id, status="paused")
            runs[run_id].status = FlowStatus.PAUSED
            if notify:
                from crewai_productfeature_planner.apis.slack.blocks import flow_paused_blocks
                blocks = flow_paused_blocks(run_id)
                _post_blocks(channel, thread_ts, blocks,
                             text=f"PRD flow paused ({run_id})")

        except (BillingError, LLMError) as exc:
            update_job_completed(run_id, status="paused")
            runs[run_id].status = FlowStatus.PAUSED
            runs[run_id].error = str(exc)
            if notify:
                from crewai_productfeature_planner.apis.slack.blocks import flow_paused_blocks
                is_busy = isinstance(exc, ModelBusyError)
                extra = (
                    " The model is currently busy — will auto-resume shortly."
                    if is_busy else ""
                )
                blocks = flow_paused_blocks(run_id, str(exc))
                _post_blocks(channel, thread_ts, blocks,
                             text=f"PRD flow paused due to error ({run_id}).{extra}")

    except Exception as exc:
        logger.error("Interactive Slack PRD flow %s failed: %s", run_id, exc)
        runs[run_id].status = FlowStatus.FAILED
        runs[run_id].error = str(exc)
        if notify:
            try:
                send_tool.run(
                    channel=channel,
                    text=f":x: PRD flow failed: {exc}",
                    thread_ts=thread_ts,
                )
            except Exception:
                pass

    except BaseException as exc:  # noqa: BLE001
        # Never let SystemExit / KeyboardInterrupt crash the server.
        logger.critical(
            "Interactive Slack PRD flow %s caught fatal %s: %s — "
            "suppressed to protect server",
            run_id, type(exc).__name__, exc,
        )
        try:
            runs[run_id].status = FlowStatus.FAILED
            runs[run_id].error = f"FATAL: {type(exc).__name__}: {exc}"
        except Exception:  # noqa: BLE001
            pass

    finally:
        if webhook_url:
            run = runs.get(run_id)
            _deliver_webhook(
                run_id,
                result=run.result if run else None,
                error=run.error if run else None,
                webhook_url=webhook_url,
            )
        # Clean up module-level callback registry
        try:
            from crewai_productfeature_planner.flows.prd_flow import cleanup_callbacks
            cleanup_callbacks(run_id)
        except Exception:  # noqa: BLE001
            pass
        cleanup_interactive_run(run_id)
