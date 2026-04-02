---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# GET /flow/jobs

> List persistent job records from MongoDB, optionally filtered.

**Method**: `GET`
**Path**: `/flow/jobs`
**Auth**: SSO Bearer token
**Tags**: Jobs

---

## Request

| Param | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `status` | `string \| null` | `null` | — | Filter by job status |
| `flow_name` | `string \| null` | `null` | — | Filter by flow name |
| `limit` | `int` | `50` | 1–500 | Max results |

---

## Response — 200

```json
{
  "count": 5,
  "jobs": [
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
  ]
}
```

See [[GET flow-jobs-{job_id}]] for `JobDetail` field descriptions.

---

## Database Algorithm

1. Build query from params: `{"status": status, "flow_name": flow_name}` (skip nulls)
2. Query `crewJobs` collection: `.find(query).sort("queued_at", -1).limit(limit)`
3. Map each doc → `JobDetail`

---

## Source

- **Router**: `apis/prd/router.py` → `list_all_jobs()`
- **Repository**: `mongodb/crew_jobs/` → `list_jobs()`
- **Collection**: `crewJobs`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
