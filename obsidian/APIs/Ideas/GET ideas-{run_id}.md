---
tags:
  - api
  - endpoints
  - ideas
---

# GET /ideas/{run_id}

> Get a single idea with full progress details.

**Method**: `GET`
**Path**: `/ideas/{run_id}`
**Auth**: SSO Bearer token
**Tags**: Ideas

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | path | Unique flow run identifier |

---

## Response — 200

```json
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
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | Unique flow run identifier |
| `title` | `string` | `""` | Short display title. Set via `PRDKickoffRequest.title` |
| `idea` | `string` | `""` | Original idea text |
| `finalized_idea` | `string` | `""` | Enriched idea after Idea Refinement agent |
| `status` | `string` | `""` | Lifecycle status (see Status Lifecycle) |
| `project_id` | `string` | `""` | Associated project ID |
| `created_at` | `string` | `""` | ISO-8601 creation timestamp |
| `completed_at` | `string` | `""` | ISO-8601 completion timestamp |
| `sections_done` | `int` | `0` | Completed PRD sections (0–12) |
| `total_sections` | `int` | `0` | Total sections (12) |
| `iteration` | `int` | `0` | Total iteration count |
| `confluence_url` | `string` | `""` | Published Confluence page URL |
| `jira_phase` | `string` | `""` | Jira status: `""`, `"in_progress"`, `"completed"` |
| `ux_design_status` | `string` | `""` | UX design: `""`, `"generating"`, `"completed"` |

## Error — 404

Run not found.

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

## Database Algorithm

1. Query `workingIdeas`: `find_one({"run_id": run_id, "status": {"$ne": "archived"}})`
2. Return 404 if not found
3. Compute `sections_done` from `sections` array length
4. Lookup `confluence_url` from `productRequirements` if status is `"completed"`
5. Map doc → `IdeaItem`

---

## Source

- **Router**: `apis/ideas/get_idea.py`
- **Models**: `apis/ideas/models.py`
- **Repository**: `mongodb/working_ideas/repository.py`
- **Collection**: `workingIdeas`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
