---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# POST /publishing/jira/{run_id}

> Create Jira tickets (Epics, Stories, Sub-tasks) from a single PRD.

**Method**: `POST`
**Path**: `/publishing/jira/{run_id}`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | path | PRD run to create tickets for |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "jira_completed": true,
  "ticket_keys": ["MCR-101", "MCR-102", "MCR-103"],
  "progress": ["Created Epic MCR-101", "Created Story MCR-102"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | Run identifier |
| `jira_completed` | `bool` | Success status |
| `ticket_keys` | `string[]` | Created Jira issue keys |
| `progress` | `string[]` | Step-by-step progress messages |

## Error — 404 / 503

Run not found, or Jira credentials not configured.

---

## Database Algorithm

1. Lookup PRD requirements from `productRequirements`
2. Extract engineering plan + functional requirements
3. Create Jira Epic → Stories → Sub-tasks via Jira REST API
4. Store ticket references in `productRequirements`
5. Return ticket keys

---

## Source

- **Router**: `apis/publishing/router.py`
- **Tools**: `tools/jira_tools.py`
- **Collection**: `productRequirements`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
