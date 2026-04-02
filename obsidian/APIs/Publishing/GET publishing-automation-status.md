---
tags:
  - api
  - endpoints
  - publishing
  - confluence
  - jira
---

# GET /publishing/automation/status

> Check file watcher and cron scheduler status.

**Method**: `GET`
**Path**: `/publishing/automation/status`
**Auth**: SSO Bearer token
**Tags**: Publishing

---

## Request

No parameters.

---

## Response — 200

```json
{
  "watcher_running": true,
  "watcher_directory": "/output",
  "scheduler_running": true,
  "scheduler_interval_seconds": 300
}
```

| Field | Type | Description |
|-------|------|-------------|
| `watcher_running` | `bool` | Whether filesystem watcher is active |
| `watcher_directory` | `string` | Directory being watched |
| `scheduler_running` | `bool` | Whether cron scheduler is active |
| `scheduler_interval_seconds` | `int` | Scan interval (e.g. 300 = 5 min) |

---

## Database Algorithm

No database access. Reads from in-memory watcher/scheduler state.

---

## Source

- **Router**: `apis/publishing/router.py`
- **Watcher**: `apis/publishing/watcher.py`
- **Scheduler**: `apis/publishing/scheduler.py`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
