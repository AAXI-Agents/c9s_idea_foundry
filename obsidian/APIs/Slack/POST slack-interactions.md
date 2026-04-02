---
tags:
  - api
  - endpoints
  - slack
---

# POST /slack/interactions

> Block Kit interactive payload handler — buttons, menus, modals.

**Method**: `POST`
**Path**: `/slack/interactions`
**Auth**: Slack HMAC-SHA256
**Tags**: Slack Interactions

---

## Request

Slack interactive payload (URL-encoded form body with `payload` JSON field).

```json
{
  "type": "block_actions",
  "trigger_id": "123.456.abc",
  "user": { "id": "U123ABC" },
  "channel": { "id": "C123ABC" },
  "message": { "ts": "1711234567.000100" },
  "actions": [
    {
      "action_id": "cmd_create_prd",
      "type": "button",
      "value": "create_prd"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `block_actions` (buttons), `view_submission` (modals) |
| `trigger_id` | `string` | Slack trigger for opening modals |
| `user.id` | `string` | User who clicked |
| `channel.id` | `string` | Channel where interaction occurred |
| `message.ts` | `string` | Message timestamp (for thread context) |
| `actions[].action_id` | `string` | Button/action identifier (see table below) |

---

## Response — 200

```json
{ "ok": true }
```

---

## Supported Action IDs

### Command Actions

`cmd_help`, `cmd_create_prd`, `cmd_list_ideas`, `cmd_list_products`, `cmd_resume_prd`, `cmd_restart_prd`, `cmd_check_publish`, `cmd_publish`, `cmd_create_jira`, `cmd_summarize_ideas`, `cmd_current_project`, `cmd_end_session`, `cmd_list_projects`, `cmd_configure_project`, `cmd_configure_memory`, `cmd_switch_project`, `cmd_create_project`

### Flow Control Actions

`refinement_agent`, `refinement_manual`, `refinement_skip`, `idea_approve`, `idea_reject`, `idea_edit`, `req_approve`, `req_reject`, `section_approve`, `section_reject`

### Publishing Actions

`publish_confluence`, `publish_jira`, `publish_both`, `publish_skip`

### Session Actions

`session_start`, `session_end`, `project_select_*`

---

## Source

- **Router**: `apis/slack/interactions_router/`


---

## Database Algorithm

1. Verify Slack HMAC-SHA256 signature
2. Parse URL-encoded `payload` field as JSON
3. Extract `action_id` from `actions[0]`
4. **Command actions** (`cmd_*`): dispatch to `_command_handler.py` → most trigger Slack API responses (post blocks, start flows)
5. **Flow control** (`idea_approve`, `section_approve`, etc.): set `approval_events` / `approval_decisions` in `shared.py` → unblock waiting flow
6. **Publishing** (`publish_confluence`, `publish_jira`): call publishing service → update delivery records in MongoDB
7. **Session** (`project_select_*`): update `userSession` collection → set active project
8. All actions logged to `agentInteractions` collection

---

## Source

- **Router**: `apis/slack/interactions_router/`
- **Command Handler**: `apis/slack/interactions_router/_command_handler.py`
- **Flow Handlers**: `apis/slack/interactive_handlers/`
---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
