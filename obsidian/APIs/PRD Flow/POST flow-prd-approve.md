---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# POST /flow/prd/approve

> Approve the current section or submit feedback for refinement.

**Method**: `POST`
**Path**: `/flow/prd/approve`
**Auth**: SSO Bearer token
**Tags**: Approvals

---

## Request

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
| `run_id` | `string` | **Yes** | — | — | The run to approve |
| `approve` | `bool` | **Yes** | — | — | `true` to approve and advance; `false` to refine |
| `feedback` | `string \| null` | No | max 10,000 chars | `null` | User critique (replaces auto-critique when `approve: false`) |
| `selected_agent` | `string \| null` | No | `"openai"` or `"gemini"` | `null` | Which agent's draft to use (parallel drafting) |

---

## Response — 200

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

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | The run this action was applied to |
| `action` | `string` | `"approved"`, `"continuing refinement"`, or `"continuing refinement with user feedback"` |
| `section` | `string` | Section key the action applied to |
| `current_step` | `int \| null` | 1-based step number (1–12) |
| `sections_approved` | `int \| null` | Sections approved so far |
| `sections_total` | `int \| null` | Total sections (12) |
| `is_final_section` | `bool` | `true` when last section approved — flow will finalize |
| `active_agents` | `string[]` | Currently participating providers |
| `dropped_agents` | `string[]` | Removed providers |
| `agent_errors` | `dict` | Provider → error message |
| `message` | `string` | Human-readable result |

## Error — 404

Run not found.

## Error — 409

Run is not in `awaiting_approval` state.

---

## Database Algorithm

No direct database writes. Sets in-memory approval state:
1. Validate run exists in `runs` dict and is `awaiting_approval`
2. Set `approval_decisions[run_id] = approve`
3. If feedback provided: `approval_feedback[run_id] = feedback`
4. If selected_agent provided: `approval_selected[run_id] = selected_agent`
5. Signal the `approval_events[run_id]` threading.Event to unblock the flow

---

## Source

- **Router**: `apis/prd/_route_actions.py`
- **Models**: `apis/prd/_requests.py` → `PRDApproveRequest`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
