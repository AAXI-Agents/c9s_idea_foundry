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
