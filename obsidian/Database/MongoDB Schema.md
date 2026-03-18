# MongoDB Schema

> Collections, indexes, and document schemas.
> Hosted on **MongoDB Atlas** — connection via `MONGODB_ATLAS_URI` env var.
> Database name controlled by `MONGODB_DB` env var (default: `ideas`).
> Change `MONGODB_DB` to target a different database (e.g. `ideas_dev`, `ideas_uat`, `ideas_prod`).

## Collections (8 total)

Created by `ensure_collections()` in `scripts/setup_mongodb.py` on startup.

### `crewJobs`

Async job tracking for PRD flows.

```json
{
  "job_id": "str",
  "flow_name": "str",
  "idea": "str",
  "status": "queued|running|completed|failed|awaiting_approval|paused",
  "error": "str|null",
  "slack_channel": "str",
  "slack_thread_ts": "str",
  "current_section": "str",
  "current_section_key": "str",
  "current_section_step": "int",
  "total_sections": "int",
  "queued_at": "datetime",
  "started_at": "datetime",
  "completed_at": "datetime",
  "queue_time_ms": "int",
  "queue_time_human": "str",
  "running_time_ms": "int",
  "running_time_human": "str",
  "updated_at": "datetime"
}
```

Status flow: `queued` → `running` → `completed` | `failed` | `awaiting_approval` | `paused`

### `workingIdeas`

In-progress PRD persistence. Each iteration saved to MongoDB.

Key fields: `run_id`, `idea`, `original_idea`, `finalized_idea`, `status`, `project_id`, `slack_channel`, `slack_thread_ts`, `executive_summary`, `sections`, `jira_phase`, `jira_skeleton`, `jira_epics_stories_output`

Sub-modules: `_iterations.py`, `_finalization.py`, `_queries.py`, `_status.py`

### `productRequirements`

Completed PRD delivery records.

Key fields: `run_id`, `confluence_url`, `confluence_page_id`, `confluence_published`, `confluence_published_at`, `jira_tickets[]`, `jira_completed`, `status` (`new` | `inprogress` | `completed`)

### `projectConfig`

Per-project settings.

Key fields: `project_id`, `confluence_space_key`, `jira_project_key`, `figma_api_key`, `figma_team_id`, `figma_oauth_token`, `figma_oauth_refresh_token`, `figma_oauth_expires_at`

### `projectMemory`

Project-level memory store for agent context.

### `agentInteraction`

Slack interaction logging for LLM fine-tuning data.

### `userSession`

User session management.

### `slackOAuth`

Slack OAuth token persistence (per-team tokens).

## Key Repository Functions

### `crew_jobs/repository.py`
- `create_job()`, `update_job_status()`, `update_job_started()`, `update_job_completed()`
- `fail_incomplete_jobs_on_startup()`, `reactivate_job()`
- `find_active_job()`, `find_job()`, `list_jobs()`

### `working_ideas/`
- `save_iteration()`, `save_executive_summary()`, `save_pipeline_step()`
- `find_unfinalized()`, `find_ideas_by_project()`, `find_completed_ideas_by_project()`
- `save_slack_context()`, `save_project_ref()`, `mark_completed()`, `mark_paused()`, `mark_archived()`
- `save_jira_phase()`, `save_jira_skeleton()`, `get_jira_skeleton()`, `save_jira_epics_stories_output()`, `get_jira_epics_stories_output()`

---

See also: [[Server Lifecycle]], [[PRD Flow]]
