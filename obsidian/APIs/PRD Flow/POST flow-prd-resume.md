---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# POST /flow/prd/resume

> Resume a paused or unfinalized PRD flow from saved state.

**Method**: `POST`
**Path**: `/flow/prd/resume`
**Auth**: SSO Bearer token
**Tags**: Flow Runs
**Status**: 202 Accepted

---

## Request

```json
{
  "run_id": "a1b2c3d4e5f6",
  "auto_approve": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `run_id` | `string` | **Yes** | — | The unfinalized run to resume |
| `auto_approve` | `bool` | No | `false` | Resume without pausing for approval |

---

## Response — 202

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

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | The resumed run |
| `flow_name` | `string` | Always `"prd"` |
| `status` | `string` | Status after resuming (`"running"`) |
| `sections_approved` | `int` | Sections already approved |
| `sections_total` | `int` | Total sections (12) |
| `next_section` | `string \| null` | Next section to iterate |
| `next_step` | `int \| null` | 1-based step number |
| `message` | `string` | Human-readable status |

## Error — 404

Run not found in resumable (unfinalized) runs.

## Error — 409

Run is already active.

---

## Database Algorithm

1. Check `runs` dict — return 409 if already active
2. Query `workingIdeas` for unfinalized runs: `find_unfinalized()`
3. Match `run_id` — return 404 if not found
4. Create in-memory `FlowRun` in `runs` dict
5. Launch `resume_prd_flow(run_id, auto_approve)` as background task:
   - Calls `reactivate_job(run_id)` to update `crewJobs` status
   - Calls `restore_prd_state(run_id)` to rebuild `PRDDraft` + `ExecutiveSummaryDraft` from MongoDB
   - Resumes the iteration loop from the next unapproved section
6. Return 202

---

## Source

- **Router**: `apis/prd/_route_actions.py`
- **Service**: `apis/prd/service.py` → `resume_prd_flow()`
- **Models**: `apis/prd/_requests.py` → `PRDResumeRequest`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
