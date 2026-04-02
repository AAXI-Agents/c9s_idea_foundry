---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# POST /publishing/confluence/all

> Batch-publish all pending PRDs to Confluence.

**Method**: `POST`
**Path**: `/publishing/confluence/all`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

No body.

---

## Response — 200

```json
{
  "published": 3,
  "failed": 1,
  "results": [],
  "errors": [{ "run_id": "...", "error": "..." }],
  "message": "Published 3 of 4 PRDs to Confluence"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `published` | `int` | Successfully published count |
| `failed` | `int` | Failed count |
| `results` | `ConfluencePublishResult[]` | Per-item success results |
| `errors` | `dict[]` | Per-item error details |
| `message` | `string` | Summary |

---

## Database Algorithm

Same as single publish, iterated over all pending PRDs.

---

## Source

- **Router**: `apis/publishing/router.py`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
