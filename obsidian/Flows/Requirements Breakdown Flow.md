---
tags:
  - flows
  - pipeline
---

# Step 3 — Requirements Breakdown Flow

> Pipeline Step 3 — Decompose the refined idea into granular, implementation-ready requirements.

| Field | Value |
|-------|-------|
| **Phase** | 1 (runs after executive summary approval) |
| **Agent** | [[Requirements Breakdown]] |
| **LLM Tier** | Research (Gemini) |
| **Source** | `orchestrator/_requirements.py` |
| **Stage Factory** | `build_requirements_breakdown_stage(flow)` |

---

## Purpose

Decompose a refined product idea into granular, implementation-ready product requirements. Each feature includes data entities, attributes, state machines, API contracts, AI augmentation points, and acceptance criteria. The output feeds the Engineering Manager and section drafting phases.

---

## Step-by-Step Flow

### Step 1 — Skip Check

```
_should_skip() → bool
```

Skips this phase if:
- `flow.state.requirements_broken_down == True` (already completed)
- No Gemini credentials

### Step 2 — Requirements Execution

```
_run() → StageResult
```

- Calls `agents.requirements_breakdown.breakdown_requirements(idea, run_id, original_idea, project_id)`
- Runs iterative cycles:
  1. **Breakdown**: `breakdown_requirements_task` — decompose into features with entities, state machines, API contracts, acceptance criteria (2000-5000 words)
  2. **Evaluate**: `evaluate_requirements_task` — score 6 criteria, determine if ready
  3. **Repeat** if not all criteria ≥ 4
- Returns `StageResult(output=requirements_str, history=list[dict])`

### Step 3 — State Update

```
_apply(result) → None
```

- `flow.state.requirements_breakdown = result.output`
- `flow.state.breakdown_history = result.history`
- `flow.state.requirements_broken_down = True`

### Step 4 — User Approval Gate

```
_requires_approval() → bool
_get_approval() → bool
```

Auto-approves (skips gate) if:
- Sections already have content (resumed run)
- Specialist agents already produced output (`executive_product_summary`, `engineering_plan`, or `ux_design_status` present)

Otherwise:
- Calls `flow.requirements_approval_callback(requirements_breakdown, idea, run_id, breakdown_history)`
- If user declines: raises `RequirementsFinalized()` — flow stops

**Requirements gate bypass** (v0.20.1): Auto-approves on resume when specialist agent state is present, preventing 10-minute timeout re-prompts.

---

## Scoring Criteria

| Criterion | Threshold |
|-----------|-----------|
| Feature completeness | ≥ 4 / 5 |
| Entity granularity | ≥ 4 / 5 |
| State machine rigour | ≥ 4 / 5 |
| AI augmentation depth | ≥ 4 / 5 |
| API contract precision | ≥ 4 / 5 |
| Acceptance criteria coverage | ≥ 4 / 5 |

All six must score ≥ 4 for the requirements to pass.

---

## Progress Events

| Event | When |
|-------|------|
| `pipeline_stage_start` | Requirements breakdown begins |
| `pipeline_stage_complete` | Breakdown finished |
| `pipeline_stage_skipped` | Skipped (already broken down or no credentials) |

---

## Resume Behaviour

On resume, skipped if `flow.state.requirements_broken_down == True`. Requirements text and history restored from MongoDB `working_ideas.requirements_breakdown[-1]`.

---

## MongoDB Persistence

- `save_iteration(run_id, step="requirements_breakdown", ...)` — after each cycle
- Stored in `working_ideas.requirements_breakdown[]` as iteration array
- History stored in `working_ideas.breakdown_history[]`

---

## Data Flow

```
Input:  flow.state.idea (refined)
        flow.state.original_idea
Output: flow.state.requirements_breakdown (structured text)
        flow.state.breakdown_history (all iterations)
Next:   → CEO Review Flow (Phase 1.5a)
        → Engineering Plan Flow (Phase 1.5b, consumes requirements)
        → Section Drafting Flow (Phase 2, uses as context)
```

---

## Source Files

- `orchestrator/_requirements.py` — stage factory and implementation
- `agents/requirements_breakdown/agent.py` — agent factory
- `agents/requirements_breakdown/config/agent.yaml` — role, goal, backstory
- `agents/requirements_breakdown/config/tasks.yaml` — task definitions

---

See also: [[PRD Flow]], [[Requirements Breakdown]], [[Executive Summary Flow|Step 2 — Executive Summary Flow]], [[CEO Review Flow|Step 4 — CEO Review Flow]]


---

## Change Requests

<!-- 
HOW TO USE: Add your change requests below as bullet points.
Codex will implement each request, update this page, bump the
version, and move the completed item to the "Completed" list.

FORMAT:

EXAMPLE:
-->

### Pending

_No pending change requests._

### Completed

_No completed change requests._
