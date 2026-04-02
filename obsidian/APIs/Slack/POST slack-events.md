---
tags:
  - api
  - endpoints
  - slack
---

# POST /slack/events

> Slack Events API webhook — handles mentions, messages, and channel joins.

**Method**: `POST`
**Path**: `/slack/events`
**Auth**: Slack HMAC-SHA256
**Tags**: Slack Events

---

## Request

Slack Events API payload (JSON body from Slack).

```json
{
  "type": "event_callback",
  "event_id": "Ev04ABCDEF",
  "event": {
    "type": "app_mention",
    "channel": "C123ABC456",
    "user": "U123ABC456",
    "text": "<@BBOT> create a PRD for dark mode",
    "ts": "1711234567.000100",
    "thread_ts": "1711234567.000100"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `url_verification` or `event_callback` |
| `event_id` | `string` | Unique event ID for deduplication |
| `event.type` | `string` | `app_mention`, `message`, or `member_joined_channel` |
| `event.channel` | `string` | Slack channel ID |
| `event.user` | `string` | User who triggered the event |
| `event.text` | `string` | Message text |
| `event.ts` | `string` | Message timestamp |
| `event.thread_ts` | `string` | Thread parent timestamp (if threaded) |

---

## Response — 200

```json
{ "ok": true }
```

For `url_verification` events: returns `{ "challenge": "<value>" }`

---

## Supported Events

| Event Type | Subtype | Description |
|------------|---------|-------------|
| `url_verification` | — | Slack setup handshake |
| `event_callback` | `member_joined_channel` | Bot joined — posts intro |
| `event_callback` | `app_mention` | @mention — LLM intent classification |
| `event_callback` | `message` | Thread reply — continues conversation |

---

## Event Deduplication

In-memory `event_id` tracking with 5-minute TTL.

---

## Source

- **Router**: `apis/slack/events_router.py`


---

## Database Algorithm

1. Verify Slack HMAC-SHA256 signature
2. If `type == "url_verification"`: return `{ challenge }` (Slack setup)
3. Deduplicate by `event_id` — in-memory cache with 5-min TTL
4. **`member_joined_channel`**: post intro message with help buttons via Slack API
5. **`app_mention`**: check pending session state (`session_manager`) → route to thread handler or LLM intent classifier (`gemini_utils` / `openai_chat`) → dispatch to appropriate handler → log interaction to `agentInteractions` collection
6. **`message` (thread reply)**: check if thread has active flow → inject feedback into flow queue, or route to Idea Agent / Engagement Manager → log to `agentInteractions`

---

## Source

- **Router**: `apis/slack/events_router.py`
- **Message Handler**: `apis/slack/_message_handler.py`
- **Session**: `apis/slack/session_manager.py`
---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
