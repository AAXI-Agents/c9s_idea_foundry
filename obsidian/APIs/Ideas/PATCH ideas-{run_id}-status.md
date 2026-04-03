---
tags:
  - api
  - endpoints
  - ideas
---

# PATCH /ideas/{run_id}/status

> Archive or pause an idea.

**Method**: `PATCH`
**Path**: `/ideas/{run_id}/status`
**Auth**: SSO Bearer token
**Tags**: Ideas

---

## Request

```json
{
  "status": "archived"
}
```

| Field | Type | Required | Allowed Values | Description |
|-------|------|----------|----------------|-------------|
| `status` | `string` | **Yes** | `"archived"`, `"paused"` | New status |

> Other status transitions (`inprogress`, `completed`, `failed`) are managed internally by the PRD Flow engine.

---

## Response — 200

Returns the updated `IdeaItem` (same schema as GET /ideas/{run_id}).

## Error — 404

Run not found.

## Error — 422

Invalid status value.

---

## Database Algorithm

1. Find idea: `find_one({"run_id": run_id})`
2. Return 404 if not found
3. Validate status is `"archived"` or `"paused"`
4. `update_one({"run_id": run_id}, {"$set": {"status": status}})`
5. Re-fetch and return as `IdeaItem`

---

## Source

- **Router**: `apis/ideas/patch_idea_status.py`
- **Models**: `apis/ideas/models.py`
- **Repository**: `mongodb/working_ideas/repository.py`
- **Collection**: `workingIdeas`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
