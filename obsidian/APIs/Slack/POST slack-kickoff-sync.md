---
tags:
  - api
  - endpoints
  - slack
---

# POST /slack/kickoff/sync

> Start PRD flow from Slack (sync — blocks until done).

**Method**: `POST`
**Path**: `/slack/kickoff/sync`
**Auth**: Slack HMAC-SHA256
**Tags**: Slack Messenger

---

## Request

Same schema as [[POST slack-kickoff]].

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `channel` | `string` | No | `SLACK_DEFAULT_CHANNEL` | Slack channel for results |
| `text` | `string` | **Yes** | — | Product idea (max 50,000 chars) |
| `auto_approve` | `bool` | No | `true` | Skip manual approval |
| `interactive` | `bool` | No | `false` | Interactive mode |
| `notify` | `bool` | No | `true` | Post status to channel |
| `webhook_url` | `string` | No | `null` | SSRF-protected callback (HTTPS) |

---

## Response — 200

Same schema as [[POST slack-kickoff]], but response is delayed until the flow completes.

```json
{
  "run_id": "a1b2c3d4e5f6",
  "status": "completed",
  "idea": "create a PRD for a mobile fitness app"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | Unique run identifier |
| `status` | `string` | Final status: `completed` or `paused` |
| `idea` | `string` | Original idea text |

---

## Database Algorithm

1. Same initial steps as [[POST slack-kickoff]] — validate, resolve channel, generate `run_id`
2. Runs the PRD flow **synchronously** (blocks the HTTP response)
3. Creates `crewJobs` and `workingIdeas` records during flow
4. Returns final status on completion (may take several minutes)

> [!warning] Long Response Time
> This endpoint blocks until the full PRD flow completes. Use `POST /slack/kickoff` (async) for production workloads.

---

## Source

- **Router**: `apis/slack/router.py`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
