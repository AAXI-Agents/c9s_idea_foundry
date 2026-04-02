---
tags:
  - api
  - endpoints
  - projects
---

# DELETE /projects/{project_id}

> Delete a project by ID.

**Method**: `DELETE`
**Path**: `/projects/{project_id}`
**Auth**: SSO Bearer token
**Tags**: Projects

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `project_id` | `string` | path | Project to delete |

---

## Response — 204

No body. Successful deletion.

## Error — 404

Project not found.

---

## Database Algorithm

1. `delete_one({"project_id": project_id})` on `projectConfig` collection
2. Return 404 if `deleted_count == 0`
3. Return 204 (no body)

---

## Source

- **Router**: `apis/projects/router.py`
- **Repository**: `mongodb/project_config/repository.py` → `delete_project()`
- **Collection**: `projectConfig`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
