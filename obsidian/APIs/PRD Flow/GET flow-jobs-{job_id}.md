---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# GET /flow/jobs/{job_id}

> Get a single persistent job record.

**Method**: `GET`
**Path**: `/flow/jobs/{job_id}`
**Auth**: SSO Bearer token
**Tags**: Jobs

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `job_id` | `string` | path | Unique job identifier (same as `run_id`) |

---

## Response — 200

```json
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
```

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `string` | Unique job identifier |
| `flow_name` | `string` | Always `"prd"` |
| `idea` | `string` | Feature idea text |
| `status` | `string` | `"queued"`, `"running"`, `"awaiting_approval"`, `"paused"`, `"completed"` |
| `error` | `string \| null` | Error message if paused due to error |
| `queued_at` | `string \| null` | ISO-8601 when job was created |
| `started_at` | `string \| null` | ISO-8601 when execution began |
| `completed_at` | `string \| null` | ISO-8601 when terminal state reached |
| `queue_time_ms` | `int \| null` | Time in queue (ms) |
| `queue_time_human` | `string \| null` | Human-readable queue time |
| `running_time_ms` | `int \| null` | Time running (ms) |
| `running_time_human` | `string \| null` | Human-readable run time |
| `updated_at` | `string \| null` | ISO-8601 last update |
| `output_file` | `string \| null` | Path to PRD markdown file |
| `confluence_url` | `string \| null` | Published Confluence page URL |

## Error — 404

Job not found.

---

## Database Algorithm

1. Query `crewJobs`: `find_one({"job_id": job_id})`
2. Return 404 if not found
3. Map doc → `JobDetail`

---

## Source

- **Router**: `apis/prd/router.py` → `get_job()`
- **Repository**: `mongodb/crew_jobs/` → `find_job()`
- **Collection**: `crewJobs`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
