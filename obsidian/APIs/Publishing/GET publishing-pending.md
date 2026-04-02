---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# GET /publishing/pending

> List PRDs pending delivery (Confluence publishing or Jira ticketing).

**Method**: `GET`
**Path**: `/publishing/pending`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

No parameters.

---

## Response — 200

```json
{
  "count": 3,
  "items": [
    {
      "run_id": "a1b2c3d4e5f6",
      "title": "Dark Mode Dashboard Feature",
      "source": "mongodb",
      "output_file": "/output/a1b2c3d4e5f6/product requirement documents/prd.md",
      "confluence_published": false,
      "confluence_url": "",
      "jira_completed": false,
      "jira_tickets": [],
      "status": "new"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `count` | `int` | Total pending items |
| `items[].run_id` | `string` | Flow run identifier |
| `items[].title` | `string` | PRD page title |
| `items[].source` | `string` | `"mongodb"` or `"disk"` |
| `items[].output_file` | `string` | Path to PRD markdown file |
| `items[].confluence_published` | `bool` | Whether Confluence page exists |
| `items[].confluence_url` | `string` | Confluence URL (empty if unpublished) |
| `items[].jira_completed` | `bool` | Whether Jira tickets created |
| `items[].jira_tickets` | `dict[]` | Created Jira tickets |
| `items[].status` | `string` | `"new"`, `"inprogress"`, `"completed"` |

---

## Database Algorithm

1. Query `productRequirements` for completed PRDs: `find({"status": "completed"})`
2. Scan `output/` directory for PRD files on disk
3. Merge results, deduplicating by `run_id`
4. Filter out already-fully-delivered items
5. Return pending items

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
