---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# POST /flow/prd/kickoff

> Start the PRD generation flow asynchronously.

**Method**: `POST`
**Path**: `/flow/prd/kickoff`
**Auth**: SSO Bearer token
**Tags**: Flow Runs
**Status**: 202 Accepted

---

## Request

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
| `idea` | `string` | **Yes** | 1–50,000 chars | — | The product feature idea |
| `title` | `string` | No | max 256 chars | `""` | Short display title; fallback: first line of idea |
| `project_id` | `string` | No | max 50 chars | `""` | Link to existing project for Confluence/Jira config |
| `auto_approve` | `bool` | No | — | `false` | Skip manual approval — auto-iterate and approve sections |

---

## Response — 202

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
| `run_id` | `string` | Unique run identifier — use in all subsequent API calls |
| `flow_name` | `string` | Always `"prd"` |
| `status` | `string` | Initial status (`"running"`) |
| `message` | `string` | Human-readable confirmation |

## Error — 409

A job is already active. Only one job can run at a time.

## Error — 422

Validation error (e.g. idea too long or empty).

---

## Database Algorithm

1. Check `crewJobs` for active job: `find_active_job()` — return 409 if found
2. Generate `run_id = uuid4().hex[:12]`
3. Create in-memory `FlowRun` in `runs` dict
4. Insert job record: `crewJobs.insert_one({job_id, flow_name: "prd", idea, status: "queued", queued_at: now()})`
5. If `project_id` provided: `workingIdeas.update_one({run_id}, {$set: {project_id, idea}}, upsert=True)` via `save_project_ref()`
6. If `title` provided: `workingIdeas.update_one({run_id}, {$set: {title}}, upsert=True)`
7. Launch `run_prd_flow(run_id, idea, auto_approve)` as background task
8. Return 202 with `run_id`

---

## Flow Phases

1. **Idea Refinement** — Gemini agent enriches the raw idea (3-10 cycles)
2. **Requirements Breakdown** — Structured requirements decomposition
3. **Phase 1: Executive Summary** — Iterative drafting (≥ `PRD_EXEC_RESUME_THRESHOLD` cycles)
4. **Phase 2: Sections** — 9 remaining sections auto-iterate between `PRD_SECTION_MIN_ITERATIONS` and `PRD_SECTION_MAX_ITERATIONS`

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

## Source

- **Router**: `apis/prd/_route_actions.py`
- **Service**: `apis/prd/service.py` → `run_prd_flow()`
- **Models**: `apis/prd/_requests.py` → `PRDKickoffRequest`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
