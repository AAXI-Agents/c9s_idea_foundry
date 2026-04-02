---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# GET /flow/prd/resumable

> List unfinalized runs that can be resumed from MongoDB.

**Method**: `GET`
**Path**: `/flow/prd/resumable`
**Auth**: SSO Bearer token
**Tags**: Flow Runs

---

## Request

No parameters.

---

## Response — 200

```json
{
  "count": 3,
  "runs": [
    {
      "run_id": "a1b2c3d4e5f6",
      "idea": "Add dark mode to the dashboard",
      "iteration": 12,
      "created_at": "2026-03-20T10:30:00Z",
      "sections": ["executive_summary", "executive_product_summary"],
      "exec_summary_iterations": 5,
      "req_breakdown_iterations": 2
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `count` | `int` | Number of resumable runs |
| `runs[].run_id` | `string` | Unique run identifier |
| `runs[].idea` | `string` | Feature idea text |
| `runs[].iteration` | `int` | Last iteration count |
| `runs[].created_at` | `string \| null` | Last activity timestamp |
| `runs[].sections` | `string[]` | Completed section keys |
| `runs[].exec_summary_iterations` | `int` | Executive summary iterations done |
| `runs[].req_breakdown_iterations` | `int` | Requirements breakdown iterations done |

---

## Database Algorithm

1. Query `workingIdeas` collection: `find({"status": {"$nin": ["completed", "archived", "failed"]}})`
2. Map each doc → `PRDResumableRun`

---

## Source

- **Router**: `apis/prd/router.py` → `list_resumable_runs()`
- **Repository**: `mongodb/working_ideas/repository.py` → `find_unfinalized()`
- **Collection**: `workingIdeas`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
