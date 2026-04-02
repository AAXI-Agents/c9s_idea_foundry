---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# POST /publishing/all

> Confluence + Jira for all pending PRDs.

**Method**: `POST`
**Path**: `/publishing/all`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

No body.

---

## Response — 200

```json
{
  "run_id": "",
  "confluence": { "published": 3, "failed": 0, "results": [], "errors": [] },
  "jira": { "completed": 3, "failed": 0, "results": [], "errors": [] }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | Empty for batch operations |
| `confluence` | `ConfluenceBatchResult` | Confluence results |
| `jira` | `JiraBatchResult` | Jira results |

---

## Database Algorithm

1. Call `publish_all_and_create_tickets()` in `publishing/service.py`
2. **Confluence batch**: `find_pending_confluence()` queries `workingIdeas` for completed PRDs without `confluence_url` set
3. For each pending PRD: `publish_to_confluence(run_id)` → calls Confluence REST API → stores `confluence_url` and `confluence_page_id` on delivery record
4. **Jira batch**: `find_pending_jira()` queries delivery records where `confluence_url` exists but `jira_completed` is `false`
5. For each: `create_jira_tickets(run_id)` → reads PRD from `productRequirements` → creates Epics, Stories, Sub-tasks via Jira REST API → marks `jira_completed: true`
6. Returns aggregated counts and per-run results/errors

---

## Source

- **Router**: `apis/publishing/router.py`
- **Service**: `apis/publishing/service.py` → `publish_all_and_create_tickets()`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
