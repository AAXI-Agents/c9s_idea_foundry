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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from crewai_productfeature_planner.apis.dashboard.router import router as dashboard_router
from crewai_productfeature_planner.apis.health.router import router as health_router
from crewai_productfeature_planner.apis.ideas.router import router as ideas_router
from crewai_productfeature_planner.apis.prd.router import router as prd_router
from crewai_productfeature_planner.apis.prd.router import ws_only_router as prd_ws_router
from crewai_productfeature_planner.apis.projects.router import router as projects_router
from crewai_productfeature_planner.apis.publishing.router import router as publishing_router
from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus  # noqa: F401 (re-export)
from crewai_productfeature_planner.apis.slack.events_router import router as slack_events_router
from crewai_productfeature_planner.apis.slack.interactions_router import router as slack_interactions_router
from crewai_productfeature_planner.apis.slack.oauth_router import router as slack_oauth_router
from crewai_productfeature_planner.apis.slack.router import router as slack_router
from crewai_productfeature_planner.apis.integrations.router import router as integrations_router
from crewai_productfeature_planner.apis.sso.router import router as sso_auth_router
from crewai_productfeature_planner.apis.sso_webhooks import router as sso_webhooks_router
from crewai_productfeature_planner.apis.user_profile.router import router as user_profile_router
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
                "You can start a fresh run by describing your idea again."
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


def _auto_resume_flows(resumable: list[dict]) -> None:
    """Auto-resume PRD flows that were interrupted by a server restart.

    For each resumable run, posts a notification to the original Slack
    thread and spawns a background thread to resume the PRD flow from
    where it left off.

    Args:
        resumable: List of dicts from ``find_resumable_on_startup``,
            each containing ``run_id``, ``idea``, ``slack_channel``,
            ``slack_thread_ts``, ``project_id``.
    """
    if not resumable:
        return

    import threading

    try:
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
        send_tool = SlackSendMessageTool()
    except Exception:  # noqa: BLE001
        _logger.debug("Could not create SlackSendMessageTool for auto-resume")
        return

    for run_info in resumable:
        run_id = run_info["run_id"]
        channel = run_info.get("slack_channel", "")
        thread_ts = run_info.get("slack_thread_ts", "")
        idea = run_info.get("idea", "")
        project_id = run_info.get("project_id")

        if not channel or not thread_ts:
            continue

        # Notify the user that we're resuming
        try:
            send_tool.run(
                channel=channel,
                text=(
                    ":arrows_counterclockwise: *Server restarted.* "
                    f"Auto-resuming PRD flow for:\n> _{idea}_\n"
                    "I'll continue from where I left off."
                ),
                thread_ts=thread_ts,
            )
        except Exception:  # noqa: BLE001
            _logger.debug(
                "Could not notify Slack about resumed flow %s", run_id,
                exc_info=True,
            )

        # Spawn background thread for resume
        t = threading.Thread(
            target=_resume_flow_background,
            args=(run_id, channel, thread_ts, project_id),
            name=f"auto-resume-{run_id[:8]}",
            daemon=True,
        )
        t.start()
        _logger.info(
            "Startup auto-resume: launched thread for run_id=%s", run_id,
        )

    _logger.info(
        "Startup: auto-resuming %d flow(s)", len(resumable),
    )


def _resume_flow_background(
    run_id: str,
    channel: str,
    thread_ts: str,
    project_id: str | None,
) -> None:
    """Background thread target: resume a single PRD flow."""
    try:
        # Double-check the idea is not archived before resuming
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_run_any_status,
        )
        doc = find_run_any_status(run_id)
        if doc and doc.get("status") == "archived":
            _logger.info(
                "Startup auto-resume: skipping run_id=%s — already archived",
                run_id,
            )
            return

        from crewai_productfeature_planner.apis.slack.router import (
            _run_slack_resume_flow,
        )
        _run_slack_resume_flow(
            run_id=run_id,
            channel=channel,
            thread_ts=thread_ts,
            project_id=project_id,
        )
    except Exception as exc:
        _logger.error(
            "Auto-resume failed for run_id=%s: %s", run_id, exc,
            exc_info=True,
        )
        try:
            from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool
            send_tool = SlackSendMessageTool()
            send_tool.run(
                channel=channel,
                text=(
                    f":x: Auto-resume failed for this PRD flow. "
                    f"Error: {exc}\n"
                    "You can start a fresh run by describing your idea again."
                ),
                thread_ts=thread_ts,
            )
        except Exception:  # noqa: BLE001
            pass


def _validate_slack_token() -> bool:
    """Validate the Slack bot token is usable via ``auth.test``.

    Returns ``True`` when the token is confirmed valid, ``False``
    otherwise.  Logs at appropriate levels so administrators can
    detect expired/revoked tokens immediately on startup.
    """
    from crewai_productfeature_planner.tools.slack_token_manager import get_valid_token

    token = get_valid_token()
    if not token:
        _logger.warning(
            "Startup: No Slack token available — set SLACK_BOT_TOKEN in "
            ".env or complete the OAuth install flow. The bot will receive "
            "events but cannot respond."
        )
        return False

    # Verify token is actually usable — not just present
    try:
        from slack_sdk import WebClient

        _test_client = WebClient(token=token)
        _auth_result = _test_client.auth_test()
        if _auth_result.get("ok"):
            _logger.info(
                "Startup: Slack token validated — bot will respond "
                "to events (team=%s, bot=%s)",
                _auth_result.get("team_id", "?"),
                _auth_result.get("user_id", "?"),
            )
            return True
        _logger.error(
            "Startup: Slack token exists but auth.test failed "
            "(error=%s). The bot CANNOT respond to events — "
            "re-install the Slack app to obtain a new token.",
            _auth_result.get("error", "unknown"),
        )
        return False
    except Exception as auth_exc:
        _err_str = str(auth_exc).lower()
        if any(kw in _err_str for kw in (
            "token_expired", "token_revoked", "invalid_auth",
            "not_authed", "account_inactive",
        )):
            _logger.error(
                "Startup: Slack token is EXPIRED or REVOKED — the "
                "bot CANNOT respond to events. Re-install the Slack "
                "app to obtain a new token. (error: %s)",
                auth_exc,
            )
            return False
        # Network blip etc. — assume token might still be OK
        _logger.warning(
            "Startup: Slack auth.test check failed (non-token "
            "error, bot may still work): %s",
            auth_exc,
        )
        return True


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

    # 0b. Validate Slack token availability (incl. auth.test check)
    try:
        _validate_slack_token()
    except Exception as exc:
        _logger.warning("Startup: Slack token check failed: %s", exc)

    # 0c. Fix CrewAI event bus: unregister the atexit shutdown handler
    #     and reinitialise the bus if it was left in a dead state from
    #     a prior dirty shutdown.
    try:
        from crewai_productfeature_planner.scripts.crewai_bus_fix import (
            install_crewai_bus_fix,
        )
        install_crewai_bus_fix()
    except Exception as exc:
        _logger.warning("Startup: CrewAI bus fix failed: %s", exc)

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

    # 2a. Archive stale crew jobs whose ideas were archived by user
    try:
        from crewai_productfeature_planner.mongodb.crew_jobs import archive_stale_jobs_on_startup
        archived_count = archive_stale_jobs_on_startup()
        if archived_count:
            _logger.info("Startup: archived %d stale crew job(s) for archived ideas", archived_count)
    except Exception as exc:
        _logger.warning("Startup (archive stale jobs) failed: %s", exc)

    # 2b. Partition unfinalized working ideas into resumable vs failed.
    #     Resumable ideas (with Slack context) will be auto-resumed
    #     after startup completes.  Others are marked failed.
    resumable_ideas: list[dict] = []
    terminated_ideas: list[dict] = []
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_resumable_on_startup,
        )
        resumable_ideas, terminated_ideas = find_resumable_on_startup()
        if resumable_ideas:
            _logger.info(
                "Startup: %d idea(s) will be auto-resumed",
                len(resumable_ideas),
            )
        if terminated_ideas:
            _logger.info(
                "Startup recovery: %d unfinalized idea(s) marked as failed",
                len(terminated_ideas),
            )
    except Exception as exc:
        _logger.warning("Startup recovery (partition unfinalized ideas) failed: %s", exc)

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

    # 7b. Token refresh scheduler: proactively refresh Slack tokens
    try:
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            start_token_refresh_scheduler,
        )
        if start_token_refresh_scheduler():
            _logger.info("Token refresh scheduler: started")
    except Exception as exc:
        _logger.warning("Token refresh scheduler failed to start: %s", exc)

    # 8. Notify Slack threads about terminated flows
    try:
        _notify_terminated_flows(terminated_ideas)
    except Exception as exc:
        _logger.warning("Startup Slack termination notices failed: %s", exc)

    # 8b. Auto-resume flows that have Slack context
    try:
        _auto_resume_flows(resumable_ideas)
    except Exception as exc:
        _logger.warning("Startup auto-resume failed: %s", exc)

    # 8c. SSO public key refresh scheduler
    try:
        from crewai_productfeature_planner.apis.sso_auth import (
            start_key_refresh_scheduler,
        )
        if start_key_refresh_scheduler():
            _logger.info("SSO key refresh scheduler: started")
    except Exception as exc:
        _logger.warning("SSO key refresh scheduler failed to start: %s", exc)

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
    try:
        from crewai_productfeature_planner.tools.token_refresh_scheduler import (
            stop_token_refresh_scheduler,
        )
        stop_token_refresh_scheduler()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(
    title="Idea Foundry — CrewAI Product Feature Planner API",
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
        {
            "name": "SSO Webhooks",
            "description": (
                "Receives user lifecycle events from the C9 SSO service "
                "(user.created, user.updated, user.deleted, login.success, "
                "login.failed, token.revoked). "
                "Payloads are verified with HMAC-SHA256 via the "
                "X-Webhook-Signature header using SSO_WEBHOOK_SECRET."
            ),
        },
        {
            "name": "SSO",
            "description": (
                "C9S Single Sign-On integration (OAuth2 + RS256 JWT). "
                "Provides login, registration, password reset, token "
                "refresh, re-authentication, and logout. All auth flows "
                "use email-based 6-digit 2FA codes. Login, registration, "
                "and password-reset are public (no Bearer). Re-auth, "
                "logout, and userinfo require a valid Bearer token."
            ),
        },
        {
            "name": "Projects",
            "description": (
                "CRUD operations for project configurations. "
                "Create, read, update, delete, and list projects with "
                "paginated results (10, 25, or 50 per page)."
            ),
        },
        {
            "name": "Ideas",
            "description": (
                "Browse and manage working ideas (PRD runs). "
                "List ideas with paginated results, filter by project "
                "or status, view details, and update status."
            ),
        },
    ],
)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(prd_router)
app.include_router(prd_ws_router)
app.include_router(slack_router)
app.include_router(slack_events_router)
app.include_router(slack_interactions_router)
app.include_router(slack_oauth_router)
app.include_router(projects_router)
app.include_router(ideas_router)
app.include_router(publishing_router)
app.include_router(integrations_router)
app.include_router(sso_auth_router)
app.include_router(sso_webhooks_router)
app.include_router(user_profile_router)

# ── CORS — required for web-based SSO login flows ────────────
import os as _os

_cors_origins = [
    o.strip()
    for o in _os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request latency middleware ────────────────────────────────
import time as _time


_SLOW_REQUEST_THRESHOLD_MS = 2000  # log a warning when request exceeds this


@app.middleware("http")
async def _latency_middleware(request: Request, call_next):
    """Log request duration and expose it via the X-Process-Time header.

    Requests slower than ``_SLOW_REQUEST_THRESHOLD_MS`` are logged at
    WARNING level to surface latency bottlenecks.
    """
    start = _time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (_time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.1f}ms"
    method = request.method
    path = request.url.path
    status_code = response.status_code
    if elapsed_ms > _SLOW_REQUEST_THRESHOLD_MS:
        _logger.warning(
            "[API] Slow request: %s %s → %d (%.0fms)",
            method, path, status_code, elapsed_ms,
        )
    else:
        _logger.debug(
            "[API] %s %s → %d (%.0fms)",
            method, path, status_code, elapsed_ms,
        )
    return response


# ── Global exception handler ─────────────────────────────────


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Return a structured ErrorResponse for any unhandled server error.

    This ensures every API endpoint returns a consistent JSON envelope
    (``ErrorResponse``) instead of a bare 500 HTML page, making errors
    machine-readable for MCP clients and dashboards.
    """
    from crewai_productfeature_planner.scripts.retry import (
        BillingError, LLMError, ShutdownError,
    )

    if isinstance(exc, BillingError):
        status_code = 503
        error_code = "BILLING_ERROR"
    elif isinstance(exc, ShutdownError):
        status_code = 503
        error_code = "SHUTDOWN"
    elif isinstance(exc, LLMError):
        status_code = 503
        error_code = "LLM_ERROR"
    else:
        status_code = 500
        error_code = "INTERNAL_ERROR"

    _logger.error(
        "Unhandled %s in %s %s: %s",
        error_code, request.method, request.url.path, exc,
        exc_info=True,
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": "An internal error occurred. Check server logs for details.",
            "run_id": None,
            "detail": error_code,
        },
    )
