---
tags:
  - api
  - endpoints
---

# Projects API

> [!warning] Deprecated — Use Per-Route Files
> This monolithic file is superseded by individual per-route files in [[Projects/]].
> Each endpoint now has its own file with detailed request, response, and database algorithm.
> **Edit the per-route files instead.** This file is kept for historical reference only.

---


> CRUD operations for project configuration — Confluence and Jira settings.

**Base path**: `/projects`
**Auth**: SSO Bearer token (all endpoints)
**Pagination**: `page` (1-based), `page_size` (10, 25, or 50)

---

## Endpoints

| Method | Path | Auth | Request | Response | Status | Purpose |
|--------|------|------|---------|----------|--------|---------|
| `GET` | `/projects` | SSO | query params | `ProjectListResponse` | 200 | List projects (paginated, newest first) |
| `GET` | `/projects/{project_id}` | SSO | — | `ProjectItem` | 200 | Get single project |
| `POST` | `/projects` | SSO | `ProjectCreate` | `ProjectItem` | 201 | Create new project |
| `PATCH` | `/projects/{project_id}` | SSO | `ProjectUpdate` | `ProjectItem` | 200 | Partial update |
| `DELETE` | `/projects/{project_id}` | SSO | — | — | 204 | Delete project |

---

## Request Schemas

### ProjectCreate

`POST /projects`

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
| `name` | `string` | **Yes** | 1–256 chars | Display name for the project |
| `description` | `string` | No | max 2,000 chars, default `""` | Project description text — shown on project cards and detail pages |
| `confluence_space_key` | `string` | No | max 50 chars, default `""` | Confluence space key for PRD publishing (e.g. `"PROD"`, `"ENG"`) |
| `jira_project_key` | `string` | No | max 50 chars, default `""` | Jira project key for ticket creation (e.g. `"MCR"`, `"FEAT"`) |
| `confluence_parent_id` | `string` | No | max 50 chars, default `""` | Confluence parent page ID — PRDs are published as child pages under this |
| `reference_urls` | `string[]` | No | max 20 items, default `[]` | Reference URLs for context (specs, design docs, competitor links) |

---

### ProjectUpdate

`PATCH /projects/{project_id}`

Partial update — only include fields you want to change. Omitted fields are left unchanged.

```json
{
  "description": "Updated project description",
  "confluence_space_key": "ENG",
  "jira_project_key": "ENG"
}
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | `string \| null` | No | 1–256 chars | New display name |
| `description` | `string \| null` | No | — | New project description |
| `confluence_space_key` | `string \| null` | No | — | New Confluence space key |
| `jira_project_key` | `string \| null` | No | — | New Jira project key |
| `confluence_parent_id` | `string \| null` | No | — | New Confluence parent page ID |

> **Note**: `reference_urls` is not included in `ProjectUpdate` — use full replacement via the create endpoint or direct MongoDB update if needed.

---

## Response Schemas

### ProjectItem

Returned by all GET, POST, and PATCH endpoints.

```json
{
  "project_id": "proj-abc123",
  "name": "Mobile Checkout Redesign",
  "description": "Redesign the mobile checkout flow to reduce cart abandonment",
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
| `project_id` | `string` | Unique project identifier (generated on create) |
| `name` | `string` | Project display name |
| `description` | `string` | Project description text — empty if not set |
| `confluence_space_key` | `string` | Confluence space key — empty if not configured |
| `jira_project_key` | `string` | Jira project key — empty if not configured |
| `confluence_parent_id` | `string` | Confluence parent page ID — empty if not configured |
| `reference_urls` | `string[]` | List of reference URLs attached to this project |
| `created_at` | `string` | ISO-8601 creation timestamp |
| `updated_at` | `string` | ISO-8601 last-modification timestamp |

---

### ProjectListResponse

`GET /projects`

**Query params**: `page` (int, default 1), `page_size` (int, default 10, allowed: 10/25/50)

```json
{
  "items": [ /* ProjectItem[] */ ],
  "total": 42,
  "page": 1,
  "page_size": 10,
  "total_pages": 5
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items` | `ProjectItem[]` | Array of project items for the current page |
| `total` | `int` | Total number of projects across all pages |
| `page` | `int` | Current page number (1-based) |
| `page_size` | `int` | Number of items per page |
| `total_pages` | `int` | Computed total pages (`ceil(total / page_size)`) |

---

## Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| 404 | `project_id` not found | `ErrorResponse` with `error_code: "INTERNAL_ERROR"` |
| 422 | Validation failed (e.g. name too long) | FastAPI validation error |
| 204 | Successful delete | No body |

---

See also: [[API Overview]], [[Ideas API]], [[MongoDB Schema]]


---

## Change Requests

<!-- 
HOW TO USE: Add your change requests below as bullet points.
Codex will implement each request, update this page, bump the
version, and move the completed item to the "Completed" list.

FORMAT:
- [ ] <your change request here>

EXAMPLE:
- [ ] Add a new field `priority` (string, optional) to the response
- [ ] Rename endpoint from /v1/old to /v2/new
-->

### Pending

_No pending change requests._

### Completed

- [x] **Integration Connection Status endpoint** — Implemented as `GET /integrations/status`. Returns Confluence and Jira configuration status from environment variables. *(completed 2026-04-02)*
- [x] **User Profile Update endpoint** — Documented as `[CHANGE] PATCH /user/profile` pending user feedback on design questions. *(completed 2026-04-02)*
