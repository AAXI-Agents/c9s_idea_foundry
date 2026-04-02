---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# POST /publishing/confluence/{run_id}

> Publish a single PRD to Confluence.

**Method**: `POST`
**Path**: `/publishing/confluence/{run_id}`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | path | PRD run to publish |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "title": "Dark Mode Dashboard Feature",
  "url": "https://wiki.example.com/pages/12345",
  "page_id": "12345",
  "action": "created"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | Run identifier |
| `title` | `string` | Confluence page title |
| `url` | `string` | Full URL |
| `page_id` | `string` | Confluence page ID |
| `action` | `string` | `"created"` or `"updated"` |

## Error — 404 / 503

Run not found, or Confluence credentials not configured.

---

## Database Algorithm

1. Lookup PRD content from `productRequirements` or `output/` file
2. Convert markdown → Confluence XHTML via `confluence_xhtml` module
3. Call Confluence REST API to create or update page
4. Store `confluence_url` + `confluence_page_id` in `productRequirements`
5. Return publish result

---

## Source

- **Router**: `apis/publishing/router.py`
- **Tools**: `tools/confluence_tool.py`
- **Collection**: `productRequirements`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
