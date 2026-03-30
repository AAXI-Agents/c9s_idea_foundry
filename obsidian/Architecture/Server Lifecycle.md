# Server Lifecycle

> FastAPI startup and shutdown sequence in `apis/__init__.py`.

## Startup Steps (`_lifespan()`)

The FastAPI app runs startup steps in order:

| Step | Function | Purpose |
|------|---------|---------|
| 0 | `ensure_collections()` | Create missing MongoDB collections and indexes |
| 0b | `_validate_slack_token()` | Verify Slack token via `auth.test` — logs ERROR for expired/revoked tokens |
| 1 | Kill stale crew processes | Clean up from previous server crash |
| 2 | `fail_incomplete_jobs_on_startup()` | Mark orphaned crewJobs as `failed` |
| 2a | `archive_stale_jobs_on_startup()` | Archive crew jobs for user-archived ideas |
| 2b | `find_resumable_on_startup()` | Partition unfinalized working ideas: resumable (with Slack context) vs failed |
| 3 | Generate missing markdown outputs | For completed ideas missing output files |
| 4 | Run startup pipeline | Discover unpublished PRDs (uses optimized projection query) |
| 5 | Launch autonomous delivery crew | Confluence + Jira in background thread (daemon) |
| 6 | Start file watcher | `output/prds/` auto-publish on new `.md` files |
| 7 | Start cron scheduler | Periodic delivery scans |
| 7b | Start token refresh scheduler | Proactive Slack token rotation (every 30 min) |
| 8 | `_notify_terminated_flows()` | Slack notices for terminated flows |
| 8b | `_auto_resume_flows()` | Auto-resume flows with Slack context |
| 9 | Install `threading.excepthook` | Safety net for uncaught thread exceptions |

## CORS Configuration

The FastAPI app includes CORS middleware configured via `CORS_ALLOWED_ORIGINS` env var:
- Default: `http://localhost:3000` (local web app development)
- Set to your web app origin for production deployment
- Supports multiple origins (comma-separated)

## Shutdown

- Restores original `threading.excepthook`
- Stops file watcher
- Stops cron scheduler
- Stops token refresh scheduler

## Kill Old Runs on Restart (v0.6.0+)

Instead of auto-resuming, all unfinalized PRD flows are terminated on server restart:
- `fail_unfinalized_on_startup()` marks paused/in-progress working ideas as `failed`
- Slack threads receive a termination notice
- Users say "create prd" to start fresh with updated code

## Crash Prevention (v0.5.0+)

- All background thread targets catch `BaseException` (including `SystemExit`, `KeyboardInterrupt`)
- Global `threading.excepthook` installed during server lifespan as final safety net
- Prevents CrewAI subprocess crashes from taking down the server

---

See also: [[Project Overview]], [[Environment Variables]]
