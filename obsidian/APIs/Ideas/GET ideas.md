---
tags:
  - api
  - endpoints
  - ideas
---

# GET /ideas

> List ideas with pagination, filtered by project or status.

**Method**: `GET`
**Path**: `/ideas`
**Auth**: SSO Bearer token
**Tags**: Ideas

---

## Request

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | `int` | `1` | Page number (1-based) |
| `page_size` | `int` | `10` | Items per page (1–100) |
| `project_id` | `string` | `null` | Filter by project |
| `status` | `string` | `null` | Explicit status filter (e.g. `"completed"`, `"inprogress"`, `"paused"`, `"failed"`, `"archived"`, `"deleted"`) |
| `include_archived` | `bool` | `false` | Include all statuses (removes default exclusion filter) |
| `organization_id` | `string` | `null` | Filter by organization (enterprise admins only) |

---

## Response — 200

```json
{
  "items": [
    {
      "run_id": "a1b2c3d4e5f6",
      "title": "Dark Mode Dashboard",
      "idea": "Add dark mode to the dashboard",
      "finalized_idea": "## Dark Mode Dashboard\n...",
      "status": "completed",
      "project_id": "proj-abc123",
      "created_at": "2026-03-20T10:30:00Z",
      "completed_at": "2026-03-20T11:45:00Z",
      "sections_done": 12,
      "total_sections": 12,
      "iteration": 36,
      "confluence_url": "https://wiki.example.com/pages/12345",
      "jira_phase": "completed",
      "ux_design_status": "completed"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 10,
  "total_pages": 2
}
```

See [[GET ideas-{run_id}]] for `IdeaItem` field descriptions.

---

## Database Algorithm

1. Build query filter from params:
   - If `project_id` provided: `{"project_id": project_id}`
   - If `status` provided explicitly: `{"status": status}` (overrides default)
   - Default (no `status`, `include_archived=false`): exclude terminal states
     `{"status": {"$nin": ["deleted", "archived", "failed", "completed"]}}`
   - `include_archived=true`: no status filter applied (returns all)
2. Apply tenant filter from SSO token / `organization_id`
3. Query `workingIdeas` collection: `.find(query, projection).sort("created_at", -1)`
4. Apply pagination: `.skip((page - 1) * page_size).limit(page_size)`
5. Count total: `count_documents(query)`
6. For each doc, compute `sections_done` from `section` sub-document

> **Note**: Completed ideas (PRD generated) are excluded by default.
> To fetch them, pass `?status=completed` explicitly.

---

## Source

- **Router**: `apis/ideas/get_ideas.py`
- **Models**: `apis/ideas/models.py`
- **Repository**: `mongodb/working_ideas/repository.py`
- **Collection**: `workingIdeas`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
