---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# GET /flow/runs

> List all in-memory flow runs.

**Method**: `GET`
**Path**: `/flow/runs`
**Auth**: SSO Bearer token
**Tags**: Flow Runs

---

## Request

No parameters.

---

## Response — 200

```json
{
  "count": 2,
  "runs": [
    {
      "run_id": "a1b2c3d4e5f6",
      "flow_name": "prd",
      "status": "running",
      "iteration": 5,
      "created_at": "2026-03-20T10:30:00Z",
      "current_section_key": "executive_summary"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `count` | `int` | Number of runs |
| `runs` | `RunSummary[]` | Summary of each run |

---

## Database Algorithm

No database access. Iterates over in-memory `runs` dict and returns summary fields.

---

## Source

- **Router**: `apis/prd/router.py` → `list_runs()`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
