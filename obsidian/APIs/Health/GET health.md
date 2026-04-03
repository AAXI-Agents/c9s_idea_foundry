---
tags:
  - api
  - endpoints
  - health
---

# GET /health

> Liveness probe — returns server status and version.

**Method**: `GET`
**Path**: `/health`
**Auth**: None
**Tags**: Health

---

## Request

No parameters.

---

## Response — 200

```json
{
  "status": "ok",
  "version": "0.49.0"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | Always `"ok"` when server is running |
| `version` | `string` | Current application version (semver `X.Y.Z`) |

---

## Database Algorithm

No database access. Returns hardcoded status and the version from `version.py`.

---

## Source

- **Router**: `apis/health/get_health.py`
- **Model**: Inline dict response

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
