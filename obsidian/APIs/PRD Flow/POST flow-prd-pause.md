---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# POST /flow/prd/pause

> Pause a running flow and save progress to MongoDB.

**Method**: `POST`
**Path**: `/flow/prd/pause`
**Auth**: SSO Bearer token
**Tags**: Approvals

---

## Request

```json
{
  "run_id": "a1b2c3d4e5f6"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | **Yes** | The run to pause |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "action": "paused",
  "section": "executive_summary",
  "current_step": 1,
  "sections_approved": 3,
  "sections_total": 12,
  "is_final_section": false,
  "active_agents": ["openai"],
  "dropped_agents": [],
  "agent_errors": {},
  "message": "Pause requested for run a1b2c3d4e5f6..."
}
```

Same response schema as [[POST flow-prd-approve]] with `action: "paused"`.

## Error — 404

Run not found.

## Error — 409

Run cannot be paused (not in `running` or `awaiting_approval` state).

---

## Database Algorithm

No direct database writes at request time:
1. Validate run exists and is `running` or `awaiting_approval`
2. Set `pause_requested[run_id] = True` (in-memory flag)
3. If `awaiting_approval`, signal the event to unblock immediately
4. If `running`, flow will pause at the next approval checkpoint
5. The flow loop checks `pause_requested` and saves state to MongoDB when it pauses

---

## Source

- **Router**: `apis/prd/_route_actions.py`
- **Models**: `apis/prd/_requests.py` → `PRDPauseRequest`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
