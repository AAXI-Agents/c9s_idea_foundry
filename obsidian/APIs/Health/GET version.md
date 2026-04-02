---
tags:
  - api
  - endpoints
  - health
---

# GET /version

> Returns current version and full changelog history.

**Method**: `GET`
**Path**: `/version`
**Auth**: None
**Tags**: Health

---

## Request

No parameters.

---

## Response — 200

```json
{
  "version": "0.49.0",
  "latest": {
    "version": "0.49.0",
    "date": "2026-04-01",
    "summary": "API & Obsidian docs for web app integration."
  },
  "codex": [
    {
      "version": "0.1.0",
      "date": "2026-02-14",
      "summary": "Initial release."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `version` | `string` | Current application version |
| `latest` | `CodexEntry` | Most recent changelog entry |
| `latest.version` | `string` | Version string |
| `latest.date` | `string` | ISO date |
| `latest.summary` | `string` | Human-readable summary |
| `codex` | `CodexEntry[]` | Full version history (oldest → newest) |

---

## Database Algorithm

No database access. Reads from the in-memory `_CODEX` list in `version.py`.

---

## Source

- **Router**: `apis/health/router.py`
- **Model**: `version.py` → `get_version()`, `get_codex()`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
