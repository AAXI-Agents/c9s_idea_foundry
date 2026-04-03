---
tags:
  - api
  - endpoints
  - sso
  - webhooks
---

# POST /sso/webhooks/events

> Receive SSO lifecycle events — user provisioning, login tracking, token revocation.

**Method**: `POST`
**Path**: `/sso/webhooks/events`
**Auth**: HMAC-SHA256 webhook signature (`X-Webhook-Signature` header)
**Tags**: SSO Webhooks

---

## Request

```json
{
  "event": "user.created",
  "data": {
    "user_id": "usr_abc123",
    "email": "jane@example.com",
    "name": "Jane Smith",
    "roles": ["member"]
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event` | `string` | **Yes** | Event type (see below) |
| `data` | `object` | **Yes** | Event-specific payload |

---

## Supported Events

| Event | Data Fields |
|-------|-------------|
| `user.created` | `user_id`, `email`, `name`, `roles` |
| `user.updated` | `user_id`, `email`, `name`, `roles` |
| `user.deleted` | `user_id`, `email` |
| `login.success` | `user_id`, `email`, `ip_address`, `user_agent` |
| `login.failed` | `email`, `ip_address`, `reason` |
| `token.revoked` | `user_id`, `token_id` |

---

## Response — 200

```json
{ "status": "ok", "event": "user.created" }
```

## Error — 401

Missing or invalid `X-Webhook-Signature`.

---

## Database Algorithm

1. Verify HMAC-SHA256 signature using `SSO_WEBHOOK_SECRET`
2. Parse event type and data
3. Dispatch to handler based on event type
4. For user events: upsert `users` collection
5. For login events: log to `userSession` collection
6. Return confirmation

---

## Source

- **Router**: `apis/sso_webhooks/post_events.py`
- **Collections**: `users`, `userSession`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
