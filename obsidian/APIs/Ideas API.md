# Ideas API

> Read and manage product feature ideas and their lifecycle status.

**Base path**: `/ideas`
**Auth**: SSO Bearer token (all endpoints)
**Pagination**: `page` (1-based), `page_size` (10, 25, or 50)

---

## Endpoints

| Method | Path | Auth | Request | Response | Status | Purpose |
|--------|------|------|---------|----------|--------|---------|
| `GET` | `/ideas` | SSO | query params | `IdeaListResponse` | 200 | List ideas (paginated, filtered) |
| `GET` | `/ideas/{run_id}` | SSO | — | `IdeaItem` | 200 | Get single idea with progress |
| `PATCH` | `/ideas/{run_id}/status` | SSO | `IdeaStatusUpdate` | `IdeaItem` | 200 | Archive or pause an idea |

---

## Query Parameters

### GET /ideas

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | `int` | `1` | Page number (1-based) |
| `page_size` | `int` | `10` | Items per page (allowed: 10, 25, 50) |
| `project_id` | `string` | `""` | Filter by project — only return ideas linked to this project |
| `status` | `string` | `""` | Filter by status — e.g. `"completed"`, `"inprogress"` |

---

## Request Schemas

### IdeaStatusUpdate

`PATCH /ideas/{run_id}/status`

```json
{
  "status": "archived"
}
```

| Field | Type | Required | Allowed Values | Description |
|-------|------|----------|----------------|-------------|
| `status` | `string` | **Yes** | `"archived"`, `"paused"` | New status. Only archive and pause transitions are supported via this endpoint |

> **Note**: Other status transitions (`inprogress`, `completed`, `failed`) are managed internally by the PRD Flow engine and cannot be set manually.

---

## Response Schemas

### IdeaItem

Returned by all GET and PATCH endpoints.

```json
{
  "run_id": "a1b2c3d4e5f6",
  "idea": "Add dark mode to the dashboard",
  "finalized_idea": "## Dark Mode Dashboard\n\nA comprehensive dark mode...",
  "status": "completed",
  "project_id": "proj-abc123",
  "created_at": "2026-03-20T10:30:00Z",
  "completed_at": "2026-03-20T11:45:00Z",
  "sections_done": 12,
  "total_sections": 12,
  "iteration": 36,
  "confluence_url": "https://wiki.example.com/pages/12345",
  "jira_phase": "completed",
  "figma_design_url": "https://figma.com/file/abc123",
  "figma_design_status": "completed"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | Unique identifier for this flow run (used across all APIs) |
| `idea` | `string` | `""` | Original idea text submitted by the user |
| `finalized_idea` | `string` | `""` | Enriched idea after Idea Refinement agent processing — includes structured markdown with problem statement, scope, and constraints. Empty until refinement completes |
| `status` | `string` | `""` | Current lifecycle status (see Status Lifecycle below) |
| `project_id` | `string` | `""` | Associated project ID — empty if idea was created without a project |
| `created_at` | `string` | `""` | ISO-8601 timestamp when the idea was submitted |
| `completed_at` | `string` | `""` | ISO-8601 timestamp when PRD generation finished — empty until completed |
| `sections_done` | `int` | `0` | Number of PRD sections completed (0–12). Use with `total_sections` for progress bars |
| `total_sections` | `int` | `0` | Total sections in the PRD (always 12 when flow is active) |
| `iteration` | `int` | `0` | Total iteration count across all sections — higher means more refinement cycles |
| `confluence_url` | `string` | `""` | URL of the published Confluence page — empty until published |
| `jira_phase` | `string` | `""` | Jira ticket creation status — empty, `"in_progress"`, or `"completed"` |
| `figma_design_url` | `string` | `""` | URL to Figma design file — empty if no design was generated |
| `figma_design_status` | `string` | `""` | Figma design status — empty, `"in_progress"`, or `"completed"` |

---

### IdeaListResponse

`GET /ideas`

```json
{
  "items": [ /* IdeaItem[] */ ],
  "total": 15,
  "page": 1,
  "page_size": 10,
  "total_pages": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items` | `IdeaItem[]` | Array of idea items for the current page |
| `total` | `int` | Total number of ideas matching the filter |
| `page` | `int` | Current page number (1-based) |
| `page_size` | `int` | Number of items per page |
| `total_pages` | `int` | Computed total pages (`ceil(total / page_size)`) |

---

## Status Lifecycle

| Status | Meaning | Can transition to |
|--------|---------|-------------------|
| `inprogress` | PRD flow is actively running | `completed`, `paused`, `failed`, `archived` |
| `completed` | PRD generation finished successfully | `archived` |
| `paused` | Flow paused (user-initiated or error) — can be resumed | `inprogress` (via resume), `archived` |
| `failed` | Flow failed — can be resumed after fixing the issue | `inprogress` (via resume), `archived` |
| `archived` | Soft-deleted — hidden from default views | (terminal) |

```
inprogress → completed → archived
inprogress → paused → inprogress (resume)
inprogress → failed → inprogress (resume)
any status → archived
```

---

## PRD Sections

The 12 PRD sections tracked by `sections_done`:

| Step | Key | Title |
|------|-----|-------|
| 1 | `executive_summary` | Executive Summary |
| 2 | `executive_product_summary` | Executive Product Summary |
| 3 | `engineering_plan` | Engineering Plan |
| 4 | `problem_statement` | Problem Statement |
| 5 | `user_personas` | User Personas |
| 6 | `functional_requirements` | Functional Requirements |
| 7 | `no_functional_requirements` | Non-Functional Requirements |
| 8 | `edge_cases` | Edge Cases |
| 9 | `error_handling` | Error Handling |
| 10 | `success_metrics` | Success Metrics |
| 11 | `dependencies` | Dependencies |
| 12 | `assumptions` | Assumptions |

---

## Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| 404 | `run_id` not found | `ErrorResponse` |
| 422 | Invalid status value (not `"archived"` or `"paused"`) | FastAPI validation error |

---

See also: [[API Overview]], [[Projects API]], [[PRD Flow API]]
