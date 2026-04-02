---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# POST /publishing/all/{run_id}

> Confluence + Jira for a single PRD.

**Method**: `POST`
**Path**: `/publishing/all/{run_id}`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | path | PRD run to deliver |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "confluence": {
    "run_id": "a1b2c3d4e5f6",
    "title": "Dark Mode Dashboard Feature",
    "url": "https://wiki.example.com/pages/12345",
    "page_id": "12345",
    "action": "created"
  },
  "jira": {
    "run_id": "a1b2c3d4e5f6",
    "jira_completed": true,
    "ticket_keys": ["MCR-101"]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | Run identifier |
| `confluence` | `ConfluencePublishResult` | Confluence result |
| `jira` | `JiraCreateResult` | Jira result |

---

## Database Algorithm

1. Call `publish_and_create_tickets(run_id)` in `publishing/service.py`
2. **Confluence**: load PRD from `productRequirements` by `run_id` → if no `confluence_url`, publish via Confluence REST API → save URL and page_id to delivery record
3. **Jira**: if Confluence published but `jira_completed` is `false` → load PRD content → create Epics, Stories, Sub-tasks via Jira REST API → mark `jira_completed: true`
4. Returns combined result with Confluence URL and Jira ticket keys
5. Returns 404 if no deliverable content found for `run_id`

---

## Source

- **Router**: `apis/publishing/router.py`
- **Service**: `apis/publishing/service.py` → `publish_and_create_tickets()`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
