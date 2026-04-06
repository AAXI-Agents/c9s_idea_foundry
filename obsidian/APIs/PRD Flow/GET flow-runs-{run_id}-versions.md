---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# GET /flow/runs/{run_id}/versions

> PRD version history — git-style snapshots with section content and changelogs.

**Method**: `GET`
**Path**: `/flow/runs/{run_id}/versions`
**Auth**: SSO Bearer token
**Tags**: Flow Runs

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
  "current_version": 2,
  "versions": [
    {
      "version": 1,
      "changelog": "Initial PRD completed",
      "sections": {
        "problem_statement": "Content of problem statement...",
        "user_personas": "Content of user personas..."
      },
      "created_at": "2026-04-05T10:00:00"
    },
    {
      "version": 2,
      "changelog": "Updated problem statement based on feedback",
      "sections": {
        "problem_statement": "Updated content...",
        "user_personas": "Content of user personas..."
      },
      "created_at": "2026-04-06T14:30:00"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | The run this version history belongs to |
| `current_version` | `int` | Latest version number (0 if no versions) |
| `versions` | `VersionEntry[]` | Version snapshots, oldest first |

### VersionEntry

| Field | Type | Description |
|-------|------|-------------|
| `version` | `int` | Version number (1, 2, 3, ...) |
| `changelog` | `string` | What changed in this version |
| `sections` | `object` | `{section_key: content}` snapshot |
| `created_at` | `string` | ISO-8601 creation timestamp |

---

## DB Algorithm

1. Verify run exists via `find_run_any_status(run_id)` → 404 if not found
2. Query `productRequirements` via `get_version_history(run_id)` → returns `version_history` array
3. Query `productRequirements` via `get_current_version(run_id)` → returns `current_version` int
4. Map each history entry to `VersionEntry` response model

---

## Errors

| Code | Description |
|------|-------------|
| 404 | Run not found |
| 500 | Internal server error |
| 503 | Service unavailable |

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
