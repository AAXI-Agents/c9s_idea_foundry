---
tags:
  - database
  - mongodb
---

# slackOAuth Schema

> Slack workspace OAuth token persistence — per-team bot tokens with rotation support.

**Collection**: `slackOAuth`
**Primary Key**: `team_id` (unique index)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[Slack/]] | `GET /slack/oauth/callback` | Stores tokens after OAuth code exchange |
| [[Health/]] | `GET /health/slack-token` | Reads token metadata for diagnostics (no secrets) |
| [[Health/]] | `POST /health/slack-token/exchange` | Updates tokens after manual exchange |
| [[Health/]] | `POST /health/slack-token/refresh` | Updates tokens after refresh cycle |
| Slack event handlers | All Slack endpoints | Reads bot token for `WebClient` authentication |

---

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `team_id` | `string` | **Yes** | — | Slack workspace ID (e.g. `"T0123456789"`). Primary key — one record per installed workspace |
| `team_name` | `string` | **Yes** | — | Human-readable Slack workspace name |
| `access_token` | `string` | **Yes** | — | Current bot access token — may be rotating (short-lived) or static (long-lived). **Sensitive — never exposed in API responses** |
| `refresh_token` | `string \| null` | No | `null` | OAuth2 refresh token — present only when using rotating tokens. Used to obtain new access tokens |
| `token_type` | `string` | **Yes** | — | Token type: `"bot"` (standard), `"user"` (user-level) |
| `scope` | `string` | **Yes** | — | Space-separated list of granted OAuth scopes (e.g. `"chat:write channels:read channels:history"`) |
| `bot_user_id` | `string` | **Yes** | — | Slack bot user ID (e.g. `"U0123456789"`) — used to identify bot's own messages |
| `app_id` | `string` | **Yes** | — | Slack app ID |
| `expires_at` | `float (unix timestamp)` | No | — | When access token expires — only set for rotating tokens. `null` or `0` for static tokens |
| `authed_user_id` | `string \| null` | No | `null` | Slack user ID who authorized/installed the app |
| `installed_at` | `string (ISO-8601)` | **Yes** | *now* | When the app was first installed to this workspace |
| `updated_at` | `string (ISO-8601)` | **Yes** | *now* | Last token update timestamp |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `team_id` | Unique, Ascending | Primary key lookup — one record per workspace |

---

## Repository Functions

**Source**: `mongodb/slack_oauth/repository.py`

| Function | Purpose |
|----------|---------|
| `upsert_team()` | Insert or replace OAuth record for a workspace |
| `update_tokens()` | Update only token fields after a refresh cycle |
| `get_team(team_id)` | Return OAuth document for a workspace |
| `get_all_teams()` | Return all installed team OAuth records |
| `token_status(team_id)` | Return diagnostic info (token_type, expiry, status — no secrets) |
| `delete_team(team_id)` | Remove OAuth record for a workspace |

---

## Related Collections

None — independent workspace authentication. No foreign keys to other collections.

---

See also: [[MongoDB Schema]], [[Slack/]], [[Health/]], [[Environment Variables]]


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
