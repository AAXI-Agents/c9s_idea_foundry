---
tags:
  - api
  - endpoints
  - projects
---

# GET /projects/{project_id}

> Get a single project by ID.

**Method**: `GET`
**Path**: `/projects/{project_id}`
**Auth**: SSO Bearer token
**Tags**: Projects

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `project_id` | `string` | path | Unique project identifier |

---

## Response — 200

```json
{
  "project_id": "proj-abc123",
  "name": "Mobile Checkout Redesign",
  "description": "Redesign the mobile checkout flow",
  "confluence_space_key": "PROD",
  "jira_project_key": "MCR",
  "confluence_parent_id": "12345678",
  "reference_urls": ["https://example.com/spec"],
  "created_at": "2026-03-20T10:30:00Z",
  "updated_at": "2026-03-25T14:15:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | `string` | Unique project identifier |
| `name` | `string` | Display name |
| `description` | `string` | Project description (empty if not set) |
| `confluence_space_key` | `string` | Confluence space key (empty if not configured) |
| `jira_project_key` | `string` | Jira project key (empty if not configured) |
| `confluence_parent_id` | `string` | Confluence parent page ID (empty if not configured) |
| `reference_urls` | `string[]` | Reference URLs |
| `created_at` | `string` | ISO-8601 creation timestamp |
| `updated_at` | `string` | ISO-8601 last-modification timestamp |

## Error — 404

Project not found.

---

## Database Algorithm

1. Query `projectConfig` collection: `find_one({"project_id": project_id})`
2. Return 404 if not found
3. Map doc → `ProjectItem` fields

---

## Source

- **Router**: `apis/projects/router.py`
- **Repository**: `mongodb/project_config/repository.py`
- **Collection**: `projectConfig`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
