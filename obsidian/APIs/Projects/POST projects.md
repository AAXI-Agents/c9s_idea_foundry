---
tags:
  - api
  - endpoints
  - projects
---

# POST /projects

> Create a new project.

**Method**: `POST`
**Path**: `/projects`
**Auth**: SSO Bearer token
**Tags**: Projects

---

## Request

```json
{
  "name": "Mobile Checkout Redesign",
  "description": "Redesign the mobile checkout flow to reduce cart abandonment",
  "confluence_space_key": "PROD",
  "jira_project_key": "MCR",
  "confluence_parent_id": "12345678",
  "reference_urls": ["https://example.com/spec"]
}
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | `string` | **Yes** | 1–256 chars | Display name |
| `description` | `string` | No | max 2,000 chars, default `""` | Description text |
| `confluence_space_key` | `string` | No | max 50 chars, default `""` | Confluence space key |
| `jira_project_key` | `string` | No | max 50 chars, default `""` | Jira project key |
| `confluence_parent_id` | `string` | No | max 50 chars, default `""` | Confluence parent page ID |
| `reference_urls` | `string[]` | No | max 20 items, default `[]` | Reference URLs |

---

## Response — 201

Returns the created `ProjectItem` (same schema as GET).

## Error — 422

Validation failed (e.g. name too long, missing required field).

---

## Database Algorithm

1. Generate `project_id` = `"proj-" + uuid4().hex[:8]`
2. Set `created_at` = `updated_at` = `datetime.now(UTC)`
3. Insert into `projectConfig` collection
4. Return the created document as `ProjectItem`

---

## Source

- **Router**: `apis/projects/post_project.py`
- **Models**: `apis/projects/models.py`
- **Repository**: `mongodb/project_config/repository.py` → `create_project()`
- **Collection**: `projectConfig`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
