---
tags:
  - api
  - endpoints
---

# PRD Flow API

> [!warning] Deprecated — Use Per-Route Files
> This monolithic file is superseded by individual per-route files in [[PRD Flow/]].
> Each endpoint now has its own file with detailed request, response, and database algorithm.
> **Edit the per-route files instead.** This file is kept for historical reference only.

---


> Start, monitor, approve, pause, and resume PRD generation flows.

**Base path**: `/flow`
**Auth**: SSO Bearer token (all endpoints)

---

## Endpoints

| Method | Path | Auth | Request | Response | Status | Purpose |
|--------|------|------|---------|----------|--------|---------|
| `POST` | `/flow/prd/kickoff` | SSO | `PRDKickoffRequest` | `PRDKickoffResponse` | 202 | Start PRD generation (async) |
| `POST` | `/flow/prd/approve` | SSO | `PRDApproveRequest` | `PRDActionResponse` | 200 | Approve section or send feedback |
| `POST` | `/flow/prd/pause` | SSO | `PRDPauseRequest` | `PRDActionResponse` | 200 | Pause a running flow |
| `POST` | `/flow/prd/resume` | SSO | `PRDResumeRequest` | `PRDResumeResponse` | 202 | Resume a paused flow |
| `GET` | `/flow/runs/{run_id}` | SSO | — | `PRDRunStatusResponse` | 200 | Poll flow progress |
| `GET` | `/flow/runs` | SSO | — | `RunListResponse` | 200 | List all in-memory flow runs |
| `GET` | `/flow/prd/resumable` | SSO | — | `PRDResumableListResponse` | 200 | List resumable runs from MongoDB |
| `GET` | `/flow/jobs` | SSO | query params | `JobListResponse` | 200 | List persistent job records |
| `GET` | `/flow/jobs/{job_id}` | SSO | — | `JobDetail` | 200 | Get single job record |

---

## Web App Integration Flow

Typical frontend workflow for interactive PRD generation:

1. **Start**: `POST /flow/prd/kickoff` with `{ "idea": "..." }` → receive `run_id`
2. **Poll**: `GET /flow/runs/{run_id}` every 5 seconds
3. **Review**: When `status = "awaiting_approval"`, display `current_draft` sections
4. **Approve**: `POST /flow/prd/approve` with `{ "run_id": "...", "approve": true }` — or `{ "approve": false, "feedback": "..." }` to request changes
5. **Repeat**: Continue polling until `status = "completed"`
6. **Auto mode**: Set `auto_approve: true` in kickoff to skip manual review — poll only

---

## Request Schemas

### PRDKickoffRequest

`POST /flow/prd/kickoff`

```json
{
  "idea": "Add dark mode to the dashboard with system preference detection",
  "title": "Dark Mode Dashboard",
  "project_id": "proj-abc123",
  "auto_approve": false
}
```

| Field | Type | Required | Constraints | Default | Description |
|-------|------|----------|-------------|---------|-------------|
| `idea` | `string` | **Yes** | 1–50,000 chars | — | The product feature idea to build a PRD for |
| `title` | `string` | No | max 256 chars | `""` | Short display title for the idea. Used in dashboards and project views. When empty, the first line of the idea text is used as a fallback |
| `project_id` | `string` | No | max 50 chars | `""` | Associate this PRD run with an existing project. Links the idea to the project so it inherits Confluence/Jira config. When empty, the idea is created without a project |
| `auto_approve` | `bool` | No | — | `false` | When `true`, the flow runs end-to-end without pausing for manual approval. Sections auto-iterate between `PRD_SECTION_MIN_ITERATIONS` and `PRD_SECTION_MAX_ITERATIONS` and auto-approve when critique contains `SECTION_READY`. The `/flow/prd/approve` endpoint is not needed — poll `/flow/runs/{run_id}` for progress instead |

---

### PRDApproveRequest

`POST /flow/prd/approve`

```json
{
  "run_id": "a1b2c3d4e5f6",
  "approve": true,
  "feedback": null,
  "selected_agent": null
}
```

| Field | Type | Required | Constraints | Default | Description |
|-------|------|----------|-------------|---------|-------------|
| `run_id` | `string` | **Yes** | — | — | The run to approve or continue |
| `approve` | `bool` | **Yes** | — | — | `true` to approve the current section and move to the next. `false` to keep refining |
| `feedback` | `string \| null` | No | max 10,000 chars | `null` | User critique feedback. When provided with `approve: false`, this replaces the agent's self-critique for the current section iteration |
| `selected_agent` | `string \| null` | No | `"openai"` or `"gemini"` | `null` | Which agent's draft to use. Required when multiple agents produced results (parallel drafting). Defaults to the first available agent |

---

### PRDPauseRequest

`POST /flow/prd/pause`

```json
{
  "run_id": "a1b2c3d4e5f6"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | **Yes** | The run to pause. Flow will stop after the current iteration completes |

---

### PRDResumeRequest

`POST /flow/prd/resume`

```json
{
  "run_id": "a1b2c3d4e5f6",
  "auto_approve": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `run_id` | `string` | **Yes** | — | The `run_id` of an unfinalized working idea to resume |
| `auto_approve` | `bool` | No | `false` | When `true`, the resumed flow runs end-to-end without pausing for approval. Poll `/flow/runs/{run_id}` for progress instead of calling `/flow/prd/approve` |

---

## Response Schemas

### PRDKickoffResponse

`POST /flow/prd/kickoff` → 202

```json
{
  "run_id": "a1b2c3d4e5f6",
  "flow_name": "prd",
  "status": "running",
  "message": "PRD flow started for idea: Add dark mode..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | Unique identifier for this flow run — use in all subsequent API calls |
| `flow_name` | `string` | Always `"prd"` |
| `status` | `string` | Initial status — typically `"running"` |
| `message` | `string` | Human-readable confirmation message |

---

### PRDActionResponse

`POST /flow/prd/approve`, `POST /flow/prd/pause`

```json
{
  "run_id": "a1b2c3d4e5f6",
  "action": "approved",
  "section": "executive_summary",
  "current_step": 1,
  "sections_approved": 1,
  "sections_total": 12,
  "is_final_section": false,
  "active_agents": ["openai"],
  "dropped_agents": [],
  "agent_errors": {},
  "message": "Section 'Executive Summary' approved (1/12)"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | The run this action was applied to |
| `action` | `string` | — | Action taken: `"approved"`, `"continuing refinement"`, `"continuing refinement with user feedback"`, or `"paused"` |
| `section` | `string` | `""` | Section key the action was applied to (e.g. `"executive_summary"`) |
| `current_step` | `int \| null` | `null` | 1-based step number of the current section (1–12) |
| `sections_approved` | `int \| null` | `null` | Number of sections approved so far (including this one if approved) |
| `sections_total` | `int \| null` | `null` | Total number of sections in the PRD (12) |
| `is_final_section` | `bool` | `false` | `true` when this approval completed the last section — the flow will finalize |
| `active_agents` | `string[]` | `[]` | Provider identifiers currently participating (e.g. `["openai"]`, `["gemini", "openai"]`) |
| `dropped_agents` | `string[]` | `[]` | Providers removed after failing during parallel drafting |
| `agent_errors` | `dict[string, string]` | `{}` | Map of dropped provider name → error message |
| `message` | `string` | — | Human-readable result message |

---

### PRDRunStatusResponse

`GET /flow/runs/{run_id}`

Full flow state for polling.

```json
{
  "run_id": "a1b2c3d4e5f6",
  "flow_name": "prd",
  "status": "awaiting_approval",
  "iteration": 5,
  "created_at": "2026-03-20T10:30:00Z",
  "update_date": "2026-03-20T10:35:00Z",
  "completed_at": null,
  "result": null,
  "error": null,
  "current_section_key": "executive_summary",
  "current_step": 1,
  "sections_approved": 0,
  "sections_total": 12,
  "active_agents": ["openai"],
  "dropped_agents": [],
  "agent_errors": {},
  "original_idea": "Add dark mode",
  "idea_refined": true,
  "finalized_idea": "## Dark Mode Dashboard\n...",
  "requirements_breakdown": "## Requirements\n...",
  "executive_summary": { "iterations": [], "is_approved": false },
  "confluence_url": "",
  "jira_output": "",
  "output_file": "",
  "current_draft": {
    "sections": [],
    "all_approved": false
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | Unique run identifier |
| `flow_name` | `string` | — | Always `"prd"` |
| `status` | `string` | — | Current lifecycle status: `"running"`, `"awaiting_approval"`, `"paused"`, `"completed"` |
| `iteration` | `int` | `0` | Total iteration count across all sections. Phase 1 (Executive Summary) iterates ≥ `PRD_EXEC_RESUME_THRESHOLD` times, Phase 2 sections each iterate between `PRD_SECTION_MIN_ITERATIONS` and `PRD_SECTION_MAX_ITERATIONS` |
| `created_at` | `string` | — | ISO-8601 creation timestamp |
| `update_date` | `string \| null` | `null` | ISO-8601 timestamp of the last update |
| `completed_at` | `string \| null` | `null` | ISO-8601 completion timestamp — `null` while running |
| `result` | `string \| null` | `null` | Final result summary when completed |
| `error` | `string \| null` | `null` | Error message if paused due to error. Prefixed with error code: `BILLING_ERROR`, `LLM_ERROR`, or `INTERNAL_ERROR`. Errors always result in `status: "paused"` (never `"failed"`), so the run can be resumed |
| `current_section_key` | `string` | `""` | Key of the section currently being iterated (e.g. `"executive_summary"`) |
| `current_step` | `int` | `0` | 1-based step number of the current section (1–12) |
| `sections_approved` | `int` | `0` | Number of approved sections (convenience, derivable from `current_draft`) |
| `sections_total` | `int` | `0` | Total number of PRD sections (12) |
| `active_agents` | `string[]` | `[]` | Provider identifiers currently participating (e.g. `["openai"]`) |
| `dropped_agents` | `string[]` | `[]` | Providers removed after failing during parallel drafting |
| `agent_errors` | `dict[string, string]` | `{}` | Map of dropped provider → error message |
| `original_idea` | `string` | `""` | Raw idea text before refinement. Empty when refinement was skipped |
| `idea_refined` | `bool` | `false` | Whether the idea was processed by the Idea Refinement agent |
| `finalized_idea` | `string` | `""` | Enriched executive summary after Phase 1 completes. Empty until executive summary loop finishes |
| `requirements_breakdown` | `string` | `""` | Structured product requirements from the Requirements Breakdown agent. Empty until breakdown phase completes |
| `executive_summary` | `ExecutiveSummaryDraft` | `{}` | Iterative executive summary from Phase 1 — contains full iteration history |
| `confluence_url` | `string` | `""` | Confluence page URL — empty until post-completion publishing succeeds |
| `jira_output` | `string` | `""` | Summary of Jira tickets created — empty until post-completion ticketing completes |
| `output_file` | `string` | `""` | Path to generated PRD markdown file — empty until flow finalizes |
| `current_draft` | `PRDDraftDetail` | `{}` | Full structured draft with per-section state (see below) |

---

### ExecutiveSummaryDraft

Nested in `PRDRunStatusResponse.executive_summary`.

| Field | Type | Description |
|-------|------|-------------|
| `iterations` | `ExecutiveSummaryIteration[]` | Full iteration history |
| `is_approved` | `bool` | Whether the executive summary has been approved |

#### ExecutiveSummaryIteration

| Field | Type | Description |
|-------|------|-------------|
| `content` | `string` | Markdown content of this iteration |
| `iteration` | `int` | 1-based iteration number |
| `critique` | `string \| null` | Critique feedback from `critique_prd_task` — `null` on first iteration |
| `updated_date` | `string` | ISO-8601 timestamp of this iteration |

---

### PRDDraftDetail

Nested in `PRDRunStatusResponse.current_draft`.

| Field | Type | Description |
|-------|------|-------------|
| `sections` | `PRDSectionDetail[]` | Ordered list of PRD sections with their current state |
| `all_approved` | `bool` | `true` when every section has been approved |

#### PRDSectionDetail

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `key` | `string` | — | Section identifier slug (e.g. `"executive_summary"`) |
| `title` | `string` | — | Human-readable section title (e.g. `"Executive Summary"`) |
| `step` | `int` | `0` | 1-based step number in the PRD workflow (1–12) |
| `content` | `string` | `""` | Current markdown content of this section |
| `critique` | `string` | `""` | Latest critique text from the critique agent |
| `iteration` | `int` | `0` | How many times this section has been iterated |
| `updated_date` | `string` | `""` | ISO-8601 timestamp of the last update |
| `is_approved` | `bool` | `false` | Whether the user has approved this section |
| `agent_results` | `dict[string, string]` | `{}` | Per-agent draft results. Keys are provider IDs (e.g. `"openai"`), values are the markdown content each agent produced |
| `selected_agent` | `string` | `""` | Which agent's result was selected by the user. Empty = no selection made |

---

### PRDResumableRun

`GET /flow/prd/resumable`

```json
{
  "run_id": "a1b2c3d4e5f6",
  "idea": "Add dark mode to the dashboard",
  "iteration": 12,
  "created_at": "2026-03-20T10:30:00Z",
  "sections": ["executive_summary", "executive_product_summary"],
  "exec_summary_iterations": 5,
  "req_breakdown_iterations": 2
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | Unique run identifier |
| `idea` | `string` | `""` | The feature idea text |
| `iteration` | `int` | `0` | Last iteration number |
| `created_at` | `string \| null` | `null` | ISO-8601 timestamp of last activity |
| `sections` | `string[]` | `[]` | Section keys that have draft content |
| `exec_summary_iterations` | `int` | `0` | Number of executive summary iterations completed |
| `req_breakdown_iterations` | `int` | `0` | Number of requirements breakdown iterations completed |

### PRDResumableListResponse

```json
{
  "count": 3,
  "runs": [ /* PRDResumableRun[] */ ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `count` | `int` | Number of resumable runs |
| `runs` | `PRDResumableRun[]` | List of resumable runs |

---

### PRDResumeResponse

`POST /flow/prd/resume` → 202

```json
{
  "run_id": "a1b2c3d4e5f6",
  "flow_name": "prd",
  "status": "running",
  "sections_approved": 3,
  "sections_total": 12,
  "next_section": "problem_statement",
  "next_step": 4,
  "message": "Resumed PRD flow — continuing from 'Problem Statement' (step 4/12)"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | The resumed run identifier |
| `flow_name` | `string` | `"prd"` | Always `"prd"` |
| `status` | `string` | — | Status after resuming — typically `"running"` |
| `sections_approved` | `int` | `0` | Number of sections already approved |
| `sections_total` | `int` | `0` | Total number of PRD sections (12) |
| `next_section` | `string \| null` | `null` | Key of the next section to iterate |
| `next_step` | `int \| null` | `null` | 1-based step number of the next section |
| `message` | `string` | — | Human-readable status message |

---

### JobDetail

`GET /flow/jobs/{job_id}`

Persistent job record from the `crewJobs` MongoDB collection.

```json
{
  "job_id": "a1b2c3d4e5f6",
  "flow_name": "prd",
  "idea": "Add dark mode to the dashboard",
  "status": "completed",
  "error": null,
  "queued_at": "2026-03-20T10:29:55Z",
  "started_at": "2026-03-20T10:30:00Z",
  "completed_at": "2026-03-20T11:45:00Z",
  "queue_time_ms": 5000,
  "queue_time_human": "0h 0m 5s",
  "running_time_ms": 4500000,
  "running_time_human": "1h 15m 0s",
  "updated_at": "2026-03-20T11:45:00Z",
  "output_file": "/output/a1b2c3d4e5f6/product requirement documents/prd.md",
  "confluence_url": "https://wiki.example.com/pages/12345"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `job_id` | `string` | — | Unique job identifier (same as `run_id`) |
| `flow_name` | `string` | — | Name of the flow (always `"prd"`) |
| `idea` | `string` | `""` | The feature idea / input text |
| `status` | `string` | — | Job lifecycle status: `"queued"`, `"running"`, `"awaiting_approval"`, `"paused"`, or `"completed"`. Errors always result in `"paused"` (not `"failed"`), allowing the run to be resumed |
| `error` | `string \| null` | `null` | Error message when the job was paused due to an LLM, billing, or internal error |
| `queued_at` | `string \| null` | `null` | ISO-8601 timestamp when the job was created |
| `started_at` | `string \| null` | `null` | ISO-8601 timestamp when execution began |
| `completed_at` | `string \| null` | `null` | ISO-8601 timestamp when the job reached a terminal state |
| `queue_time_ms` | `int \| null` | `null` | Time spent in queue (`started_at - queued_at`) in milliseconds |
| `queue_time_human` | `string \| null` | `null` | Queue duration in human-readable form (e.g. `"0h 1m 30s"`) |
| `running_time_ms` | `int \| null` | `null` | Time spent running (`completed_at - started_at`) in milliseconds |
| `running_time_human` | `string \| null` | `null` | Running duration in human-readable form (e.g. `"1h 23m 45s"`) |
| `updated_at` | `string \| null` | `null` | ISO-8601 timestamp of last update |
| `output_file` | `string \| null` | `null` | Path to the generated PRD markdown file — `null` until flow finalizes |
| `confluence_url` | `string \| null` | `null` | URL of the published Confluence page — `null` until published |

### JobListResponse

`GET /flow/jobs`

**Query params**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | `string \| null` | `null` | Filter by job status |
| `flow_name` | `string \| null` | `null` | Filter by flow name |
| `limit` | `int` | `50` | Max results (1–500) |

```json
{
  "count": 5,
  "jobs": [ /* JobDetail[] */ ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `count` | `int` | Number of jobs returned |
| `jobs` | `JobDetail[]` | List of job records |

---

### ErrorResponse

Standard error envelope returned by all PRD Flow API errors.

```json
{
  "error_code": "LLM_ERROR",
  "message": "LLM timeout after 4 attempts",
  "run_id": "a1b2c3d4e5f6",
  "detail": "Connection refused: api.openai.com"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error_code` | `string` | **Yes** | Machine-readable error code: `"LLM_ERROR"`, `"BILLING_ERROR"`, or `"INTERNAL_ERROR"` |
| `message` | `string` | **Yes** | Human-readable description of the error |
| `run_id` | `string \| null` | No | The `run_id` affected by this error — `null` if not applicable |
| `detail` | `string \| null` | No | Additional diagnostic detail (e.g. the original exception message) |

---

## Agent Providers

The PRD flow supports parallel drafting with multiple LLM providers:

| Provider ID | LLM | Description |
|-------------|-----|-------------|
| `"gemini"` | Google Gemini | Default provider — used for most sections |
| `"openai"` | OpenAI GPT | Alternative provider — can run in parallel with Gemini |

Configure the default provider via `DEFAULT_AGENT` env var.

---

## PRD Sections Reference

| Step | Key | Title | Specialist |
|------|-----|-------|-----------|
| 1 | `executive_summary` | Executive Summary | No |
| 2 | `executive_product_summary` | Executive Product Summary | **Yes** |
| 3 | `engineering_plan` | Engineering Plan | **Yes** |
| 4 | `problem_statement` | Problem Statement | No |
| 5 | `user_personas` | User Personas | No |
| 6 | `functional_requirements` | Functional Requirements | No |
| 7 | `no_functional_requirements` | Non-Functional Requirements | No |
| 8 | `edge_cases` | Edge Cases | No |
| 9 | `error_handling` | Error Handling | No |
| 10 | `success_metrics` | Success Metrics | No |
| 11 | `dependencies` | Dependencies | No |
| 12 | `assumptions` | Assumptions | No |

**Specialist sections** use a dedicated expert agent in addition to the general PRD writer.

---

See also: [[API Overview]], [[Ideas API]], [[Publishing API]], [[PRD Flow]]


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

- [x] **Agent Activity Log endpoint** — Implemented as `GET /flow/runs/{run_id}/activity`. Returns agent interaction events from `agentInteraction` collection. *(completed 2026-04-02)*
- [x] **UX Design Flow trigger endpoint** — Documented as `[CHANGE] POST /flow/ux-design/{run_id}` pending user feedback on design questions. *(completed 2026-04-02)*
