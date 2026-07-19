---
tags: [api, ideation]
---

# Ideation Flow API

> Interactive structured Q&A pipeline for refining raw ideas before PRD generation.

## Overview

The ideation flow uses C-suite AI agent personas to guide users through a 5-step structured questionnaire. Each step returns decision cards with 3-5 questions × 3 recommendations each.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| POST | `/flow/ideation/kickoff` | Start a new ideation session |
| GET | `/flow/ideation/sessions` | List sessions (paginated) |
| GET | `/flow/ideation/sessions/{id}` | Get session detail |
| GET | `/flow/ideation/sessions/{id}/messages` | Get session messages; supports incremental fetch with `since_message_id` |
| POST | `/flow/ideation/sessions/{id}/respond` | Answer agent questions |
| POST | `/flow/ideation/sessions/{id}/iterate` | Re-run current step |
| POST | `/flow/ideation/sessions/{id}/advance` | Move to next step; idempotent after completion |
| POST | `/flow/ideation/sessions/{id}/rollback` | Go back one step |
| DELETE | `/flow/ideation/sessions/{id}` | Delete session |
| PATCH | `/flow/ideation/sessions/{id}` | Update session metadata |
| WS | `/ws/ideation/{session_id}?token=` | Real-time streaming |

## Auth

- **REST**: SSO Bearer token
- **WebSocket**: JWT via `?token=` query parameter

## Steps (a → e)

| Step | Name | Agent Persona |
|------|------|--------------|
| a | ideation | CEO — strategic vision |
| b | persona | PM — user personas & jobs-to-be-done |
| c | ux | UX Architect — interaction patterns |
| d | technical | CTO/Staff Engineer — feasibility |
| e | summary | PM — synthesize into PRD-ready brief |

## Response Shape (Structured Q&A)

```json
{
  "questions": [
    {
      "id": "q1",
      "text": "Who is the primary user?",
      "recommendations": [
        {"label": "Option A", "rationale": "..."},
        {"label": "Option B", "rationale": "..."},
        {"label": "Option C", "rationale": "..."}
      ]
    }
  ]
}
```

## Messages

`GET /flow/ideation/sessions/{id}/messages` accepts:

| Query param | Type | Purpose |
|-------------|------|---------|
| `step` | string | Optional flow-step filter |
| `after` | ISO timestamp | Return messages after a timestamp |
| `since_message_id` | string | Return messages after this message ID, exclusive, to avoid duplicate incremental fetches |
| `limit` | integer | Max messages, default `100`, range `1`-`500` |

Agent messages are repaired at read time when legacy raw JSON content can be re-parsed into structured cards.

## Advance Response

`POST /flow/ideation/sessions/{id}/advance` returns `user_message_id` when the advance request persisted the user's final answers for the current step. If the session is already completed, the endpoint returns `200` with the existing `prd_run_id` instead of a duplicate `409`.

## WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `agent_typing` | server→client | Agent is generating |
| `new_message` | server→client | New message with structured content |
| `step_advanced` | server→client | Session moved to next step |
| `session_completed` | server→client | All steps done |
| `error` | server→client | Error occurred |

## Source

- `src/crewai_productfeature_planner/apis/ideation/router.py`
- `src/crewai_productfeature_planner/apis/ideation/service.py`
- `src/crewai_productfeature_planner/apis/ideation/_route_websocket.py`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
