---
tags:
  - api
  - endpoints
  - projects
---

# GET /projects

> List projects with pagination, newest first.

**Method**: `GET`
**Path**: `/projects`
**Auth**: SSO Bearer token
**Tags**: Projects

---

## Request

| Param | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `page` | `int` | `1` | ≥ 1 | Page number (1-based) |
| `page_size` | `int` | `10` | 10, 25, or 50 | Items per page |

---

## Response — 200

```json
{
  "items": [
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
  ],
  "total": 42,
  "page": 1,
  "page_size": 10,
  "total_pages": 5
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items` | `ProjectItem[]` | Projects for the current page |
| `total` | `int` | Total number of projects |
| `page` | `int` | Current page (1-based) |
| `page_size` | `int` | Items per page |
| `total_pages` | `int` | `ceil(total / page_size)` |

---

## Database Algorithm

1. Query `projectConfig` collection: `find({}).sort("created_at", -1)`
2. Apply skip/limit pagination: `.skip((page - 1) * page_size).limit(page_size)`
3. Count total: `count_documents({})`
4. Compute `total_pages = ceil(total / page_size)`
5. Map each doc → `ProjectItem` fields

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
