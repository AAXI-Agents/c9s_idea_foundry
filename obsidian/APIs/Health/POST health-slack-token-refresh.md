---
tags:
  - api
  - endpoints
  - health
---

# POST /health/slack-token/refresh

> Force-refresh the Slack access token using the stored refresh token.

**Method**: `POST`
**Path**: `/health/slack-token/refresh`
**Auth**: SSO Bearer token
**Tags**: Health

---

## Request

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `team_id` | `string` | `null` | Slack workspace to refresh (query param) |

---

## Response — 200

```json
{
  "message": "Token refreshed successfully",
  "token_type": "rotating",
  "rotation_configured": true,
  "expires_in_seconds": 43200
}
```

| Field | Type | Description |
|-------|------|-------------|
| `message` | `string` | Human-readable result |
| `token_type` | `string` | Always `"rotating"` |
| `rotation_configured` | `bool` | Whether rotation is configured |
| `expires_in_seconds` | `int` | New token lifespan in seconds |

## Error — 400

No refresh token available.

---

## Database Algorithm

1. Reads refresh token from `.slack_tokens.json`
2. Calls Slack API `oauth.v2.access` with the refresh token
3. Stores new access + refresh tokens to `.slack_tokens.json`
4. Updates `slackOAuth` MongoDB collection

---

## Source

- **Router**: `apis/health/post_slack_token_refresh.py`
- **Token Manager**: `tools/slack_token_manager.py`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
