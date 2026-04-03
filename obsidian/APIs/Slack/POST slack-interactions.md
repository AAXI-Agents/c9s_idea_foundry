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

| Action ID | Description | Admin Only |
|-----------|-------------|-----------|
| `cmd_help` | Show help — lists all available commands as buttons | No |
| `cmd_create_prd` | Prompt user for a new PRD idea | No |
| `cmd_list_ideas` | List working ideas for the current project | No |
| `cmd_list_products` | List completed products | No |
| `cmd_resume_prd` | Resume a paused PRD flow | No |
| `cmd_restart_prd` | Restart PRD generation from scratch | No |
| `cmd_check_publish` | Check if a PRD is ready to publish | No |
| `cmd_publish` | Publish to Confluence + create Jira tickets | No |
| `cmd_create_jira` | Create Jira tickets from PRD | No |
| `cmd_summarize_ideas` | Summarize multiple ideas | No |
| `cmd_current_project` | Show current project info | No |
| `cmd_end_session` | End the current session | No |
| `cmd_list_projects` | List all projects | No |
| `cmd_configure_project` | Configure project settings | **Yes** |
| `cmd_configure_memory` | Configure memory settings | **Yes** |
| `cmd_switch_project` | Switch to a different project | **Yes** |
| `cmd_create_project` | Create a new project | **Yes** |

### Flow Control Actions

| Action ID | Description |
|-----------|-------------|
| `refinement_agent` | User chose agent-assisted idea refinement |
| `refinement_manual` | User chose manual idea refinement |
| `refinement_skip` | User chose to skip idea refinement |
| `idea_approve` | Approve the refined idea |
| `idea_reject` | Reject and re-refine the idea |
| `idea_edit` | Open idea for manual editing |
| `req_approve` | Approve the requirements breakdown |
| `req_reject` | Reject and re-generate requirements |
| `section_approve` | Approve a PRD section |
| `section_reject` | Reject a PRD section for more iterations |

### Publishing Actions

| Action ID | Description |
|-----------|-------------|
| `publish_confluence` | Publish PRD to Confluence |
| `publish_jira` | Create Jira tickets from PRD |
| `publish_both` | Publish to Confluence and create Jira tickets |
| `publish_skip` | Skip publishing |

### Session Actions

| Action ID | Description |
|-----------|-------------|
| `session_start` | Start a new project session |
| `session_end` | End the current session |
| `project_select_*` | Select a project (dynamic action ID suffix) |

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
