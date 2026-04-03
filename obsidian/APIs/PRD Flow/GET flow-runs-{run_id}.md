---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# GET /flow/runs/{run_id}

> Full flow state for polling — status, iteration, sections, draft content.

**Method**: `GET`
**Path**: `/flow/runs/{run_id}`
**Auth**: SSO Bearer token
**Tags**: Flow Runs

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | path | Unique flow run identifier |

---

## Response — 200

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
    "sections": [
      {
        "key": "executive_summary",
        "title": "Executive Summary",
        "step": 1,
        "content": "...",
        "critique": "...",
        "iteration": 3,
        "updated_date": "2026-03-20T10:35:00Z",
        "is_approved": false,
        "agent_results": {"openai": "..."},
        "selected_agent": ""
      }
    ],
    "all_approved": false
  }
}
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | `"running"`, `"awaiting_approval"`, `"paused"`, `"completed"` |
| `current_step` | `int` | 1-based step (1–12) |
| `sections_approved` | `int` | Approved section count |
| `current_draft` | `PRDDraftDetail` | Full per-section state |
| `error` | `string \| null` | Error message if paused due to error (prefixed: `BILLING_ERROR`, `LLM_ERROR`, `INTERNAL_ERROR`) |
| `finalized_idea` | `string` | Enriched idea after Phase 1 |
| `requirements_breakdown` | `string` | Structured requirements after breakdown phase |

---

### ExecutiveSummaryDraft

Nested in `executive_summary`.

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

Nested in `current_draft`.

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
| `error_code` | `string` | **Yes** | Machine-readable code: `"LLM_ERROR"`, `"BILLING_ERROR"`, or `"INTERNAL_ERROR"` |
| `message` | `string` | **Yes** | Human-readable description |
| `run_id` | `string \| null` | No | Affected `run_id` — `null` if not applicable |
| `detail` | `string \| null` | No | Additional diagnostic detail |

## Error — 404

Run not found in in-memory `runs` dict.

---

## Database Algorithm

No database access. Reads entirely from in-memory `runs` dict:
1. Look up `FlowRun` in `runs[run_id]`
2. Return 404 if not found
3. Compute `sections_approved`, `sections_total`, `current_step` from the draft
4. Serialize `current_draft` sections to `PRDDraftDetail`
5. Return the full state

---

## Source

- **Router**: `apis/prd/router.py`
- **Models**: `apis/prd/_responses.py` → `PRDRunStatusResponse`, `PRDDraftDetail`, `PRDSectionDetail`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
