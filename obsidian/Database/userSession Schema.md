---
tags:
  - database
  - mongodb
---

# userSession Schema

> User and channel session management — tracks which project a user or channel is currently working in.

**Collection**: `userSession`
**Primary Key**: `session_id` (unique index)
**Two session types**: User sessions (per-user) and Channel sessions (per-channel)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[Slack/]] | `cmd_switch_project` | Switches user's active session to a different project |
| [[Slack/]] | `cmd_end_session` | Ends user's active session |
| [[Slack/]] | Events router | Checks for active channel session (smart thread routing) |
| [[Slack/]] | Interactions router | Reads active session to determine project context |
| [[Ideas/]] | `GET /ideas` | Filters ideas by active session's project |

---

## Fields — User Sessions

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | `string` | **Yes** | *UUID hex* | Unique session identifier. Primary key |
| `user_id` | `string` | **Yes** | — | Slack user ID (e.g. `"U0123456789"`) |
| `channel` | `string` | **Yes** | — | Slack channel where the session was started |
| `project_id` | `string` | **Yes** | — | FK → `projectConfig.project_id`. The project this session is working in |
| `project_name` | `string` | **Yes** | — | Denormalized project name for display (avoids join on every read) |
| `active` | `bool` | **Yes** | `true` | `true` while session is open. Only one active session per user at a time |
| `started_at` | `string (ISO-8601)` | **Yes** | *now* | When the session was created |
| `ended_at` | `string \| null` | No | `null` | When the session was explicitly ended — `null` while active |

---

## Fields — Channel Sessions

Channel sessions provide channel-wide project context (e.g. "this channel is for Project X").

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | `string` | **Yes** | *UUID hex* | Unique session identifier. Primary key |
| `context_type` | `string` | **Yes** | `"channel"` | Always `"channel"` for channel sessions — distinguishes from user sessions |
| `channel` | `string` | **Yes** | — | Slack channel ID. Only one active channel session per channel |
| `project_id` | `string` | **Yes** | — | FK → `projectConfig.project_id` |
| `project_name` | `string` | **Yes** | — | Denormalized project name |
| `activated_by` | `string` | **Yes** | — | Slack user ID who activated the channel session |
| `active` | `bool` | **Yes** | `true` | `true` while session is open |
| `started_at` | `string (ISO-8601)` | **Yes** | *now* | When the session was created |
| `ended_at` | `string \| null` | No | `null` | When the session ended |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `session_id` | Unique, Ascending | Primary key lookup |
| `(user_id, active)` | Compound, Ascending | Find user's active session quickly |
| `(channel, context_type, active)` | Compound, Ascending | Find channel's active session |

---

## Repository Functions

**Source**: `mongodb/user_session/repository.py`

### User Sessions
| Function | Purpose |
|----------|---------|
| `start_session()` | Create new user session — closes any existing active session first |
| `end_active_session()` | End user's currently active session |
| `switch_session()` | End current + start new session atomically |
| `get_active_session()` | Return user's active session or `None` |
| `get_session(session_id)` | Fetch session by ID |
| `list_sessions(user_id, limit)` | Return user's recent sessions, newest first |

### Channel Sessions
| Function | Purpose |
|----------|---------|
| `start_channel_session()` | Create channel-scoped session |
| `end_channel_session()` | End channel's active session |
| `get_active_channel_session()` | Return channel's active session or `None` |

---

## Related Collections

| Collection | Relationship |
|------------|-------------|
| [[projectConfig Schema]] | `project_id` → `projectConfig.project_id` (N:1) |

---

See also: [[MongoDB Schema]], [[Slack/]], [[Slack Integration]]


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
