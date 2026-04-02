---
tags:
  - database
  - mongodb
---

# crewJobs Schema

> Async job tracking for PRD flow runs — status, timing, and lifecycle management.

**Collection**: `crewJobs`
**Primary Key**: `job_id` (unique index)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[PRD Flow API]] | `POST /flow/prd/kickoff` | Creates job in `queued` status |
| [[PRD Flow API]] | `POST /flow/prd/resume` | Reactivates paused job |
| [[PRD Flow API]] | `POST /flow/prd/approve` | Updates status during approval |
| [[PRD Flow API]] | `GET /flow/jobs` | Lists jobs with filters |
| [[PRD Flow API]] | `GET /flow/jobs/{job_id}` | Fetches single job record |
| [[Slack API]] | `POST /slack/kickoff` | Creates job for Slack-triggered flow |

---

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `job_id` | `string` | **Yes** | — | Unique job identifier — same value as `workingIdeas.run_id`. Primary key |
| `flow_name` | `string` | **Yes** | — | Name of the flow being executed (always `"prd"` currently) |
| `idea` | `string` | **Yes** | — | Feature idea / input text submitted by the user |
| `status` | `string` | **Yes** | `"queued"` | Job lifecycle status (see Status Values below) |
| `error` | `string \| null` | No | `null` | Error message when job was paused or failed due to an LLM, billing, or internal error |
| `slack_channel` | `string \| null` | No | `null` | Slack channel ID where the run was triggered — used for auto-resume context |
| `slack_thread_ts` | `string \| null` | No | `null` | Slack thread timestamp — used for auto-resume context |
| `queued_at` | `datetime (UTC)` | **Yes** | *now* | When the job was created |
| `started_at` | `datetime \| null` | No | `null` | When execution began — set when status transitions from `queued` to `running` |
| `completed_at` | `datetime \| null` | No | `null` | When the job reached a terminal state (`completed`, `failed`, or `paused`) |
| `queue_time_ms` | `int \| null` | No | `null` | Time spent in queue (`started_at - queued_at`) in milliseconds — computed on transition to `running` |
| `queue_time_human` | `string \| null` | No | `null` | Human-readable queue duration (e.g. `"0h 0m 12s"`) |
| `running_time_ms` | `int \| null` | No | `null` | Time spent running (`completed_at - started_at`) in milliseconds — computed on completion |
| `running_time_human` | `string \| null` | No | `null` | Human-readable running duration (e.g. `"1h 23m 45s"`) |
| `updated_at` | `datetime (UTC)` | **Yes** | *now* | Last status update timestamp — auto-set on every update |

---

## Status Values

| Status | Description | Transitions to |
|--------|-------------|----------------|
| `queued` | Job created, waiting for execution slot | `running` |
| `running` | Flow actively executing | `completed`, `awaiting_approval`, `paused`, `failed` |
| `awaiting_approval` | Paused for user section approval (interactive mode) | `running` (on approve/reject) |
| `paused` | Paused due to error or user request — can be resumed | `running` (on resume) |
| `completed` | Flow finished successfully | (terminal) |
| `failed` | Flow failed and cannot auto-recover | (terminal) |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `job_id` | Unique, Ascending | Primary key lookup |
| `(status, queued_at DESC)` | Compound | Filter jobs by status, ordered by queue time |

---

## Repository Functions

**Source**: `mongodb/crew_jobs/repository.py`

| Function | Purpose |
|----------|---------|
| `create_job()` | Insert new job in `queued` status |
| `find_active_job()` | Return the single incomplete job (if any) |
| `find_job(job_id)` | Fetch a single job by ID |
| `list_jobs(status, flow_name, limit)` | List jobs with optional filters |
| `update_job_status(job_id, status, **extra)` | Generic status update |
| `update_job_started(job_id)` | Mark as `running`, compute queue time |
| `update_job_completed(job_id, status)` | Mark as completed/paused, compute running time |
| `update_job_failed(job_id, error)` | Mark as `failed` with error message |
| `reactivate_job(job_id)` | Reactivate a paused job for resume |
| `fail_incomplete_jobs_on_startup()` | Fail all incomplete jobs on server restart |
| `archive_stale_jobs_on_startup()` | Archive old stale jobs |

---

## Related Collections

| Collection | Relationship |
|------------|-------------|
| [[workingIdeas Schema]] | `job_id` = `workingIdeas.run_id` (1:1) |

---

See also: [[MongoDB Schema]], [[PRD Flow API]], [[Server Lifecycle]]


---

## Change Requests

<!-- 
HOW TO USE: Add your change requests below as bullet points.
Codex will implement each request, update this page, bump the
version, and move the completed item to the "Completed" list.

FORMAT:
- [ ] <your change request here>

EXAMPLE:
- [ ] Add a new field `priority` (string, optional) to the response
- [ ] Rename endpoint from /v1/old to /v2/new
-->

### Pending

_No pending change requests._

### Completed

_No completed change requests._
