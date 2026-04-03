---
tags:
  - api
  - endpoints
  - projects
---

# PATCH /projects/{project_id}

> Partial update — only include fields to change; omitted fields stay unchanged.

**Method**: `PATCH`
**Path**: `/projects/{project_id}`
**Auth**: SSO Bearer token
**Tags**: Projects

---

## Request

```json
{
  "description": "Updated project description",
  "confluence_space_key": "ENG",
  "jira_project_key": "ENG"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string \| null` | No | New display name (1–256 chars) |
| `description` | `string \| null` | No | New description |
| `confluence_space_key` | `string \| null` | No | New Confluence space key |
| `jira_project_key` | `string \| null` | No | New Jira project key |
| `confluence_parent_id` | `string \| null` | No | New Confluence parent page ID |

---

## Response — 200

Returns the updated `ProjectItem`.

## Error — 404

Project not found.

---

## Database Algorithm

1. Find project: `find_one({"project_id": project_id})`
2. Return 404 if not found
3. Build `$set` dict from non-null request fields + `updated_at = now()`
4. `update_one({"project_id": project_id}, {"$set": updates})`
5. Re-fetch and return as `ProjectItem`

---

## Source

- **Router**: `apis/projects/patch_project.py`
- **Models**: `apis/projects/models.py`
- **Repository**: `mongodb/project_config/repository.py` → `update_project()`
- **Collection**: `projectConfig`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
