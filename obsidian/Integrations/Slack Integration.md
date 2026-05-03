---
tags:
  - integrations
---

# Slack Integration

> **Status**: OAuth-only mode (v5.1.0+). All idea interaction features have been removed.
> Slack OAuth is retained for future notification delivery (e.g. PRD completion summaries).

## Module Structure

```
apis/slack/
  __init__.py              Re-exports oauth_router
  oauth_router.py          /slack/oauth/callback (OAuth v2)
  verify.py                HMAC-SHA256 request verification
```

## Remaining Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /slack/oauth/callback` | OAuth v2 install/reinstall |

## Token Management

- Supports both static (`xoxb-`) and rotating (`xoxe.`) bot tokens
- Automatic refresh when near expiry (background scheduler)
- Persists to `.slack_tokens.json` + MongoDB (`slackOAuth` collection)
- Health endpoints: `GET /health/slack-token`, `POST /exchange`, `POST /refresh`

## Removed Features (v5.1.0)

The following were removed to consolidate interaction via the web UI:

- **Event subscriptions** — `app_mention`, `message.*` handlers
- **Block Kit interactions** — all button click handlers
- **Interactive flow state** — per-run state tracking, decision resolution
- **Intent classification** — LLM + phrase-based message routing
- **Thread conversations** — per-thread state management
- **Session management** — Slack-based project sessions
- **Block Kit builders** — all 12+ block builder modules
- **Slack tools** — `SlackPostPRDResultTool`, `SlackInterpretMessageTool`

## Future Use

Slack OAuth tokens will be used for:
- Sending PRD completion summaries to channels
- Direct notification delivery from the agent screen
- Future agent ↔ user communication channel

---

See also: [[Jira Integration]], [[Confluence Integration]], [[PRD Flow]]
