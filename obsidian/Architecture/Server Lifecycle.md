# Server Lifecycle

> FastAPI startup and shutdown sequence in `apis/__init__.py`.

## Startup Steps (`_lifespan()`)

The FastAPI app runs 10 startup steps in order:

| Step | Function | Purpose |
|------|---------|---------|
| 0 | `ensure_collections()` | Create missing MongoDB collections and indexes |
| 0b | Token validation | Log warning if no Slack token available |
| 1 | Kill stale crew processes | Clean up from previous server crash |
| 2 | `fail_incomplete_jobs_on_startup()` | Mark orphaned crewJobs as `failed` |
| 2b | `fail_unfinalized_on_startup()` | Mark unfinalized working ideas as `failed` |
| 3 | Generate missing markdown outputs | For completed ideas missing output files |
| 4 | Run startup pipeline | Review + Confluence publish via orchestrator |
| 5 | Launch autonomous delivery crew | Confluence + Jira in background thread |
| 6 | Start file watcher | `output/prds/` auto-publish on new `.md` files |
| 7 | Start cron scheduler | Periodic delivery scans |
| 8 | `_notify_terminated_flows()` | Slack notices for terminated flows |
| 9 | Install `threading.excepthook` | Safety net for uncaught thread exceptions |

## Shutdown

- Restores original `threading.excepthook`
- Stops file watcher
- Stops cron scheduler

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
