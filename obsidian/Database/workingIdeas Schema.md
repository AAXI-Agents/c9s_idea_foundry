# workingIdeas Schema

> In-progress PRD persistence — every iteration, section draft, and lifecycle state is saved here.

**Collection**: `workingIdeas`
**Primary Key**: `run_id` (unique index)
**This is the most heavily written collection** — updated on every section iteration, critique, and status change.

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[PRD Flow API]] | `POST /flow/prd/kickoff` | Creates initial document |
| [[PRD Flow API]] | `GET /flow/runs/{run_id}` | Reads full run state for polling |
| [[PRD Flow API]] | `GET /flow/prd/resumable` | Queries unfinalized documents |
| [[PRD Flow API]] | `POST /flow/prd/approve` | Updates section state |
| [[PRD Flow API]] | `POST /flow/prd/resume` | Reads + resumes paused document |
| [[Ideas API]] | `GET /ideas` | Lists ideas by project/status |
| [[Ideas API]] | `GET /ideas/{run_id}` | Reads single idea with progress |
| [[Ideas API]] | `PATCH /ideas/{run_id}/status` | Updates status (archive/pause) |
| [[Slack API]] | Events router | Finds idea by thread for smart routing |
| [[Publishing API]] | Publishing endpoints | Reads completed ideas for delivery |

---

## Fields

### Core Identity

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `run_id` | `string` | **Yes** | — | Unique identifier for this flow run. Links to `crewJobs.job_id`. Primary key |
| `idea` | `string` | **Yes** | — | Original user-submitted idea text (never modified after creation) |
| `finalized_idea` | `string \| null` | No | `null` | Approved executive summary content — copy of the last executive summary iteration once Phase 1 completes. Empty until executive summary is approved |
| `status` | `string` | **Yes** | `"inprogress"` | Workflow lifecycle status (see Status Values below) |
| `error` | `string \| null` | No | `null` | Error message when `status` is `failed` — includes error code prefix (`LLM_ERROR`, `BILLING_ERROR`, `INTERNAL_ERROR`) |
| `project_id` | `string \| null` | No | `null` | FK → `projectConfig.project_id`. Associates this idea with a project for config (Confluence/Jira keys) |

### Timestamps

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `created_at` | `datetime (UTC)` | **Yes** | *now* | When the run was created |
| `completed_at` | `datetime \| null` | No | `null` | When the run completed — set by `mark_completed()` |
| `archived_at` | `datetime \| null` | No | `null` | When the run was archived — set by `mark_archived()` |
| `update_date` | `string (ISO-8601) \| null` | No | `null` | Last update timestamp — updated on every iteration save |

### Slack Context

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `slack_channel` | `string \| null` | No | `null` | Slack channel ID where the run was triggered — used for thread linking and auto-resume |
| `slack_thread_ts` | `string \| null` | No | `null` | Slack thread timestamp — unique thread identifier for context linking |

### Executive Summary (Phase 1)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `executive_summary` | `list[dict]` | No | `[]` | Array of executive summary iterations. Each element: `{ content: str, iteration: int, critique: str \| null, updated_date: str }`. Iterations accumulate — the latest entry is the current draft |

### Requirements Breakdown (Phase 1.5)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `requirements_breakdown` | `list[dict]` | No | `[]` | Array of requirements breakdown iterations. Each element: `{ content: str, iteration: int, critique: str \| null, step: int, updated_date: str }`. Produced by the Requirements Breakdown agent |

### PRD Sections (Phase 2)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `section` | `dict[str, list]` | No | `{}` | Section key → array of iteration records. Keys are section slugs (e.g. `"executive_summary"`, `"engineering_plan"`). Each iteration: `{ content: str, iteration: int, critique: str \| null, updated_date: str }`. See [[Ideas API]] for the 12 section keys |

### Output Files

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `output_file` | `string \| null` | No | `null` | Absolute path to the generated PRD markdown file on disk — set on flow finalization |
| `ux_output_file` | `string \| null` | No | `null` | Absolute path to the generated UX design markdown file — set if UX design phase ran |

### Jira Integration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `jira_phase` | `string` | No | `""` | Current Jira ticketing phase. Progression: `""` → `"skeleton_pending"` → `"skeleton_approved"` → `"epics_stories_done"` → `"subtasks_ready"` → `"subtasks_done"` |
| `jira_skeleton` | `string \| null` | No | `null` | Jira skeleton text (Epic/Story structure outline) — shown to user for review/approval before ticket creation |
| `jira_epics_stories_output` | `string \| null` | No | `null` | Agent output summary from Jira Phase 2 (Epics & Stories creation) |

### Figma Integration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `figma_design_url` | `string \| null` | No | `null` | URL to the Figma design file generated from the PRD |
| `figma_design_status` | `string \| null` | No | `null` | Design generation status: `null`, `"in_progress"`, or `"completed"` |

---

## Status Values

| Status | Description | Transitions to |
|--------|-------------|----------------|
| `inprogress` | PRD flow is actively running | `completed`, `paused`, `failed`, `archived` |
| `completed` | PRD generation finished successfully | `archived` |
| `paused` | Flow paused by user or auto-paused on error — can be resumed | `inprogress` (resume), `archived` |
| `failed` | Flow failed — can be resumed after fixing | `inprogress` (resume), `archived` |
| `archived` | Soft-deleted — hidden from default views | (terminal) |

---

## Jira Phase Values

| Phase | Description |
|-------|-------------|
| `""` (empty) | No Jira activity yet |
| `skeleton_pending` | Skeleton generated, awaiting user approval |
| `skeleton_approved` | User approved skeleton, Epics/Stories creation in progress |
| `epics_stories_done` | Phase 2 complete — Epics & Stories created |
| `subtasks_ready` | Sub-tasks approved by user, ready for creation |
| `subtasks_done` | All Jira tickets created (terminal) |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `run_id` | Unique, Ascending | Primary key lookup |
| `(status, created_at DESC)` | Compound | Filter by status, newest first |
| `(project_id, status, created_at DESC)` | Compound | Filter ideas by project + status |
| `(slack_channel, status)` | Compound | Find active ideas in a Slack channel |

---

## Repository Functions

**Source**: `mongodb/working_ideas/` (sub-modules: `_iterations.py`, `_finalization.py`, `_queries.py`, `_status.py`)

### Iteration Management
| Function | Purpose |
|----------|---------|
| `save_iteration()` | Persist section iteration (content + critique) |
| `update_section_critique()` | Update critique on existing iteration |
| `save_executive_summary()` | Persist executive summary iteration |
| `update_executive_summary_critique()` | Update executive summary critique |
| `save_finalized_idea()` | Copy approved content to `finalized_idea` |
| `save_pipeline_step()` | Persist requirements breakdown iteration |
| `ensure_section_field()` | Ensure `section` dict exists on document |

### Status Management
| Function | Purpose |
|----------|---------|
| `mark_completed()` | Set status to `completed`, set `completed_at` |
| `mark_paused()` | Set status to `paused` |
| `mark_archived()` | Set status to `archived`, set `archived_at` |
| `save_failed()` | Set status to `failed` with error message |

### Queries
| Function | Purpose |
|----------|---------|
| `find_unfinalized()` | Find ideas not yet completed |
| `find_resumable_on_startup()` | Partition unfinalized into resumable vs failed |
| `fail_unfinalized_on_startup()` | Mark all unfinalized as failed on restart |
| `find_completed_without_confluence()` | Find completed ideas not published |
| `find_completed_without_output()` | Find completed ideas missing output file |
| `find_ideas_by_project()` | Find ideas for a project (paginated) |
| `find_completed_ideas_by_project()` | Find completed ideas for a project |
| `find_idea_by_thread()` | Find idea by Slack channel + thread_ts |
| `find_run_any_status()` | Fetch document by run_id |
| `get_run_documents()` | Fetch multiple runs by run_ids |
| `has_active_idea_flow()` | Check if user has active PRD flow |

### Context & Output
| Function | Purpose |
|----------|---------|
| `save_slack_context()` | Persist Slack channel and thread_ts |
| `save_project_ref()` | Associate run with project config |
| `save_output_file()` | Store generated PRD file path |
| `get_output_file()` | Fetch current output_file path |
| `save_ux_output_file()` | Store UX design file path |
| `get_ux_output_file()` | Fetch current UX output file path |
| `save_jira_phase()` | Persist current Jira phase |
| `save_jira_skeleton()` | Persist Jira skeleton text |
| `get_jira_skeleton()` | Fetch Jira skeleton text |
| `save_jira_epics_stories_output()` | Persist Phase 2 Jira output |
| `get_jira_epics_stories_output()` | Fetch Phase 2 Jira output |
| `save_figma_design()` | Persist Figma URL and status |

---

## Related Collections

| Collection | Relationship |
|------------|-------------|
| [[crewJobs Schema]] | `run_id` = `crewJobs.job_id` (1:1) |
| [[projectConfig Schema]] | `project_id` → `projectConfig.project_id` (N:1) |
| [[productRequirements Schema]] | `run_id` = `productRequirements.run_id` (1:1) |

---

See also: [[MongoDB Schema]], [[PRD Flow API]], [[Ideas API]], [[PRD Flow]]
