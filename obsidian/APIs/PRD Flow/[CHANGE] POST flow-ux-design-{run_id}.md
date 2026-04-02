---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# [CHANGE] POST /flow/ux-design/{run_id}

> **⚠️ This API requires user feedback before implementation.**

Trigger UX design generation from a completed PRD. Currently this flow is only available via Slack interactions (`product_ux_design_*` action IDs).

**Method**: `POST`
**Path**: `/flow/ux-design/{run_id}`
**Auth**: SSO Bearer token
**Tags**: Flow Runs
**Status**: 202 Accepted

---

## Design Questions for User

1. **Prerequisite**: Should this require the PRD to be in `completed` status before triggering? Or allow triggering from any status?
2. **Implementation**: Should this reuse the existing Slack UX design flow logic (`flows/ux_design_flow.py`) or be a separate implementation?
3. **Polling**: Should the UX design status be:
   - Added to `GET /flow/runs/{run_id}` response (a `ux_design_status` field)?
   - A separate endpoint `GET /flow/ux-design/{run_id}`?
4. **Response**: What should the response contain beyond `{ run_id, status: "started" }`?
5. **Figma integration**: The Figma design mentions "Generate a Figma Make design from the PRD" — is there a Figma Make API integration planned, or is this a mockup-generation flow?

---

## Proposed Request

| Param | Type | Location | Description |
|-------|------|----------|-------------|
| `run_id` | `string` | path | Completed PRD run to generate UX design for |

---

## Proposed Response — 202

```json
{
  "run_id": "a1b2c3d4e5f6",
  "status": "started",
  "message": "UX design generation started for this PRD"
}
```

---

## Existing Implementation

- **UX Design Flow**: `flows/ux_design_flow.py` — CrewAI flow for UX design generation
- **Slack Trigger**: `apis/slack/interactions_router/` handles `product_ux_design_*` actions
- **Status Field**: `workingIdeas.ux_design_status` already tracked (`""`, `"generating"`, `"completed"`)

---

## Source

- **Existing Flow**: `flows/ux_design_flow.py`
- **Slack Handler**: `apis/slack/interactions_router/`

---

## Change Requests

### Pending

- [ ] Implement after user provides answers to design questions above

### Completed

_No completed change requests._
