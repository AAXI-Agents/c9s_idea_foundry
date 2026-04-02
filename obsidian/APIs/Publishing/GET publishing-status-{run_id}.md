---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# GET /publishing/status/{run_id}

> Check delivery status for a run (Confluence + Jira).

**Method**: `GET`
**Path**: `/publishing/status/{run_id}`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | path | Flow run to check |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "confluence_published": true,
  "confluence_url": "https://wiki.example.com/pages/12345",
  "confluence_page_id": "12345",
  "jira_completed": true,
  "jira_tickets": [
    { "key": "MCR-101", "summary": "Epic: Dark Mode", "type": "Epic" }
  ],
  "status": "completed",
  "error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | Run identifier |
| `confluence_published` | `bool` | Whether Confluence page exists |
| `confluence_url` | `string` | Confluence page URL |
| `confluence_page_id` | `string` | Confluence page ID |
| `jira_completed` | `bool` | Whether Jira tickets created |
| `jira_tickets` | `dict[]` | Array of created Jira tickets |
| `status` | `string` | `"new"`, `"inprogress"`, `"completed"` |
| `error` | `string \| null` | Last error message |

## Error — 404

Run not found.

---

## Database Algorithm

1. Query `productRequirements`: `find_one({"run_id": run_id})`
2. Read `confluence_url`, `confluence_page_id`, `jira_tickets` fields
3. Compute `status` from field presence
4. Return delivery status

---

## Source

- **Router**: `apis/publishing/router.py`
- **Collection**: `productRequirements`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
