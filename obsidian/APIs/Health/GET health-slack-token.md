---
tags:
  - api
  - endpoints
  - health
---

# GET /health/slack-token

> Slack token rotation diagnostics — check token type, expiry, and store path.

**Method**: `GET`
**Path**: `/health/slack-token`
**Auth**: None
**Tags**: Health

---

## Request

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `team_id` | `string` | `null` | Slack workspace to check (query param) |

---

## Response — 200

```json
{
  "token_type": "rotating",
  "rotation_configured": true,
  "expires_in_seconds": 39600,
  "last_refresh": "2026-02-25T10:00:00Z",
  "store_path": ".slack_tokens.json"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `token_type` | `string` | `"rotating"` or `"static"` |
| `rotation_configured` | `bool` | Whether rotation client secret is configured |
| `expires_in_seconds` | `int` | Seconds until current access token expires |
| `last_refresh` | `string` | ISO-8601 timestamp of last token refresh |
| `store_path` | `string` | Filesystem path to the token store |

---

## Database Algorithm

No database access. Reads from `SlackTokenManager` in-memory state and `.slack_tokens.json` file store.

---

## Source

- **Router**: `apis/health/router.py`
- **Token Manager**: `tools/slack_token_manager.py`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
