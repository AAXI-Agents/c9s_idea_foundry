---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# POST /publishing/jira/all

> Batch-create Jira tickets for all pending PRDs.

**Method**: `POST`
**Path**: `/publishing/jira/all`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

No body.

---

## Response — 200

```json
{
  "completed": 3,
  "failed": 0,
  "results": [],
  "errors": [],
  "message": "Created Jira tickets for 3 PRDs"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `completed` | `int` | Successfully completed count |
| `failed` | `int` | Failed count |
| `results` | `JiraCreateResult[]` | Per-item results |
| `errors` | `dict[]` | Per-item errors |
| `message` | `string` | Summary |

---

## Database Algorithm

Same as single Jira creation, iterated over all pending PRDs.

---

## Source

- **Router**: `apis/publishing/router.py`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
