# Health API

> Liveness probes, version info, and Slack token management.

**Base path**: `/health` (health checks), `/version` (version info)
**Auth**: None for read-only probes; SSO for token management

---

## Endpoints

| Method | Path | Auth | Response | Purpose |
|--------|------|------|----------|---------|
| `GET` | `/health` | None | `HealthResponse` | Liveness probe |
| `GET` | `/version` | None | `VersionResponse` | Version + changelog |
| `GET` | `/health/slack-token` | None | `SlackTokenStatus` | Token rotation diagnostics |
| `POST` | `/health/slack-token/exchange` | SSO | `SlackTokenExchangeResult` | Exchange auth code for rotating tokens |
| `POST` | `/health/slack-token/refresh` | SSO | `SlackTokenRefreshResult` | Force-refresh Slack access token |

---

## Response Schemas

### HealthResponse

`GET /health`

```json
{
  "status": "ok",
  "version": "0.43.6"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | Always `"ok"` when server is running |
| `version` | `string` | Current application version (semver `X.Y.Z`) |

---

### VersionResponse

`GET /version`

```json
{
  "version": "0.43.6",
  "latest": {
    "version": "0.43.6",
    "date": "2026-03-26",
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
| `latest.version` | `string` | Version string of the latest entry |
| `latest.date` | `string` | ISO date of the latest entry |
| `latest.summary` | `string` | Human-readable summary of the change |
| `codex` | `CodexEntry[]` | Full version history (oldest → newest) |

---

### SlackTokenStatus

`GET /health/slack-token`

**Query params**: `team_id` (string, optional) — Slack workspace to check

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
| `token_type` | `string` | `"rotating"` or `"static"` — whether token rotation is active |
| `rotation_configured` | `bool` | `true` if rotation client secret is configured |
| `expires_in_seconds` | `int` | Seconds until current access token expires |
| `last_refresh` | `string` | ISO-8601 timestamp of the last token refresh |
| `store_path` | `string` | Filesystem path to the token store |

---

### SlackTokenExchangeResult

`POST /health/slack-token/exchange`

**Query params**: `team_id` (string, optional) — Slack workspace to exchange for

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
| `token_type` | `string` | `"rotating"` — exchange always produces rotating tokens |
| `rotation_configured` | `bool` | Whether rotation is configured |
| `expires_in` | `int` | Token lifespan in seconds |
| `message` | `string` | Human-readable result message |
| `scope` | `string` | Comma-separated OAuth scopes granted |

**Error**: 400 if exchange fails (missing code or invalid state)

---

### SlackTokenRefreshResult

`POST /health/slack-token/refresh`

**Query params**: `team_id` (string, optional) — Slack workspace to refresh

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
| `message` | `string` | Human-readable result message |
| `token_type` | `string` | `"rotating"` — refresh maintains rotating mode |
| `rotation_configured` | `bool` | Whether rotation is configured |
| `expires_in_seconds` | `int` | New token lifespan in seconds |

**Error**: 400 if no refresh token is available

---

See also: [[API Overview]], [[Server Lifecycle]], [[Environment Variables]]


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

_No completed change requests._
