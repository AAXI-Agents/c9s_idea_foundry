# SSO Webhooks API

> Receive SSO lifecycle events — user provisioning, login tracking, and token revocation.

**Base path**: `/sso/webhooks`
**Auth**: HMAC-SHA256 webhook signature verification (`X-Webhook-Signature` header)

---

## Endpoints

| Method | Path | Auth | Request | Response | Purpose |
|--------|------|------|---------|----------|---------|
| `POST` | `/sso/webhooks/events` | Webhook HMAC | SSO event payload | `{ "status": "ok", "event": "..." }` | Receive SSO lifecycle events |

---

## Authentication

Requests are verified via HMAC-SHA256 signature in the `X-Webhook-Signature` header.

**Env var**: `SSO_WEBHOOK_SECRET` — shared secret used to compute the HMAC digest.

The signature is computed over the raw request body:
```
HMAC-SHA256(SSO_WEBHOOK_SECRET, request_body)
```

---

## Request Schema

`POST /sso/webhooks/events`

The request body is an untyped JSON object with `event` and `data` fields:

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
| `event` | `string` | **Yes** | Event type identifier (see Supported Events below) |
| `data` | `object` | **Yes** | Event-specific payload — structure varies by event type |

---

## Supported Events

| Event | Description | Data Fields |
|-------|-------------|-------------|
| `user.created` | New user provisioned in SSO | `user_id`, `email`, `name`, `roles` |
| `user.updated` | User profile or role changed | `user_id`, `email`, `name`, `roles` (updated values) |
| `user.deleted` | User account deactivated/removed | `user_id`, `email` |
| `login.success` | User successfully logged in | `user_id`, `email`, `ip_address`, `user_agent` |
| `login.failed` | Login attempt failed | `email`, `ip_address`, `reason` |
| `token.revoked` | Access token explicitly revoked | `user_id`, `token_id` |

---

## Response Schema

```json
{
  "status": "ok",
  "event": "user.created"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | Always `"ok"` on successful processing |
| `event` | `string` | Echo of the received event type |

---

## Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Missing or invalid `X-Webhook-Signature` header |
| 400 | Malformed JSON body or missing `event` field |
| 500 | Internal processing error |

---

See also: [[API Overview]], [[Environment Variables]]


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
