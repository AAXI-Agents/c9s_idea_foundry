---
tags:
  - api
  - endpoints
  - slack
---

# POST /slack/kickoff

> Start PRD flow from Slack (async — returns immediately).

**Method**: `POST`
**Path**: `/slack/kickoff`
**Auth**: Slack HMAC-SHA256
**Tags**: Slack Messenger

---

## Request

```json
{
  "channel": "crewai-prd-planner",
  "text": "create a PRD for a mobile fitness app",
  "auto_approve": true,
  "interactive": false,
  "notify": true,
  "webhook_url": "https://example.com/webhooks/prd-result"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `channel` | `string \| null` | No | `SLACK_DEFAULT_CHANNEL` | Slack channel for results |
| `text` | `string \| null` | No | `null` | Product idea (max 50,000 chars) |
| `auto_approve` | `bool` | No | `true` | Run without manual approval |
| `interactive` | `bool` | No | `false` | Interactive mode (overrides `auto_approve`) |
| `notify` | `bool` | No | `true` | Post status updates to channel |
| `webhook_url` | `string \| null` | No | `null` | SSRF-protected callback URL (HTTPS only) |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "status": "running",
  "idea": "create a PRD for a mobile fitness app"
}
```

---

## Database Algorithm

1. Validate `text` is not empty (422 if missing)
2. Resolve channel: `req.channel` or `SLACK_DEFAULT_CHANNEL` env var
3. Generate `run_id = uuid4().hex[:12]`
4. If `interactive=true`: launch `run_interactive_slack_flow()` in background executor
5. If `interactive=false`: launch `_run_slack_prd_flow()` in background executor
6. Background flow creates `crewJobs` record, `workingIdeas` document, and runs the full PRD pipeline
7. Return immediately with `{ run_id, status: "pending", idea }`

> [!note] Webhook Callback
> When `webhook_url` is provided, the server POSTs a JSON payload on completion or failure:
> ```json
> {
>   "run_id": "a1b2c3d4e5f6",
>   "status": "completed",
>   "result": { "...": "..." },
>   "error": null
> }
> ```
> URL must be HTTPS with SSRF protection (blocks private/loopback IPs).

---

## Source

- **Router**: `apis/slack/router.py`
- **Interactive**: `apis/slack/interactive_handlers/`
- **Background**: `_run_slack_prd_flow()` in `apis/slack/router.py`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
