---
tags:
  - api
  - endpoints
---

# Slack API

> [!warning] Deprecated — Use Per-Route Files
> This monolithic file is superseded by individual per-route files in [[Slack/]].
> Each endpoint now has its own file with detailed request, response, and database algorithm.
> **Edit the per-route files instead.** This file is kept for historical reference only.

---


> Slack bot integration — PRD flow kickoff, events webhook, and interactive actions.

**Auth**: Slack HMAC-SHA256 signing secret verification (all endpoints)
**Verification**: `SLACK_SIGNING_SECRET` env var, validated via `verify_slack_request` dependency

---

## Endpoints

| Method | Path | Auth | Request | Response | Purpose |
|--------|------|------|---------|----------|---------|
| `POST` | `/slack/kickoff` | Slack HMAC | `SlackPRDKickoffRequest` | `SlackPRDKickoffResponse` | Start PRD flow from Slack (async) |
| `POST` | `/slack/kickoff/sync` | Slack HMAC | `SlackPRDKickoffRequest` | `SlackPRDKickoffResponse` | Start PRD flow from Slack (sync, blocks until done) |
| `POST` | `/slack/events` | Slack HMAC | Slack Events API payload | `{ "ok": true }` | Events API webhook (messages, mentions) |
| `POST` | `/slack/interactions` | Slack HMAC | Slack interaction payload | `{ "ok": true }` | Block Kit button/action handler |
| `GET` | `/slack/oauth/callback` | None | query params | redirect | OAuth v2 install callback |

---

## Request Schemas

### SlackPRDKickoffRequest

`POST /slack/kickoff` or `POST /slack/kickoff/sync`

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

| Field | Type | Required | Constraints | Default | Description |
|-------|------|----------|-------------|---------|-------------|
| `channel` | `string \| null` | No | — | `SLACK_DEFAULT_CHANNEL` env var | Slack channel name or ID to post results to |
| `text` | `string \| null` | No | max 50,000 chars | `null` | Natural-language product idea / feature description |
| `auto_approve` | `bool` | No | — | `true` | Run the full flow without pausing for manual approval |
| `interactive` | `bool` | No | — | `false` | Enable interactive mode — mirrors the CLI experience in Slack. Prompts user to choose refinement mode (agent/manual), approve the refined idea, and approve the requirements breakdown using Block Kit buttons before auto-generating all PRD sections. Overrides `auto_approve` when `true` |
| `notify` | `bool` | No | — | `true` | Post status updates and results back to the Slack channel |
| `webhook_url` | `string \| null` | No | Must be `https://`; SSRF-protected (blocks private/loopback IPs) | `null` | Optional callback URL for result delivery |

> **Security**: `webhook_url` is SSRF-protected — only HTTPS URLs to public IPs are allowed. Private networks, loopback addresses, and non-HTTPS schemes are rejected.

---

## Response Schemas

### SlackPRDKickoffResponse

```json
{
  "run_id": "a1b2c3d4e5f6",
  "status": "running",
  "idea": "create a PRD for a mobile fitness app"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | Unique identifier for the PRD flow run |
| `status` | `string` | Current job status (e.g. `"running"`, `"completed"`) |
| `idea` | `string \| null` | The extracted product idea — `null` if no idea was parsed |

---

## Events API

`POST /slack/events`

Handles Slack Events API callbacks. The endpoint automatically responds with `200 OK` and processes events asynchronously.

### Supported Events

| Event Type | Subtype | Description |
|------------|---------|-------------|
| `url_verification` | — | Slack setup handshake — returns `{ "challenge": "..." }` |
| `event_callback` | `member_joined_channel` | Bot joined a channel — posts introductory message with help buttons |
| `event_callback` | `app_mention` | User @mentioned the bot — interprets message via LLM intent classification |
| `event_callback` | `message` | Threaded follow-up message — continues multi-turn conversation |

### Event Deduplication

- **Method**: In-memory `event_id` tracking
- **TTL**: 5 minutes — duplicate events within this window are silently ignored
- **Behavior**: Duplicate events return `200 OK` without processing

### Thread State Management

The bot maintains in-memory conversation state for threaded conversations:

| Setting | Value | Description |
|---------|-------|-------------|
| **TTL** | 10 minutes | Thread state expires after 10 minutes of inactivity |
| **Max messages** | 20 per thread | Oldest messages are dropped when limit is reached |
| **Thread key** | `(channel, thread_ts)` | Unique identifier for each conversation thread |

### Smart Thread Routing

Threaded messages are only processed if **any** of these conditions are met:

1. Thread exists in in-memory conversation cache
2. Thread is part of an active interactive run
3. User has pending session state (e.g. awaiting input)
4. Channel has an active project session in MongoDB (requires @mention)
5. Bot has previously replied in this thread (checked via `agentInteractions` collection)
6. Working-idea document is linked to this thread via `slack_channel + slack_thread_ts`

---

## Block Kit Interactions

`POST /slack/interactions`

Handles user clicks on Block Kit buttons and interactive elements. All interactions are dispatched by `action_id`.

### Command Actions

These are top-level command buttons available via the help menu and other UI surfaces:

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

These are triggered during interactive PRD generation:

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

### Session Management Actions

| Action ID | Description |
|-----------|-------------|
| `session_start` | Start a new project session |
| `session_end` | End the current session |
| `project_select_*` | Select a project (dynamic action ID suffix) |

---

## OAuth Callback

`GET /slack/oauth/callback`

Handles the OAuth v2 installation flow redirect from Slack.

**Query params**: `code` (authorization code), `state` (CSRF token)

On success, exchanges the code for bot and user tokens, stores them, and redirects to a success page.

---

## Webhook Delivery

When `webhook_url` is provided in `SlackPRDKickoffRequest`, the system delivers results on completion:

```json
{
  "run_id": "a1b2c3d4e5f6",
  "status": "completed",
  "result": { "...": "..." },
  "error": null
}
```

---

See also: [[API Overview]], [[PRD Flow API]], [[Slack Integration]]


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
