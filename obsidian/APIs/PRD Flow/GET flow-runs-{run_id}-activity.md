---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# GET /flow/runs/{run_id}/activity

> Agent activity log — interaction events for a flow run.

**Method**: `GET`
**Path**: `/flow/runs/{run_id}/activity`
**Auth**: SSO Bearer token
**Tags**: Flow Runs

---

## Request

| Param | Type | Location | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| `run_id` | `string` | path | — | — | Flow run identifier |
| `limit` | `int` | query | `50` | 1–500 | Max events to return |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "count": 5,
  "events": [
    {
      "interaction_id": "abc123def456",
      "source": "api",
      "intent": "create_prd",
      "agent_response": "Starting PRD generation...",
      "run_id": "a1b2c3d4e5f6",
      "user_id": "usr_abc123",
      "created_at": "2026-03-20T10:30:00Z",
      "predicted_next_step": {
        "next_step": "approve_section",
        "message": "Review the executive summary",
        "confidence": 0.85
      }
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | The run this activity belongs to |
| `count` | `int` | Number of events returned |
| `events` | `ActivityEvent[]` | Events, newest first |

### ActivityEvent

| Field | Type | Description |
|-------|------|-------------|
| `interaction_id` | `string` | Unique interaction ID |
| `source` | `string` | Origin: `"slack"`, `"cli"`, `"api"` |
| `intent` | `string` | Classified intent |
| `agent_response` | `string` | Agent response text |
| `run_id` | `string \| null` | Associated flow run ID |
| `user_id` | `string \| null` | User who triggered |
| `created_at` | `string` | ISO-8601 timestamp |
| `predicted_next_step` | `dict \| null` | LLM-predicted next action |

---

## Database Algorithm

1. Query `agentInteraction` collection: `find({"run_id": run_id}).sort("created_at", -1).limit(limit)`
2. Map each doc → `ActivityEvent`
3. Return as `ActivityLogResponse`

---

## Source

- **Router**: `apis/prd/router.py` → `get_run_activity()`
- **Repository**: `mongodb/agent_interactions/repository.py` → `find_interactions(run_id=...)`
- **Collection**: `agentInteraction`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
