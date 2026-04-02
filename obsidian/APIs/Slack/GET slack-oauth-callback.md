---
tags:
  - api
  - endpoints
  - slack
---

# GET /slack/oauth/callback

> OAuth v2 install callback — exchanges code for bot tokens.

**Method**: `GET`
**Path**: `/slack/oauth/callback`
**Auth**: None
**Tags**: Slack OAuth

---

## Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `code` | `string` | query | Authorization code from Slack |
| `state` | `string` | query | CSRF token |

---

## Response

Redirects to success page on completion.

---

## Database Algorithm

1. Exchange `code` with Slack API (`oauth.v2.access`)
2. Store bot + user tokens in `.slack_tokens.json`
3. Persist workspace info in `slackOAuth` MongoDB collection
4. Redirect to success page

---

## Source

- **Router**: `apis/slack/oauth_router.py`
- **Collection**: `slackOAuth`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
