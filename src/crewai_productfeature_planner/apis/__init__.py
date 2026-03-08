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
from crewai_productfeature_planner.scripts.setup_mongodb import ensure_collections
from crewai_productfeature_planner.version import get_version

_logger = get_logger(__name__)


def _notify_terminated_flows(terminated: list[dict]) -> None:
    """Post Slack notifications for flows terminated on server restart.

    For each terminated run that has Slack context, posts a message
    to the original thread telling the user their flow was stopped
    and they should start a new one to pick up code changes.

    Args:
        terminated: List of dicts from ``fail_unfinalized_on_startup``,
            each containing ``run_id``, ``idea``, ``slack_channel``,
            ``slack_thread_ts``.
    """
    slack_runs = [
        r for r in terminated
        if r.get("slack_channel") and r.get("slack_thread_ts")
    ]
    if not slack_runs:
        return

    try:
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        send_tool = SlackSendMessageTool()
    except Exception:  # noqa: BLE001
        _logger.debug("Could not create SlackSendMessageTool for termination notices")
        return

    for run_info in slack_runs:
        run_id = run_info["run_id"]
        channel = run_info["slack_channel"]
        thread_ts = run_info["slack_thread_ts"]
        idea = run_info.get("idea", "")
        try:
            msg = (
                ":octagonal_sign: *Server restarted.* "
                f"PRD flow `{run_id}` was terminated to apply new changes.\n"
                f"> _{idea}_\n"
                "Say *create prd* to start a fresh run."
            )
            send_tool.run(channel=channel, text=msg, thread_ts=thread_ts)
        except Exception:  # noqa: BLE001
            _logger.debug(
                "Could not notify Slack about terminated flow %s", run_id,
                exc_info=True,
            )

    _logger.info(
        "Startup: notified %d Slack thread(s) about terminated flows",
        len(slack_runs),
    )


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Startup / shutdown lifecycle hook.

    Runs the same recovery tasks as the CLI on startup:
    0. Create MongoDB collections if they don't exist.
    1. Kill stale crew processes from a previous server crash.
    2. Mark incomplete crew-jobs as failed.
    2b. Mark unfinalized working ideas as failed (no auto-resume).
    3. Generate missing markdown outputs for completed ideas.
    4. Publish unpublished PRDs to Confluence (when credentials are set).
    """
    # 0. Ensure MongoDB collections and indexes exist
    try:
        ensure_collections()
    except Exception as exc:
        _logger.warning("Startup: MongoDB collection setup failed: %s", exc)

    # 0b. Validate Slack token availability
    try:
        from crewai_productfeature_planner.tools.slack_token_manager import get_valid_token
        token = get_valid_token()
        if token:
            _logger.info("Startup: Slack token available — bot will respond to events")
        else:
            _logger.warning(
                "Startup: No Slack token available — set SLACK_BOT_TOKEN in "
                ".env or complete the OAuth install flow. The bot will receive "
                "events but cannot respond."
            )
    except Exception as exc:
        _logger.warning("Startup: Slack token check failed: %s", exc)

    # 1. Kill stale processes
    _logger.info("Startup: killing stale crew processes...")
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

    # 2b. Fail unfinalized working ideas so old runs are not resumed
    terminated_ideas: list[dict] = []
    try:
        from crewai_productfeature_planner.mongodb.working_ideas import fail_unfinalized_on_startup
        terminated_ideas = fail_unfinalized_on_startup()
        if terminated_ideas:
            _logger.info(
                "Startup recovery: %d unfinalized idea(s) marked as failed",
                len(terminated_ideas),
            )
    except Exception as exc:
        _logger.warning("Startup recovery (fail unfinalized ideas) failed: %s", exc)

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

    # 8. Notify Slack threads about terminated flows (no auto-resume)
    try:
        _notify_terminated_flows(terminated_ideas)
    except Exception as exc:
        _logger.warning("Startup Slack termination notices failed: %s", exc)

    # 9. Install a safety-net threading.excepthook so uncaught exceptions
    #    in background threads (e.g. CrewAI subprocess crashes) are logged
    #    instead of silently killing the thread.
    import threading

    _original_excepthook = threading.excepthook

    def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
        _logger.error(
            "Uncaught exception in thread %s: %s",
            args.thread.name if args.thread else "<unknown>",
            args.exc_value,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_excepthook

    yield

    # ── Shutdown ──────────────────────────────────────────────────
    # Restore original thread exception hook
    threading.excepthook = _original_excepthook

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
