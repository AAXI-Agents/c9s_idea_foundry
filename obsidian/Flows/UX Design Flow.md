# UX Design Flow

> Post-PRD — Standalone 2-phase design generation triggered by Finalization (Step 7).

| Field | Value |
|-------|-------|
| **Phase** | Post-PRD |
| **Agents** | [[UX Designer]], Design Partner, Senior Designer |
| **LLM Tier** | Research (Gemini) |
| **Source** | `flows/_ux_design.py`, `flows/ux_design_flow.py` |
| **Entry Point** | `kick_off_ux_design_flow(flow)` |
| **Introduced** | v0.20.0 (refactored v0.41.0) |

---

## Purpose

Convert the Executive Product Summary into a structured, production-ready design specification through a 2-phase collaborative design flow. Phase 1 drafts with two agents, Phase 2 reviews with a senior designer applying a 7-pass quality check.

---

## Trigger Conditions

Called by `_trigger_ux_design_flow()` in `_finalization.py` after finalization:
- **Required**: Executive Product Summary present
- **Skip if**: No EPS, or status already `completed`
- **Error handling**: `BillingError`/`ModelBusyError`/`ShutdownError` propagate; other errors caught (PRD saved regardless)

---

## Step-by-Step Flow

### Phase 1 — Draft (Design Partner + UX Designer)

```
run_ux_design_draft(flow) → str
```

#### Step 1 — Design Specification Scope

The Design Partner agent (gstack design-consultation methodology) structures the draft across 12 sections:
1. Product context
2. Aesthetic direction
3. Typography
4. Color palette
5. Spacing system
6. Layout grid
7. Motion & animation
8. Shadows & elevation
9. Component patterns
10. Interaction states
11. CSS token export
12. Decisions log

Includes AI slop avoidance blacklist.

#### Step 2 — Draft Generation

- Task: `create_initial_design_draft_task`
- Input parameters:
  - `{executive_product_summary}`: from CEO Review
  - `{idea}`: refined idea text
  - `{requirements_breakdown}`: from Requirements Breakdown

#### Step 3 — File Output

- Writes `output/{project_id}/ux design/ux_design_draft.md` (overwritten on each run)

---

### Phase 2 — Review (Senior Designer)

```
run_ux_design_review(flow, initial_draft) → str
```

#### Step 1 — Agent Setup

- Creates Senior Designer agent (gstack plan-design-review methodology)

#### Step 2 — 7-Pass Review

| Pass | Focus |
|------|-------|
| 1 | Information architecture |
| 2 | Interaction states |
| 3 | User journey |
| 4 | AI slop detection |
| 5 | Design system alignment |
| 6 | Responsive / accessibility |
| 7 | Unresolved decisions |

Each pass scores before/after (0-10).

#### Step 3 — File Output

- Writes `output/{project_id}/ux design/ux_design_final.md` (created once)

---

## Progress Events

| Event | When |
|-------|------|
| `ux_design_start` | UX design flow begins |
| `ux_design_draft_complete` | Phase 1 draft finished |
| `ux_design_complete` | Phase 2 review finished |

---

## File Output

Only 2 files per product idea (fixed names, overwrite on each run):
- `output/{project_id}/ux design/ux_design_draft.md`
- `output/{project_id}/ux design/ux_design_final.md`

---

## Resume Behaviour

- Skipped if `ux_design_status` is already `completed`
- UX design state restored from `working_ideas` document on resume

---

## MongoDB Persistence

- `flow.state.ux_design_content` — Markdown design specification content
- `flow.state.ux_design_status` — `"completed"` or `""`

---

## Data Flow

```
Input:  flow.state.executive_product_summary (from CEO Review)
        flow.state.idea
        flow.state.requirements_breakdown
Output: flow.state.ux_design_content (markdown design spec)
        flow.state.ux_design_status
        Files: ux_design_draft.md, ux_design_final.md
```

---

## Source Files

- `flows/_ux_design.py` — `run_ux_design_draft()`, `run_ux_design_review()`
- `flows/ux_design_flow.py` — `kick_off_ux_design_flow()` entry point
- `agents/ux_designer/agent.py` — agent factories
- `agents/ux_designer/config/agent.yaml` — UX Designer config
- `agents/ux_designer/config/design_partner.yaml` — Design Partner config
- `agents/ux_designer/config/senior_designer.yaml` — Senior Designer config

---

See also: [[PRD Flow]], [[UX Designer]], [[Finalization Flow|Step 7 — Finalization Flow]], [[CEO Review Flow|Step 4 — CEO Review Flow]]


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

- [x] Remove FigmaMakeTool agent setup (old Step 1) and Figma output parsing (old Step 3) — output markdown only, no Figma interaction *(completed 2026-03-29)*
- [x] Move Draft Design Specification (old Step 5) to Step 1 as the Design Partner agent’s role definition *(completed 2026-03-29)*
