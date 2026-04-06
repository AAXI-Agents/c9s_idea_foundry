---
tags:
  - api
  - endpoints
  - publishing
---

# GET /publishing/confluence/{run_id}/preview

> Preview Confluence-formatted content without publishing.

**Method**: `GET`
**Path**: `/publishing/confluence/{run_id}/preview`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

| Param | Type | Location | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| `run_id` | `string` | path | — | — | Flow run identifier |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "title": "PRD: Build a Fitness Tracking App",
  "markdown": "# Executive Summary\n\nThis PRD outlines...",
  "xhtml": "<h1>Executive Summary</h1><p>This PRD outlines...</p>",
  "sections_changed": ["problem_statement", "functional_requirements"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | The run this preview belongs to |
| `title` | `string` | Generated Confluence page title |
| `markdown` | `string` | Assembled PRD in markdown format |
| `xhtml` | `string` | Confluence XHTML rendering |
| `sections_changed` | `string[]` | Section keys that differ from last version snapshot (all keys if no previous version) |

---

## DB Algorithm

1. Query `workingIdeas` via `find_run_any_status(run_id)` → 404 if not found
2. Assemble PRD markdown via `assemble_prd_from_doc(doc)` → 500 if empty
3. Convert to XHTML via `md_to_confluence_xhtml(content)`
4. Generate page title via `make_page_title(idea)`
5. Compare current section content against last version snapshot from `get_version_history(run_id)`
6. If previous versions exist: flag sections where latest iteration content differs from snapshot
7. If no previous versions: flag all sections as changed/new

---

## Errors

| Code | Description |
|------|-------------|
| 404 | No PRD found for run_id |
| 500 | Could not assemble PRD content / internal error |

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
