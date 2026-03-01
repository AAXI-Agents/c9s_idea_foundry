"""FastAPI application for triggering CrewAI flows via HTTP.

API convention:
    POST /flow/{flow_name}/kickoff  — start a flow
    POST /flow/{flow_name}/approve  — approve current iteration
    GET  /flow/runs/{run_id}        — check status

Each flow runs asynchronously; the HTTP response returns immediately.
User approval is handled via a per-run threading Event that the flow
blocks on between iterations.

Start the server:
    uv run start_api          # localhost:8000
    uv run start_api --ngrok  # localhost:8000 + ngrok tunnel

Subpackages:
    - ``health``  — liveness / readiness probes
    - ``prd``     — PRD generation flow endpoints
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from crewai_productfeature_planner.apis.health.router import router as health_router
from crewai_productfeature_planner.apis.prd.router import router as prd_router
from crewai_productfeature_planner.apis.publishing.router import router as publishing_router
from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus  # noqa: F401 (re-export)
from crewai_productfeature_planner.apis.slack.events_router import router as slack_events_router
from crewai_productfeature_planner.apis.slack.interactions_router import router as slack_interactions_router
from crewai_productfeature_planner.apis.slack.oauth_router import router as slack_oauth_router
from crewai_productfeature_planner.apis.slack.router import router as slack_router
from crewai_productfeature_planner.mongodb.crew_jobs import fail_incomplete_jobs_on_startup
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.version import get_version

_logger = get_logger(__name__)


def _auto_resume_interrupted_flows() -> None:
    """Find unfinalized PRD flows and resume them.

    For each resumable run the function:
    1. Resolves Slack context (from workingIdeas or agentInteraction).
    2. Posts a notification to the original Slack thread (when known).
    3. Creates an in-memory ``FlowRun`` record.
    4. Launches ``resume_prd_flow`` in a daemon background thread.

    Runs without Slack context are still resumed silently.
    """
    import threading

    from crewai_productfeature_planner.mongodb.working_ideas import find_unfinalized

    unfinalized = find_unfinalized()
    if not unfinalized:
        _logger.info("Auto-resume: no unfinalized flows found")
        return

    # ── Resolve missing Slack context via fallback lookups ─────────
    for run_info in unfinalized:
        if run_info.get("slack_channel") and run_info.get("slack_thread_ts"):
            continue  # already has context
        run_id = run_info["run_id"]
        idea = run_info.get("idea", "")
        channel: str | None = None
        thread_ts: str | None = None

        try:
            from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
                find_interactions,
            )

            # Strategy 1: look up by run_id in agentInteraction
            docs = find_interactions(run_id=run_id, limit=1)
            if docs and docs[0].get("channel") and docs[0].get("thread_ts"):
                channel = docs[0]["channel"]
                thread_ts = docs[0]["thread_ts"]
                _logger.info(
                    "Auto-resume: recovered Slack context for %s via run_id match",
                    run_id,
                )

            # Strategy 2: look up by idea text (run_id may be None in interaction)
            if not channel and idea:
                docs = find_interactions(intent="create_prd", limit=20)
                for doc in docs:
                    if (
                        doc.get("idea") == idea
                        and doc.get("channel")
                        and doc.get("thread_ts")
                    ):
                        channel = doc["channel"]
                        thread_ts = doc["thread_ts"]
                        _logger.info(
                            "Auto-resume: recovered Slack context for %s via idea match",
                            run_id,
                        )
                        break

            # Strategy 3: look up Slack context from crewJobs
            if not channel:
                from crewai_productfeature_planner.mongodb.client import get_db
                job_doc = get_db()["crewJobs"].find_one({"job_id": run_id})
                if (
                    job_doc
                    and job_doc.get("slack_channel")
                    and job_doc.get("slack_thread_ts")
                ):
                    channel = job_doc["slack_channel"]
                    thread_ts = job_doc["slack_thread_ts"]
                    _logger.info(
                        "Auto-resume: recovered Slack context for %s via crewJobs",
                        run_id,
                    )

            if channel and thread_ts:
                run_info["slack_channel"] = channel
                run_info["slack_thread_ts"] = thread_ts
                _logger.info(
                    "Auto-resume: Slack context for %s → channel=%s, thread_ts=%s",
                    run_id, channel, thread_ts,
                )
                # Backfill working idea so future restarts don't need fallback
                try:
                    from crewai_productfeature_planner.mongodb.working_ideas import (
                        save_slack_context,
                    )
                    save_slack_context(run_id, channel, thread_ts)
                except Exception:  # noqa: BLE001
                    _logger.debug(
                        "Auto-resume: backfill save_slack_context failed for %s",
                        run_id, exc_info=True,
                    )
        except Exception:  # noqa: BLE001
            _logger.debug(
                "Auto-resume: Slack context fallback failed for %s",
                run_id, exc_info=True,
            )

    # Separate runs with Slack context from silent resumes
    slack_runs = [
        r for r in unfinalized
        if r.get("slack_channel") and r.get("slack_thread_ts")
    ]
    silent_runs = [
        r for r in unfinalized
        if not (r.get("slack_channel") and r.get("slack_thread_ts"))
    ]

    # Lazy imports – keep module-level lightweight
    from crewai_productfeature_planner.apis.prd.service import resume_prd_flow
    from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs

    # ── Resume runs WITH Slack context (notify + heartbeat) ──────
    if slack_runs:
        from crewai_productfeature_planner.apis.slack._flow_handlers import make_progress_poster
        from crewai_productfeature_planner.tools.slack_tools import (
            SlackPostPRDResultTool,
            SlackSendMessageTool,
        )

        send_tool = SlackSendMessageTool()

        for run_info in slack_runs:
            run_id = run_info["run_id"]
            channel = run_info["slack_channel"]
            thread_ts = run_info["slack_thread_ts"]
            idea = run_info.get("idea", "")
            sections_done = run_info.get("sections_done", 0)
            total_sections = run_info.get("total_sections", 10)

            try:
                ack = (
                    ":arrows_counterclockwise: *Server restarted.* "
                    f"Auto-resuming PRD flow (run `{run_id}`):\n"
                    f"> _{idea}_\n"
                    f"Progress: {sections_done}/{total_sections} sections completed."
                )
                send_tool.run(channel=channel, text=ack, thread_ts=thread_ts)
            except Exception:  # noqa: BLE001
                _logger.debug(
                    "Auto-resume: could not notify Slack for %s", run_id, exc_info=True,
                )

            if run_id not in runs:
                runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")

            progress_cb = make_progress_poster(
                channel=channel,
                thread_ts=thread_ts,
                user="",
                send_tool=send_tool,
                run_id=run_id,
            )

            def _resume_and_notify(
                _run_id: str = run_id,
                _channel: str = channel,
                _thread_ts: str = thread_ts,
                _idea: str = idea,
                _progress_cb=progress_cb,
            ) -> None:
                try:
                    resume_prd_flow(
                        _run_id,
                        auto_approve=True,
                        progress_callback=_progress_cb,
                    )

                    run = runs.get(_run_id)
                    if run and run.status == FlowStatus.COMPLETED:
                        post_tool = SlackPostPRDResultTool()
                        post_tool.run(
                            channel=_channel,
                            idea=_idea,
                            output_file=run.output_file,
                            confluence_url=run.confluence_url,
                            jira_output=run.jira_output,
                            thread_ts=_thread_ts,
                        )
                    elif run and run.status == FlowStatus.PAUSED:
                        send_tool.run(
                            channel=_channel,
                            text=(
                                f":pause_button: Auto-resumed PRD flow paused "
                                f"(run `{_run_id}`). Say *resume prd flow* to continue."
                            ),
                            thread_ts=_thread_ts,
                        )
                    else:
                        error_msg = run.error if run else "Unknown error"
                        send_tool.run(
                            channel=_channel,
                            text=f":x: Auto-resumed PRD flow failed: {error_msg}",
                            thread_ts=_thread_ts,
                        )
                except Exception as exc:
                    _logger.error("Auto-resume flow %s failed: %s", _run_id, exc)
                    try:
                        send_tool.run(
                            channel=_channel,
                            text=f":x: Auto-resume failed: {exc}",
                            thread_ts=_thread_ts,
                        )
                    except Exception:  # noqa: BLE001
                        pass

            t = threading.Thread(
                target=_resume_and_notify,
                name=f"auto-resume-{run_id}",
                daemon=True,
            )
            t.start()
            _logger.info(
                "Auto-resume: launched background thread for run_id=%s in %s/%s",
                run_id, channel, thread_ts,
            )

    # ── Resume runs WITHOUT Slack context (silent) ───────────────
    for run_info in silent_runs:
        run_id = run_info["run_id"]
        idea = run_info.get("idea", "")

        if run_id not in runs:
            runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")

        def _resume_silent(_run_id: str = run_id) -> None:
            try:
                resume_prd_flow(_run_id, auto_approve=True)
            except Exception as exc:
                _logger.error("Auto-resume (silent) flow %s failed: %s", _run_id, exc)

        t = threading.Thread(
            target=_resume_silent,
            name=f"auto-resume-silent-{run_id}",
            daemon=True,
        )
        t.start()
        _logger.info(
            "Auto-resume: launched silent background thread for run_id=%s (idea=%s)",
            run_id, idea[:80] if idea else "<empty>",
        )

    _logger.info(
        "Auto-resume: started %d flow(s) (%d with Slack, %d silent)",
        len(unfinalized), len(slack_runs), len(silent_runs),
    )


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Startup / shutdown lifecycle hook.

    Runs the same recovery tasks as the CLI on startup:
    1. Kill stale crew processes from a previous server crash.
    2. Mark incomplete crew-jobs as failed.
    3. Generate missing markdown outputs for completed ideas.
    4. Publish unpublished PRDs to Confluence (when credentials are set).
    """
    # 1. Kill stale processes
    try:
        from crewai_productfeature_planner.components.startup import _kill_stale_crew_processes
        killed = _kill_stale_crew_processes()
        if killed:
            _logger.info("Startup recovery: killed %d stale process(es)", killed)
    except Exception as exc:
        _logger.warning("Startup recovery (kill stale processes) failed: %s", exc)

    # 2. Fail incomplete jobs (returns list of recovered job dicts)
    recovered_jobs: list[dict] = []
    try:
        recovered_jobs = fail_incomplete_jobs_on_startup()
        if recovered_jobs:
            _logger.info("Startup recovery: %d incomplete job(s) marked as failed", len(recovered_jobs))
    except Exception as exc:
        _logger.warning("Startup recovery (fail incomplete jobs) failed: %s", exc)

    # 3. Generate missing output files
    try:
        from crewai_productfeature_planner.components.startup import _generate_missing_outputs
        generated = _generate_missing_outputs()
        if generated:
            _logger.info("Startup recovery: generated %d missing output file(s)", generated)
    except Exception as exc:
        _logger.warning("Startup recovery (generate missing outputs) failed: %s", exc)

    # 4. Startup pipeline: review markdown PRDs and publish to Confluence
    #    Uses the orchestrator stage pattern for structured execution.
    try:
        from crewai_productfeature_planner.orchestrator.stages import (
            build_startup_pipeline,
        )
        startup_pipeline = build_startup_pipeline()
        startup_pipeline.run_pipeline()
        if startup_pipeline.completed:
            _logger.info(
                "Startup pipeline: completed stage(s) %s",
                startup_pipeline.completed,
            )
        if startup_pipeline.skipped:
            _logger.info(
                "Startup pipeline: skipped stage(s) %s",
                startup_pipeline.skipped,
            )
    except Exception as exc:
        _logger.warning("Startup pipeline (markdown review) failed: %s", exc)

    # 5. Autonomous delivery: CrewAI crew-based Confluence + Jira pipeline
    #    Runs in a background thread so the server starts accepting requests
    #    immediately while the delivery agents work autonomously.
    try:
        import threading
        from crewai_productfeature_planner.components.startup import _run_startup_delivery_background
        delivery_thread = threading.Thread(
            target=_run_startup_delivery_background,
            name="startup-delivery",
            daemon=True,
        )
        delivery_thread.start()
        _logger.info("Startup delivery: background thread launched")
    except Exception as exc:
        _logger.warning("Startup delivery failed to launch: %s", exc)

    # 6. File watcher: auto-publish new PRD files dropped into output/prds/
    try:
        from crewai_productfeature_planner.apis.publishing.watcher import start_watcher
        if start_watcher():
            _logger.info("File watcher: started")
    except Exception as exc:
        _logger.warning("File watcher failed to start: %s", exc)

    # 7. Cron scheduler: periodic scan for interrupted deliveries
    try:
        from crewai_productfeature_planner.apis.publishing.scheduler import start_scheduler
        if start_scheduler():
            _logger.info("Publish scheduler: started")
    except Exception as exc:
        _logger.warning("Publish scheduler failed to start: %s", exc)

    # 8. Auto-resume interrupted PRD flows that have Slack context
    try:
        _auto_resume_interrupted_flows()
    except Exception as exc:
        _logger.warning("Auto-resume startup step failed: %s", exc)

    yield

    # ── Shutdown ──────────────────────────────────────────────────
    try:
        from crewai_productfeature_planner.apis.publishing.watcher import stop_watcher
        stop_watcher()
    except Exception:  # noqa: BLE001
        pass
    try:
        from crewai_productfeature_planner.apis.publishing.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(
    title="CrewAI Product Feature Planner API",
    version=get_version(),
    description="HTTP interface for triggering CrewAI flows.",
    lifespan=_lifespan,
    openapi_tags=[
        {
            "name": "Health",
            "description": "Service liveness and readiness checks.",
        },
        {
            "name": "Flow Runs",
            "description": (
                "Start flows, list runs, query status, list resumable runs, "
                "and resume paused/unfinalized flows."
            ),
        },
        {
            "name": "Approvals",
            "description": (
                "Approve, refine, provide feedback, or pause PRD section "
                "refinement cycles."
            ),
        },
        {
            "name": "Jobs",
            "description": (
                "Persistent job records from the crewJobs MongoDB collection. "
                "Track flow run lifecycle, queue time, and running time."
            ),
        },
        {
            "name": "Slack Messenger",
            "description": (
                "Interact with the PRD Planner through Slack. "
                "Post a product idea and the bot will generate a full PRD. "
                "Supports ``webhook_url`` for push-based result delivery."
            ),
        },
        {
            "name": "Slack Events",
            "description": (
                "Handles inbound Slack Events API callbacks. "
                "Responds to bot channel joins with an intro message and "
                "processes @mentions and thread replies via OpenAI interpretation."
            ),
        },
        {
            "name": "Slack Interactions",
            "description": (
                "Handles inbound Slack interactive payloads (button clicks, "
                "menu selections, modal submissions). Mirrors the CLI "
                "interactive experience — refinement mode choice, idea "
                "approval, and requirements approval — entirely within Slack."
            ),
        },
        {
            "name": "Slack OAuth",
            "description": (
                "Handles the Slack OAuth v2 install/reinstall callback. "
                "Exchanges the authorization code for bot tokens and persists "
                "them to ``.env`` and ``.slack_tokens.json``."
            ),
        },
        {
            "name": "Publishing",
            "description": (
                "Manage Confluence publishing and Jira ticket creation. "
                "List pending PRDs, batch-publish to Confluence, create "
                "Jira Epics/Stories/Tasks, and monitor the file watcher "
                "and cron scheduler that automate delivery."
            ),
        },
    ],
)

app.include_router(health_router)
app.include_router(prd_router)
app.include_router(slack_router)
app.include_router(slack_events_router)
app.include_router(slack_interactions_router)
app.include_router(slack_oauth_router)
app.include_router(publishing_router)


# ── Global exception handler ─────────────────────────────────


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Return a structured ErrorResponse for any unhandled server error.

    This ensures every API endpoint returns a consistent JSON envelope
    (``ErrorResponse``) instead of a bare 500 HTML page, making errors
    machine-readable for MCP clients and dashboards.
    """
    from crewai_productfeature_planner.scripts.retry import BillingError, LLMError

    if isinstance(exc, BillingError):
        status_code = 503
        error_code = "BILLING_ERROR"
    elif isinstance(exc, LLMError):
        status_code = 503
        error_code = "LLM_ERROR"
    else:
        status_code = 500
        error_code = "INTERNAL_ERROR"

    _logger.error("Unhandled %s in %s %s: %s",
                  error_code, request.method, request.url.path, exc)

    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": str(exc),
            "run_id": None,
            "detail": f"{type(exc).__name__}: {exc}",
        },
    )
