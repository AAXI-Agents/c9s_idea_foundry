# UX Design Flow

> Post-PRD — Standalone 2-phase design generation triggered after PRD completion.

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
- **Skip if**: No EPS, or status already `completed` / `prompt_ready`
- **Error handling**: `BillingError`/`ModelBusyError`/`ShutdownError` propagate; other errors caught (PRD saved regardless)

---

## Step-by-Step Flow

### Phase 1 — Draft (UX Designer + Design Partner)

```
run_ux_design_draft(flow) → str
```

#### Step 1 — Agent Setup

- Creates UX Designer agent with `FigmaMakeTool`
- Creates Design Partner agent (gstack design-consultation methodology)

#### Step 2 — Draft Generation

- Task: `create_initial_design_draft_task`
- Input parameters:
  - `{executive_product_summary}`: from CEO Review
  - `{idea}`: refined idea text
  - `{requirements_breakdown}`: from Requirements Breakdown
  - Project config (Figma credentials)

#### Step 3 — Output Parsing

- Scans output for markers:
  - `FIGMA_URL:<url>` → `flow.state.figma_design_url`, status = `"completed"`
  - `FIGMA_PROMPT:<prompt>` → `flow.state.figma_design_prompt`, status = `"prompt_ready"`
  - `FIGMA_ERROR:<message>` → logged, flow continues
  - `FIGMA_SKIPPED:<reason>` → logged, flow continues

#### Step 4 — File Output

- Writes `output/{project_id}/ux design/ux_design_draft.md` (overwritten on each run)

#### Step 5 — Draft Design Specification

The draft covers 12 sections:
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

- Skipped if `figma_design_status` is already `completed` or `prompt_ready`
- UX design state restored from `working_ideas` document on resume

---

## MongoDB Persistence

- `flow.state.figma_design_url` — Figma URL (if created)
- `flow.state.figma_design_prompt` — Figma Make prompt
- `flow.state.figma_design_status` — `"completed"` / `"prompt_ready"` / `"failed"`

---

## Data Flow

```
Input:  flow.state.executive_product_summary (from CEO Review)
        flow.state.idea
        flow.state.requirements_breakdown
Output: flow.state.figma_design_url (Figma URL)
        flow.state.figma_design_prompt (prompt text)
        flow.state.figma_design_status
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

See also: [[PRD Flow]], [[UX Designer]], [[Finalization Flow]], [[CEO Review Flow]]
