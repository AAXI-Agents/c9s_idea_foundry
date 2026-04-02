---
tags:
  - api
  - endpoints
  - health
---

# POST /health/slack-token/exchange

> Exchange a Slack OAuth authorization code for rotating tokens.

**Method**: `POST`
**Path**: `/health/slack-token/exchange`
**Auth**: SSO Bearer token
**Tags**: Health

---

## Request

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `team_id` | `string` | `null` | Slack workspace to exchange for (query param) |

Body: authorization code provided by Slack OAuth redirect.

---

## Response — 200

```json
{
  "token_type": "rotating",
  "rotation_configured": true,
  "expires_in": 43200,
  "message": "Token exchanged successfully",
  "scope": "chat:write,channels:read"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `token_type` | `string` | Always `"rotating"` |
| `rotation_configured` | `bool` | Whether rotation is configured |
| `expires_in` | `int` | Token lifespan in seconds |
| `message` | `string` | Human-readable result |
| `scope` | `string` | Comma-separated OAuth scopes granted |

## Error — 400

Exchange failed (missing code or invalid state).

---

## Database Algorithm

1. Exchanges the auth code with Slack API (`oauth.v2.access`)
2. Stores the new bot + user tokens in `.slack_tokens.json`
3. Updates the `slackOAuth` MongoDB collection with workspace info

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
